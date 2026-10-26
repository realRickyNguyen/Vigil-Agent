"""Sample mode: record a live run's Zetaris results and Nightshift replies, and replay them with no service and no
network, so a judge without Zetaris or Nightshift can still see a real run.

Recording wraps the two adapters, the app's only network boundary: every query and every model call goes through
ZetarisClient.run and NightshiftClient._post. A recording is one drug's live run, saved as
samples/<drug>.json.gz. Replay hands those results back to the same pipeline code:
- Zetaris: by the exact SQL, in the order each statement ran, with the recorded query IDs, so prompts that cite
  evidence IDs come out the same as in the live run.
- Nightshift: by the exact prompt; failing that, the closest recorded prompt of the same agent (same system prompt),
  with the similarity in the trace. Recorded failures (timeouts, rate limits) are replayed too, so the run takes the
  same fallbacks as the live one.
A statement or prompt the recording does not have fails like an outage and the pipeline degrades that step, as it
would live. Every trace event of a replay carries sample_mode, the console prefixes [SAMPLE], and the dossier and
the API say which recorded run the replay comes from."""
import copy
import dataclasses
import difflib
import gzip
import hashlib
import io
import json
import subprocess
import threading
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.adapters.meterless import MeterlessError, NightshiftClient
from app.adapters.zetaris import AlreadyExists, ZetarisClient, ZetarisError
from app.config import ROOT, Settings
from app.data.faers import DrugNotFound, slug
from app.schemas import QueryResult
from app.tracing import Tracer

FORMAT = "vigil-sample-recording/1"
# Settings that change which queries and model calls a run makes. A replay takes them from the recording, so the
# replaying machine's .env cannot send the pipeline down a path the recording does not have.
RUN_SETTINGS = ("analyst_model", "reviewer_model", "parallel", "reviewer_rounds", "run_budget", "model_timeout",
                "model_stream", "max_retries", "analyst_top", "analyst_extra", "skeptic_items", "skeptic_co_drugs")
NEAREST_AT_LEAST = 0.9  # similarity a prompt needs to reuse the closest recorded reply
NOTE = ("Replayed from a recorded live run: the Zetaris query results and Nightshift model replies are the ones that "
        "run received, played back without calling any service. Run IDs, times and timings are the replay's own.")


class NoSampleRecording(DrugNotFound):
    """Sample mode was asked for a drug that has no recording."""


def recording_path(settings: Settings, drug: str) -> Path:
    return settings.samples_dir / f"{slug(drug)}.json.gz"


def available(settings: Settings) -> list[str]:
    return sorted(p.name[:-len(".json.gz")] for p in settings.samples_dir.glob("*.json.gz"))


