"""HTTP entry point: POST /run (JSON in, JSON out), GET /runs/<run_id>, GET /health.

Standard library only (ThreadingHTTPServer), bound to 0.0.0.0 so Docker's port mapping reaches it.
One investigation at a time: parallel runs compete for the NVIDIA per-minute cap, so a second POST /run
while one is running gets a structured "Busy" error instead of slowing both down.

POST /run takes either the bare input file ({"drug": "montelukast"}, as in input_examples/) or the
organisers' envelope ({"run_id": ..., "input": {"drug": ...}, "options": {...}}). A run takes several
minutes; the request waits for it by default. With "options": {"wait": false} it returns 202 at once and
GET /runs/<run_id> reports progress and, when done, the same response a waiting request gets."""
import json
import re
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.adapters.meterless import MeterlessError, MeterlessUnauthorized
from app.adapters.zetaris import ZetarisError
from app.config import Settings, get_settings
from app.data.faers import DrugNotFound, validate_drug
from app.orchestration.pipeline import investigate
from app.tracing import Tracer

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")  # it becomes part of the trace and dossier file names
MAX_BODY = 64 * 1024

AGENTS = [
    {"name": "Data Clerk", "role": "Registers openFDA FAERS counts and the current label in Zetaris and computes "
                                   "the disproportionality screen there"},
    {"name": "Analyst", "role": "Classifies each strong reaction against the label and revises when the Reviewer "
                                "objects"},
    {"name": "Reviewer", "role": "Re-checks every finding's numbers and label quote in code, then accepts, "
                                 "rejects with an objection, or leaves the dispute unresolved"},
    {"name": "Skeptic", "role": "Tests the strongest review-next findings against co-reported drugs and sends "
                                "challenged ones back for review"},
]


class BadRequest(ValueError):
    pass


def parse_request(body: dict) -> tuple[str | None, dict, dict]:
    """(run_id or None, the investigation request, options) from either accepted shape."""
    if not isinstance(body, dict):
        raise BadRequest("the body must be a JSON object")
    inp = body.get("input", body)
    if not isinstance(inp, dict) or not isinstance(inp.get("drug"), str):
        raise BadRequest('give the drug as {"drug": "montelukast"} or {"input": {"drug": "montelukast"}}')
    try:
        validate_drug(inp["drug"])  # checked again in the pipeline; here so a bad name gets no trace or run slot
    except ValueError as e:
        raise BadRequest(str(e)) from e
    options = {} if body.get("options") is None else body["options"]
    if not isinstance(options, dict):
        raise BadRequest('"options" must be a JSON object')
    run_id = body.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not RUN_ID.match(run_id)):
        raise BadRequest("run_id must be 1 to 64 letters, digits, hyphens or underscores")
    return run_id, {"drug": inp["drug"]}, options


def classify_error(e: Exception) -> tuple[str, int, bool]:
    """(error type, HTTP status, recoverable) for an exception from a run."""
    if isinstance(e, BadRequest):
        return "InvalidInput", 400, False
    if isinstance(e, DrugNotFound):
        return "DrugNotFound", 404, False
    if isinstance(e, MeterlessUnauthorized):
        return "NightshiftUnauthorized", 502, False
    if isinstance(e, MeterlessError):
        return "NightshiftUnavailable", 502, True
    if isinstance(e, ZetarisError):
        return "ZetarisUnavailable", 502, True
    if isinstance(e, ValueError):  # validate_drug and other input checks
        return "InvalidInput", 400, False
    return "InternalError", 500, False


def error_body(run_id: str | None, kind: str, message: str, recoverable: bool, seconds: float | None = None,
               log_file: str | None = None) -> dict:
    return {"run_id": run_id, "status": "error",
            "error": {"type": kind, "message": message[:500], "recoverable": recoverable},
            "trace_id": run_id, "log_file": log_file,
            "execution_time_seconds": None if seconds is None else round(seconds, 1)}


def summary(d: dict) -> str:
    """One line on what a run found, from its dossier."""
    c = d["counts"]
    return (f"{d['drug']}: {d['data']['drug_reports']} reports; {c['passing_evans']} of {c['reactions_screened']} "
            f"reactions pass the screen; {c['assessed']} assessed ({c['decided_by_rule']} by rule), "
            f"{c['reviewed']} reviewed, {c['unresolved']} unresolved, {c['pending']} pending, {c['failed']} failed; "
            f"{c['review_next']} to review next")


