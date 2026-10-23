"""Zetaris REST adapter: POST {ZETARIS_REST_URL}/sql-editor/sqls/run with a bearer key,
X-Org-ID and a fresh X-Request-ID. Every query goes to the trace with its SQL and row count."""
import json
import time
import urllib.error
import urllib.request
import uuid

from app.config import Settings
from app.schemas import QueryResult
from app.tracing import Timer, Tracer

# Statements that register sources fetch from openFDA, so they get a longer timeout.
DDL_TIMEOUT = 180


class ZetarisError(RuntimeError):
    pass


class AlreadyExists(ZetarisError):
    pass


class ZetarisClient:
    def __init__(self, settings: Settings, tracer: Tracer):
        if not settings.zetaris_key:
            raise ZetarisError("ZETARIS_API_KEY is not set")
        self.s = settings
        self.tracer = tracer

    def _post(self, sql: str, timeout: int) -> dict:
        body = {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": 1000}
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + self.s.zetaris_key,
                   "X-Org-ID": self.s.zetaris_org,
                   "X-Request-ID": str(uuid.uuid4())}
        req = urllib.request.Request(self.s.zetaris_url + "/sql-editor/sqls/run",
                                     data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")

    def run(self, sql: str, purpose: str, agent: str = "data_clerk", ddl: bool = False) -> QueryResult:
        """Run one statement. Retries timeouts and 5xx; raises AlreadyExists or ZetarisError otherwise."""
        query_id = "q-" + uuid.uuid4().hex[:8]  # short evidence ID the agents cite; Zetaris gets its own UUID
        timeout = DDL_TIMEOUT if ddl else max(self.s.source_timeout, 60)
        last = None
        for attempt in range(self.s.max_retries + 1):
            try:
                with Timer() as t:
                    j = self._post(sql, timeout)
                res = QueryResult(query_id, sql, j.get("headers") or [], j.get("data") or [])
                self.tracer.event(agent, "zetaris_query", query_id=query_id, purpose=purpose, sql=sql,
                                  rows=len(res.rows), ms=t.ms, attempt=attempt)
                return res
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                try:
                    msg = json.loads(msg).get("msg", msg)
                except ValueError:
                    pass
                if "already exist" in msg.lower():
                    self.tracer.event(agent, "zetaris_exists", query_id=query_id, purpose=purpose, sql=sql)
                    raise AlreadyExists(msg[:300])
                last = f"HTTP {e.code}: {msg[:500]}"
                if e.code < 500:
                    break
            except (urllib.error.URLError, TimeoutError) as e:
                last = f"{type(e).__name__}: {e}"
            if attempt < self.s.max_retries:
                time.sleep(2 * (attempt + 1))
        self.tracer.event(agent, "zetaris_error", query_id=query_id, purpose=purpose, sql=sql, error=last)
        raise ZetarisError(last)

    def ensure(self, sql: str, purpose: str) -> bool:
        """Create a source or view. Returns True if created now, False if it already existed."""
        try:
            self.run(sql, purpose, ddl=True)
            return True
        except AlreadyExists:
            return False