def prompt_key(body: dict) -> str:
    return hashlib.sha256(json.dumps({k: body.get(k) for k in ("model", "messages", "max_tokens")},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sql_key(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()


# Recording

class Recording:
    """What one live run's adapters saw, in call order. Thread-safe: the pipeline calls from worker threads."""

    def __init__(self, drug: str):
        self.drug = drug
        self.lock = threading.Lock()
        self.zetaris: dict[str, dict] = {}   # sql key -> {"sql", "purpose", "outcomes": [...]}
        self.nightshift: list[dict] = []     # {"key", "system", "messages", "outcome"} in call order
        self.run_id: str | None = None

    def add_query(self, sql: str, purpose: str, outcome: dict) -> None:
        with self.lock:
            self.zetaris.setdefault(sql_key(sql), {"sql": sql, "purpose": purpose, "outcomes": []})["outcomes"].append(
                outcome)

    def add_call(self, body: dict, outcome: dict) -> None:
        with self.lock:
            self.nightshift.append({"key": prompt_key(body), "model": body.get("model"),
                                    "max_tokens": body.get("max_tokens"), "messages": body.get("messages"),
                                    "outcome": outcome})

    def save(self, path: Path, settings: Settings, status: str) -> dict:
        commit = None
        try:
            commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                    text=True, timeout=10).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
        doc = {"format": FORMAT, "drug": self.drug, "recorded_run_id": self.run_id, "status": status,
               "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": commit,
               "settings": {k: getattr(settings, k) for k in RUN_SETTINGS},
               "served_by": sorted({c["outcome"].get("response", {}).get("model") or "" for c in self.nightshift}
                                   - {""}),
               "zetaris": self.zetaris, "nightshift": self.nightshift}
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
        return {"path": str(path), "queries": sum(len(v["outcomes"]) for v in self.zetaris.values()),
                "model_calls": len(self.nightshift)}


def error_outcome(e: BaseException) -> dict:
    """An adapter's exception as data, enough to raise the same kind of error on replay."""
    out = {"error": type(e).__name__, "message": str(e)[:2000]}
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read()
        except Exception:  # noqa: BLE001 - a body already read or a closed socket
            body = b""
        out.update(code=e.code, body=body.decode(errors="replace")[:4000])
        e.fp = io.BytesIO(body)  # the live caller still reads it
    for attr in ("detail", "retryable"):
        if hasattr(e, attr):
            out[attr] = getattr(e, attr)
    return out


class RecordingZetaris(ZetarisClient):
    def __init__(self, settings: Settings, tracer: Tracer, recording: Recording):
        super().__init__(settings, tracer)
        self.recording = recording

    def run(self, sql: str, purpose: str, agent: str = "data_clerk", ddl: bool = False) -> QueryResult:
        try:
            res = super().run(sql, purpose, agent=agent, ddl=ddl)
        except ZetarisError as e:  # AlreadyExists included
            self.recording.add_query(sql, purpose, error_outcome(e))
            raise
        self.recording.add_query(sql, purpose, {"query_id": res.query_id, "headers": res.headers, "rows": res.rows})
        return res


class RecordingNightshift(NightshiftClient):
    def __init__(self, settings: Settings, tracer: Tracer, recording: Recording):
        super().__init__(settings, tracer)
        self.recording = recording

    def _post(self, body: dict) -> dict:
        try:
            j = super()._post(body)
        except Exception as e:
            self.recording.add_call(body, error_outcome(e))
            raise
        self.recording.add_call(body, {"response": copy.deepcopy(j)})
        return j


_active = threading.local()


@contextmanager
def recording(settings: Settings, drug: str, path: Path | None = None):
    """Record the run made inside the block (run.py --record). The file is written however the run ends, so a run
    that stops on an error can be replayed to the same error."""
    rec = Recording(drug)
    _active.recording = rec
    status = "completed"
    try:
        yield rec
    except BaseException as e:
        status = f"stopped: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        _active.recording = None
        rec.summary = rec.save(path or recording_path(settings, drug), settings, status)


# Replay

def load(settings: Settings, drug: str) -> dict:
    path = recording_path(settings, drug)
    if not path.exists():
        have = available(settings)
        raise NoSampleRecording(f"no sample recording for '{drug}'. Sample mode can replay: "
                                f"{', '.join(have) or 'none (record one with run.py --record)'}")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != FORMAT:
        raise NoSampleRecording(f"{path.name} is not a {FORMAT} file")
    return doc


def raise_outcome(o: dict, url: str = "replay") -> None:
    kind = o["error"]
    if kind == "AlreadyExists":
        raise AlreadyExists(o["message"])
    if kind in ("ZetarisError", "DrugNotFound"):
        raise ZetarisError(o["message"])
    if kind == "HTTPError":
        raise urllib.error.HTTPError(url, o.get("code", 500), o["message"], {}, io.BytesIO(o.get("body", "").encode()))
    if kind == "TimeoutError":
        raise TimeoutError(o["message"])
    e = MeterlessError(o["message"])
    for attr in ("detail", "retryable"):
        if attr in o:
            setattr(e, attr, o[attr])
    raise e


class ReplayZetaris(ZetarisClient):
    def __init__(self, settings: Settings, tracer: Tracer, doc: dict):
        self.s, self.tracer = settings, tracer  # no API key needed: nothing is sent
        self.queries = copy.deepcopy(doc["zetaris"])
        self.used: dict[str, int] = {}
        self.lock = threading.Lock()

    def run(self, sql: str, purpose: str, agent: str = "data_clerk", ddl: bool = False) -> QueryResult:
        key = sql_key(sql)
        with self.lock:
            entry = self.queries.get(key)
            if entry is None:
                outcome = None
            else:
                i = self.used.get(key, 0)
                # Past the recorded runs of a statement, its last outcome stands (the same SQL gives the same rows).
                outcome = entry["outcomes"][min(i, len(entry["outcomes"]) - 1)]
                self.used[key] = i + 1
        if outcome is None:
            self.tracer.event(agent, "replay_miss", source="zetaris", purpose=purpose, sql=sql)
            raise ZetarisError(f"sample mode: this query is not in the recording ({purpose})")
        if "error" in outcome:
            if outcome["error"] == "AlreadyExists":
                self.tracer.event(agent, "zetaris_exists", query_id=None, purpose=purpose, sql=sql)
            else:
                self.tracer.event(agent, "zetaris_error", query_id=None, purpose=purpose, sql=sql,
                                  error=outcome["message"])
            raise_outcome(outcome)
        res = QueryResult(outcome["query_id"], sql, outcome["headers"], outcome["rows"])
        self.tracer.event(agent, "zetaris_query", query_id=res.query_id, purpose=purpose, sql=sql, rows=len(res.rows),
                          ms=0, attempt=0)
        return res


class ReplayNightshift(NightshiftClient):
    def __init__(self, settings: Settings, tracer: Tracer, doc: dict):
        # No token needed either: nothing is sent.
        super().__init__(dataclasses.replace(settings, meterless_token=settings.meterless_token or "replay"), tracer)
        self.calls = doc["nightshift"]
        self.by_key: dict[str, list[int]] = {}
        for i, c in enumerate(self.calls):
            self.by_key.setdefault(c["key"], []).append(i)
        self.used: set[int] = set()
        self.replay_lock = threading.Lock()

    def _rate_limited_now(self) -> float:
        return 0.0  # the recorded 429 is replayed as an error, but nobody waits out a cool-down

    def _pick(self, body: dict) -> tuple[int | None, float | None]:
        """The recorded call for this request: the next unused one with the same prompt, else the closest unused
        one with the same model and system prompt."""
        with self.replay_lock:
            for i in self.by_key.get(prompt_key(body), []):
                if i not in self.used:
                    self.used.add(i)
                    return i, 1.0
            msgs = body.get("messages") or []
            system, rest = (msgs[0].get("content") if msgs else None), json.dumps(msgs[1:], ensure_ascii=False)
            best, best_ratio = None, 0.0
            for i, c in enumerate(self.calls):
                cm = c["messages"] or []
                if i in self.used or c["model"] != body.get("model") or len(cm) != len(msgs) \
                        or (cm[0].get("content") if cm else None) != system:
                    continue
                m = difflib.SequenceMatcher(None, rest, json.dumps(cm[1:], ensure_ascii=False), autojunk=False)
                if m.real_quick_ratio() < NEAREST_AT_LEAST or m.quick_ratio() < NEAREST_AT_LEAST:
                    continue
                r = m.ratio()
                if r > best_ratio:
                    best, best_ratio = i, r
            if best is not None and best_ratio >= NEAREST_AT_LEAST:
                self.used.add(best)
                return best, round(best_ratio, 3)
        return None, None

    def _post(self, body: dict) -> dict:
        i, ratio = self._pick(body)
        if i is None:
            self.tracer.event("orchestrator", "replay_miss", source="nightshift", model=body.get("model"))
            e = MeterlessError("sample mode: this model call is not in the recording")
            e.retryable = False
            raise e
        if ratio != 1.0:
            self.tracer.event("orchestrator", "replay_nearest", source="nightshift", similarity=ratio,
                              recorded_call=i)
        outcome = self.calls[i]["outcome"]
        if "error" in outcome:
            raise_outcome(outcome)
        return copy.deepcopy(outcome["response"])


def with_recorded_settings(settings: Settings, drug: str) -> Settings:
    """The settings a replay runs with: the recording's for everything in RUN_SETTINGS."""
    return dataclasses.replace(settings, **{k: v for k, v in load(settings, drug)["settings"].items()
                                            if k in RUN_SETTINGS})


def recording_active() -> bool:
    return getattr(_active, "recording", None) is not None


def clients(settings: Settings, tracer: Tracer, drug: str):
    """The run's Zetaris and Nightshift clients: live, recording (inside recording()), or replaying a recording
    (SAMPLE_MODE). The third value describes the replay for the dossier, or is None."""
    if settings.sample_mode:
        doc = load(settings, drug)
        info = {"replayed_from_run": doc["recorded_run_id"], "recorded_at": doc["recorded_at"],
                "recorded_status": doc.get("status"), "recorded_code": doc.get("code_commit"),
                "served_by_when_recorded": doc.get("served_by"), "note": NOTE}
        tracer.stamp = {"sample_mode": True}
        tracer.event("orchestrator", "sample_mode", **info)
        return ReplayZetaris(settings, tracer, doc), ReplayNightshift(settings, tracer, doc), info
    rec = getattr(_active, "recording", None)
    if rec is not None:
        rec.run_id = tracer.run_id
        return RecordingZetaris(settings, tracer, rec), RecordingNightshift(settings, tracer, rec), None
    return ZetarisClient(settings, tracer), NightshiftClient(settings, tracer), None
