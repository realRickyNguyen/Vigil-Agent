"""Append-only JSONL trace: logs/trace-<run_id>.jsonl. Written only by code, never edited by hand."""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Tracer:
    def __init__(self, logs_dir: Path, run_id: str | None = None):
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = logs_dir / f"trace-{self.run_id}.jsonl"
        self.seq = 0
        self._lock = threading.Lock()  # agents make model calls from worker threads

    def event(self, agent: str, kind: str, **data) -> dict:
        with self._lock:
            self.seq += 1
            rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": self.run_id,
                   "seq": self.seq, "agent": agent, "event": kind, **data}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
        return rec


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = round((time.perf_counter() - self.t0) * 1000)
