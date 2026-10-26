"""Append-only JSONL trace: logs/trace-<run_id>.jsonl. Written only by code, never edited by hand."""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


AGENTS = {"data_clerk": "Data Clerk", "analyst": "Analyst", "reviewer": "Reviewer", "skeptic": "Skeptic",
          "orchestrator": "Orchestrator", "world_model": "World Model"}


def _count(items, key, value) -> int:
    return sum(1 for x in items or [] if x.get(key) == value)


def progress_line(rec: dict) -> str | None:
    """One readable line for a trace event, or None for events too detailed for the console.
    The JSONL trace keeps everything; this is what someone watching a run reads."""
    who, k, d = AGENTS.get(rec["agent"], rec["agent"]), rec["event"], rec
    if k == "run_start":
        return f"Starting run for {d['request'].get('drug')} (Analyst: {d['analyst_model']}, Reviewer: {d['reviewer_model']})"
    if k in ("zetaris_query", "zetaris_exists"):
        rows = f"{d['rows']} rows, {d['ms'] / 1000:.1f} s" if k == "zetaris_query" else "already registered"
        return f"{who} queried Zetaris: {d['purpose']} ({rows})"
    if k == "zetaris_error":
        return f"{who} Zetaris query failed: {d['purpose']}: {str(d.get('error'))[:120]}"
    if k == "evidence_ready":
        return (f"{who}: {d['screened']} reactions screened, {d['passing']} pass the screen; "
                f"label effective {d.get('label_effective')}")
    if k == "selection":
        return f"{who} assesses the {len(d['always'])} strongest rows plus {len(d['chosen'])} of its own picks"
    if k == "routed":
        return f"{who} rule settled {d['reaction']}: {d['classification']}"
    if k == "llm_call":
        return (f"{who} model call served by {d.get('served_by') or d['model']} via Nightshift in {d['ms'] / 1000:.0f} s"
                + (f" (attempt {d['attempt'] + 1})" if d.get("attempt") else ""))
    if k == "llm_retry" and d.get("reason") == "rate_limited":
        return f"{who} hit NVIDIA's rate limit; all model calls pause {d.get('wait_s')} s"
    if k in ("llm_retry", "llm_deadline"):
        return f"{who} model call failed ({str(d.get('error'))[:90]}); " + (
            "splitting the batch" if k == "llm_deadline" else "retrying")
    if k == "nightshift_warning":
        return f"Nightshift setup warning: {d['warning']}"
    if k in ("degraded", "unclassified", "omitted"):
        return f"{who} {k}: {d.get('reaction') or d.get('step')}; {d.get('fallback') or d.get('error') or ''}"[:200]
    if k == "findings":
        return f"{who} round {d['round']}: {len(d['findings'])} findings"
    if k == "verdicts":
        v = d["verdicts"]
        return (f"{who} round {d['round']}: {_count(v, 'decision', 'accept')} accepted, "
                f"{_count(v, 'decision', 'reject')} rejected, {_count(v, 'decision', 'unresolved')} unresolved, "
                f"{_count(v, 'decision', 'unreviewed')} not reviewed, {len(d.get('missing') or [])} missing named")
    if k == "retry":
        return f"{who} sends the Reviewer's objections back to the Analyst (round {d['round']})"
    if k == "dispute_unresolved":
        return f"{who} closes {d['reaction']} as unresolved: {d['reason']}"
    if k == "safety_net":
        return (f"{who} safety net lists {d['terms']} terms for a person to review, {d['not_screened']} of them not "
                f"screened ({d['openfda_requests']} openFDA requests)")
    if k == "co_drug_check":
        return f"{who} checked {d['reaction']} against its co-reported drugs: {d['outcome']}"
    if k == "early_checks":
        return (f"{who} starts its co-drug checks while the Reviewer works: "
                f"{', '.join(d['candidates']) or 'no review_next findings'}")
    if k == "budget_stop":
        return f"{who} skips the {d['step']}: {d['seconds_left']} s left in the run's time budget"
    if k == "remembered":
        s = d.get("since_last_run") or {}
        compared = (f"; against earlier runs: {s.get('changed', 0)} changed, {s.get('unchanged', 0)} unchanged, "
                    f"{s.get('new', 0)} new" if s.get("compared_with_runs") else "; no earlier verdicts for this drug")
        return (f"{who} recorded {d['decisions_recorded']} verdicts against label version "
                f"{(d.get('label_version') or {}).get('effective_time')}; {len(d.get('reopened') or [])} reopened"
                + (compared if s else ""))
    if k == "sample_mode":
        return (f"Sample mode: replaying recorded run {d['replayed_from_run']} ({d['recorded_at']}); no service is "
                f"called")
    if k == "replay_nearest":
        return f"Sample mode: no exact recorded prompt, used the closest one (similarity {d['similarity']})"
    if k == "replay_miss":
        return f"Sample mode: not in the recording ({d['source']}{': ' + d['purpose'] if d.get('purpose') else ''})"
    if k == "run_end":
        return f"Completed in {d.get('seconds')} s; dossier logs/{d['dossier']}"
    return None


class Tracer:
    def __init__(self, logs_dir: Path, run_id: str | None = None, echo: bool = True):
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = logs_dir / f"trace-{self.run_id}.jsonl"
        self.seq = 0
        self.echo = echo  # readable progress lines on stdout, next to the JSONL trace
        self.stamp: dict = {}  # added to every event, e.g. {"sample_mode": True} when a recording is replayed
        self._lock = threading.Lock()  # agents make model calls from worker threads

    def event(self, agent: str, kind: str, **data) -> dict:
        with self._lock:
            self.seq += 1
            rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": self.run_id,
                   "seq": self.seq, "agent": agent, "event": kind, **self.stamp, **data}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
            if self.echo:
                self._say(rec)
        return rec

    def _say(self, rec: dict) -> None:
        """Console output must never break a run: an odd event shape or a console that cannot show a
        character only costs that line."""
        try:
            line = progress_line(rec)
        except (KeyError, TypeError, ValueError):
            line = f"{rec['agent']} {rec['event']}"
        if not line:
            return
        text = (f"[{'SAMPLE' if rec.get('sample_mode') else 'INFO'}] {rec['ts'][11:19]} run_id={self.run_id} "
                f"{line}")
        try:
            print(text, flush=True)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode(), flush=True)


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = round((time.perf_counter() - self.t0) * 1000)
