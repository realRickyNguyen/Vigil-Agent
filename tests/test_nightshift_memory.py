"""Offline checks that Nightshift's H-MEM is kept out of every model call. Run: python -I -m pytest tests"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless  # noqa: E402


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class Reply:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def test_every_call_gets_its_own_scope_so_no_earlier_answer_is_injected(monkeypatch):
    """Nightshift walls H-MEM by meterless-scope. Under the shared scope "user", each call got up to 3 earlier
    answers, which replayed one wrong 22 Oct answer into every later montelukast run."""
    sent = []

    def urlopen(req, timeout):
        sent.append(req)
        return Reply({"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(meterless.urllib.request, "urlopen", urlopen)
    settings = SimpleNamespace(meterless_token="t", meterless_url="http://x", meterless_app="vigil",
                               model_timeout=1, max_retries=0)
    client = meterless.NightshiftClient(settings, FakeTracer())
    for _ in range(2):
        client.chat("analyst", "m", [{"role": "user", "content": "the same prompt twice"}])
    scopes = [r.get_header("Meterless-scope") for r in sent]
    assert len(set(scopes)) == 2 and "user" not in scopes
    assert [r.get_header("Meterless-app") for r in sent] == ["vigil", "vigil"]