def success_body(d: dict, settings: Settings, seconds: float) -> dict:
    review_next = [{k: q.get(k) for k in ("reaction", "a", "prr", "label_coverage", "context", "reasoning",
                                          "strongest_objection", "next_check", "evidence", "since_last_run")}
                   for q in d["review_queue"]
                   if q.get("review_priority") == "review_next" and q["workflow_status"] == "reviewed"]
    return {
        "run_id": d["run_id"],
        "status": "success",
        "output": {
            "drug": d["drug"],
            "summary": summary(d),
            # Accepted review_next items, the ones an analyst should look at first. Everything else, with its
            # evidence, objections and history, is in the dossier.
            "recommendations": review_next,
            "unresolved": [q["reaction"] for q in d["review_queue"] if q["workflow_status"] == "unresolved"],
            # The World Model's comparison with earlier runs of this drug (each item also has since_last_run).
            "since_last_run": (d.get("world_model") or {}).get("since_last_run"),
            "nightshift_warnings": d.get("nightshift_warnings") or [],
            "artifacts": [f"logs/dossier-{d['run_id']}.json", f"logs/{d['trace']}"],
            "dossier": d,
        },
        "agents": AGENTS,
        "models": {"analyst": settings.analyst_model, "reviewer": settings.reviewer_model,
                   "provider": "Meterless Nightshift",
                   "note": "the model that served each call is in the trace (llm_call events, served_by)"},
        "trace_id": d["run_id"],
        "log_file": f"logs/{d['trace']}",
        "execution_time_seconds": round(seconds, 1),
    }


class Runner:
    """Runs investigations one at a time and remembers recent results for GET /runs/<run_id>."""

    def __init__(self, settings: Settings, investigate_fn=investigate):
        self.settings = settings
        self.investigate = investigate_fn
        self._lock = threading.Lock()
        self._busy = threading.Lock()
        self.current: str | None = None
        self.results: dict[str, dict] = {}

    def start(self, body: dict) -> tuple[int, dict, threading.Thread | None]:
        """Validate, claim the single run slot and create the trace. Returns (HTTP status, body, worker);
        the worker is None when the request was refused."""
        try:
            run_id, request, options = parse_request(body)
        except BadRequest as e:
            return 400, error_body(body.get("run_id") if isinstance(body, dict) else None,
                                   "InvalidInput", str(e), False), None
        settings = self.settings
        if "sample_mode" in options:
            settings = replace(settings, sample_mode=bool(options["sample_mode"]))
        if settings.sample_mode:
            return 501, error_body(run_id, "SampleModeNotImplemented",
                                   "SAMPLE_MODE is not implemented yet; run with Zetaris and Nightshift, "
                                   "or set sample_mode to false", False), None
        if run_id and (settings.logs_dir / f"trace-{run_id}.jsonl").exists():
            return 409, error_body(run_id, "RunIdInUse", f"run_id {run_id} was already used; pick another or "
                                   "leave it out", False), None
        if not self._busy.acquire(blocking=False):
            return 409, error_body(run_id, "Busy", f"investigation {self.current} is still running. Vigil runs "
                                   "one at a time because parallel runs share the NVIDIA per-minute cap; try "
                                   f"again later or poll GET /runs/{self.current}", True), None
        try:
            tracer = Tracer(settings.logs_dir, run_id=run_id)
        except Exception:
            self._busy.release()
            raise
        self.current = tracer.run_id
        with self._lock:
            self.results[tracer.run_id] = {"run_id": tracer.run_id, "status": "running",
                                           "log_file": f"logs/{tracer.path.name}"}
        worker = threading.Thread(target=self._run, args=(request, settings, tracer), daemon=True,
                                  name=f"run-{tracer.run_id}")
        return 202, self.results[tracer.run_id], worker

    def _run(self, request: dict, settings: Settings, tracer: Tracer) -> None:
        t0 = time.monotonic()
        try:
            try:
                d = self.investigate(request, settings, tracer)
                out = success_body(d, settings, time.monotonic() - t0)
            except Exception as e:  # every failure becomes a structured error, never a dropped connection
                kind, status, recoverable = classify_error(e)
                tracer.event("orchestrator", "run_error", error_type=kind, error=f"{type(e).__name__}: {e}"[:500])
                out = {**error_body(tracer.run_id, kind, f"{type(e).__name__}: {e}", recoverable,
                                    time.monotonic() - t0, f"logs/{tracer.path.name}"), "http_status": status}
            with self._lock:
                self.results[tracer.run_id] = out
        finally:
            self.current = None
            self._busy.release()

    def run(self, body: dict) -> tuple[int, dict]:
        """POST /run: wait for the result unless options.wait is false."""
        status, out, worker = self.start(body)
        if worker is None:
            return status, out
        worker.start()
        if (body.get("options") or {}).get("wait", True) is False:
            return 202, {**out, "poll": f"/runs/{out['run_id']}"}
        worker.join()
        return self.status(out["run_id"])

    def status(self, run_id: str) -> tuple[int, dict]:
        """GET /runs/<run_id>: running, the result held in memory, or a dossier left by an earlier process."""
        if not RUN_ID.match(run_id or ""):
            return 400, error_body(None, "InvalidInput", "not a valid run_id", False)
        with self._lock:
            out = self.results.get(run_id)
        if out is not None:
            out = dict(out)
            return out.pop("http_status", 200), out
        dossier = self.settings.logs_dir / f"dossier-{run_id}.json"
        if dossier.exists():
            d = json.loads(dossier.read_text(encoding="utf-8"))
            return 200, success_body(d, self.settings, (d.get("run_time") or {}).get("seconds") or 0)
        return 404, error_body(run_id, "RunNotFound", f"no run {run_id} in this server or in logs/", False)

    def health(self) -> dict:
        s = self.settings
        return {"status": "ok", "busy": self.current is not None, "current_run": self.current,
                "sample_mode": s.sample_mode, "analyst_model": s.analyst_model, "reviewer_model": s.reviewer_model,
                # Addresses only, no keys: shows whether a container reaches the host's services.
                "zetaris_url": s.zetaris_url, "nightshift_url": s.meterless_url,
                "zetaris_key_set": bool(s.zetaris_key), "nightshift_token_set": bool(s.meterless_token)}


