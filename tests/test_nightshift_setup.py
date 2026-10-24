"""Offline checks of the Nightshift setup warning. Run: python -I -m pytest tests"""
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless  # noqa: E402
from app.adapters.meterless import nightshift_steps, setup_problems  # noqa: E402

ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


def receipt(scaffold=False):
    return {"meterless": {"receipt": {"receipt_id": "r", "hmem": None, "phases": [{"phase": "final_synthesis"}],
                                      "reasoning_scaffold": {"active": scaffold}}}}


def test_no_problem_when_the_requested_model_answers_without_the_scaffold():
    assert setup_problems(ULTRA, ULTRA, nightshift_steps(receipt())) == []
    assert setup_problems(ULTRA, None, None) == []  # nothing to judge without a served model or a receipt


def test_another_model_or_the_scaffold_is_a_problem():
    other = setup_problems(ULTRA, "nvidia/nemotron-3-super-120b-a12b", nightshift_steps(receipt()))
    scaffold = setup_problems(ULTRA, ULTRA, nightshift_steps(receipt(scaffold=True)))
    assert len(other) == 1 and "nemotron-3-super" in other[0] and ULTRA in other[0]
    assert len(scaffold) == 1 and "scaffold" in scaffold[0]


def test_chat_warns_once_per_problem_in_the_trace_and_the_console(monkeypatch, caplog):
    """A default Nightshift routes calls by its own mode, so a run says so at the first call that shows it,
    instead of leaving a judge with a run of quiet timeouts."""
    settings = SimpleNamespace(meterless_token="t", meterless_url="http://x", meterless_app="vigil",
                               model_timeout=1, max_retries=0, model_stream=False)
    client = meterless.NightshiftClient(settings, FakeTracer())
    reply = {"model": "other/model", "choices": [{"message": {"content": "ok"}}], **receipt(scaffold=True)}
    monkeypatch.setattr(client, "_post", lambda body: reply)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            client.chat("analyst", ULTRA, [{"role": "user", "content": "x"}])
    warnings = [d["warning"] for _, kind, d in client.tracer.events if kind == "nightshift_warning"]
    assert len(warnings) == 2  # one for the other model and one for the scaffold, each once
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2