def make_handler(runner: Runner):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Vigil"

        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/health":
                return self._send(200, runner.health())
            if path.startswith("/runs/"):
                return self._send(*runner.status(path[len("/runs/"):]))
            self._send(404, error_body(None, "NotFound", "use POST /run, GET /runs/<run_id> or GET /health", False))

        def do_POST(self):
            if self.path.split("?", 1)[0].rstrip("/") != "/run":
                return self._send(404, error_body(None, "NotFound", "use POST /run", False))
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._send(413, error_body(None, "InvalidInput", "request body too large", False))
            try:
                body = json.loads(self.rfile.read(length) or b"null")
            except ValueError as e:
                return self._send(400, error_body(None, "InvalidInput", f"body is not valid JSON: {e}", False))
            try:
                self._send(*runner.run(body))
            except Exception as e:  # a failure before the run started (for example logs/ not writable)
                kind, status, recoverable = classify_error(e)
                self._send(status, error_body(None, kind, f"{type(e).__name__}: {e}", recoverable))

        def log_message(self, fmt, *args):
            print(f"[INFO] {time.strftime('%H:%M:%S', time.gmtime())} http {self.address_string()} {fmt % args}", flush=True)

    return Handler


def serve(port: int, settings: Settings | None = None, host: str = "0.0.0.0") -> None:
    settings = settings or get_settings()
    runner = Runner(settings)
    httpd = ThreadingHTTPServer((host, port), make_handler(runner))
    print(f"[INFO] Vigil API on http://{host}:{port}  (POST /run, GET /runs/<run_id>, GET /health); "
          f"Zetaris {settings.zetaris_url}, Nightshift {settings.meterless_url}"
          + ("; SAMPLE_MODE on" if settings.sample_mode else ""), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import os
    serve(int(os.environ.get("PORT", "8000")))
