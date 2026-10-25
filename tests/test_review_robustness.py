"""Offline tests for review robustness: a model or database hiccup degrades one step instead of crashing the run
or passing as reviewed, and a rejected Nightshift token stops the run. Run: python -I -m pytest tests"""
import http.client
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless, zetaris  # noqa: E402
from app.adapters.meterless import MeterlessError, MeterlessUnauthorized  # noqa: E402
from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.agents.analyst import Analyst  # noqa: E402
from app.agents.reviewer import RECHECK_FAILED, Reviewer  # noqa: E402
from app.orchestration.pipeline import review_queue  # noqa: E402
from app.schemas import Finding, Signal, Verdict  # noqa: E402


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class ScriptedLLM:
    """Gives the scripted replies in order, then repeats the last. An exception in the script is raised."""
    def __init__(self, *replies):
        self.tracer, self.replies, self.calls = FakeTracer(), list(replies), 0

    def chat_json(self, agent, model, messages, **kw):
        self.calls += 1
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class Clerk:
    def __init__(self, error=None):
        self.error = error

    def recheck(self, drug, reactions, agent="reviewer"):
        if self.error:
            raise self.error
        return SimpleNamespace(query_id="q-r"), {r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in reactions}


def ctx():
    passing = [Signal(n, a=10, b=1, c=1, d=1, prr=3.0, chi2=50 - i)
               for i, n in enumerate(["SLEEP TERROR", "ALOPECIA", "C", "D", "E", "F"])]
    return {"drug": "x", "passing": passing, "label": {}, "label_qid": "q-l", "screen_qid": "q-s",
            "screen_shown": 6, "evidence_ids": {"q-s"},
            "totals": {"drug_reports": 1, "all_reports": 2, "data_last_updated": "d", "query_id": "q-t"}}


def finding(reaction):
    """A finding that passes every code check against Clerk and an empty label."""
    return Finding(reaction=reaction, a=10, prr=3.0, label_coverage="not_found", context="clinical_event",
                   review_priority="review_next", reasoning="x", next_check="y", evidence=["q-s"])


def test_capitalised_decisions_are_understood():
    llm = ScriptedLLM({"verdicts": [{"reaction": "C", "decision": "Accept", "reason": "ok"},
                                    {"reaction": "D", "decision": " REJECT ", "reason": "wrong section"}]})
    verdicts, _, _ = Reviewer(llm, "m", Clerk(), parallel=1).review(ctx(), [finding("C"), finding("D")], set())
    assert [(v.reaction, v.decision) for v in verdicts] == [("C", "accept"), ("D", "reject")]


def test_a_failed_recheck_marks_findings_not_reviewed_instead_of_crashing():
    llm = ScriptedLLM({"verdicts": []})
    verdicts, missing, _ = Reviewer(llm, "m", Clerk(ZetarisError("HTTP 500")), parallel=1).review(
        ctx(), [finding("C"), finding("D")], set())
    assert [v.decision for v in verdicts] == ["unreviewed", "unreviewed"] and missing == []
    assert verdicts[0].reason.startswith(RECHECK_FAILED) and llm.calls == 0


def test_a_rejected_token_stops_the_run():
    with pytest.raises(MeterlessUnauthorized):
        Reviewer(ScriptedLLM(MeterlessUnauthorized("401")), "m", Clerk(), parallel=1).review(ctx(), [finding("C")], set())
    with pytest.raises(MeterlessUnauthorized):
        Analyst(ScriptedLLM(MeterlessUnauthorized("401")), "m", parallel=1).classify(ctx(), ["C"])
    with pytest.raises(MeterlessUnauthorized):  # on the second ask for a reaction the first reply left out
        Analyst(ScriptedLLM({"findings": []}, MeterlessUnauthorized("401")), "m", parallel=1).classify(ctx(), ["C"])
    with pytest.raises(MeterlessUnauthorized):  # in the one-reaction-per-call fallback after a failed batch
        Analyst(ScriptedLLM(MeterlessError("deadline"), MeterlessUnauthorized("401")), "m")._classify_with_fallback(
            ctx(), ["C", "D"], None)
    with pytest.raises(MeterlessUnauthorized):
        Analyst(ScriptedLLM(MeterlessUnauthorized("401")), "m", top=2, extra=2).pick(ctx())


def test_respelt_reaction_names_keep_the_tables_spelling():
    llm = ScriptedLLM({"findings": [{"reaction": "sleep  terror", "a": 10, "prr": 3.0, "context": "clinical_event",
                                     "label_coverage": "not_found", "review_priority": "insufficient_evidence",
                                     "reasoning": "r"}]})
    c = ctx()
    findings, _ = Analyst(llm, "m", parallel=1).classify(c, ["SLEEP TERROR"])
    assert [f.reaction for f in findings] == ["SLEEP TERROR"] and not c.get("unclassified")
    assert llm.calls == 1  # no second call for a reaction that was answered


def test_model_numbers_with_commas_or_words_do_not_lose_the_finding():
    f = Finding.from_dict({"reaction": "NIGHTMARE", "a": "1,200", "prr": "n/a"})
    assert (f.a, f.prr) == (1200, 0.0)
    assert Finding.from_dict({"reaction": "X", "a": float("inf")}).a == 0  # json.loads reads a bare Infinity


def test_capitalised_enum_values_are_understood():
    f = Finding.from_dict({"reaction": "X", "label_coverage": "Not_found", "context": " Clinical_Event",
                           "review_priority": "REVIEW_NEXT"})
    assert (f.label_coverage, f.context, f.review_priority) == ("not_found", "clinical_event", "review_next")


def test_null_lists_in_a_reply_do_not_crash_the_run():
    c = ctx()
    assert Analyst(ScriptedLLM({"findings": None, "summary": None}), "m", parallel=1).classify(c, ["C"])[0] == []
    assert c["unclassified"] == ["C"]
    assert Analyst(ScriptedLLM({"picked": None}), "m", top=2, extra=2).pick(ctx()) == []
    verdicts, missing, summary = Reviewer(ScriptedLLM({"verdicts": None, "missing": None, "summary": None}), "m",
                                          Clerk(), parallel=1).review(ctx(), [finding("C")], set())
    assert [v.decision for v in verdicts] == ["unreviewed"] and missing == [] and summary == ""


def test_a_dropped_zetaris_connection_is_retried_then_reported_as_a_zetaris_error(monkeypatch):
    monkeypatch.setattr(zetaris.time, "sleep", lambda s: None)
    client = zetaris.ZetarisClient(SimpleNamespace(zetaris_key="k", zetaris_org="o", zetaris_url="http://x",
                                                   max_retries=1, source_timeout=60), FakeTracer())
    for error in (ConnectionResetError("reset"), http.client.IncompleteRead(b"par"), json.JSONDecodeError("cut", "{", 1)):
        calls = []

        def post(sql, timeout, error=error):
            calls.append(sql)
            raise error
        monkeypatch.setattr(client, "_post", post)
        with pytest.raises(ZetarisError):
            client.run("SELECT 1", "test")
        assert len(calls) == 2, error  # retried once, then reported
    replies = [ConnectionResetError("reset"), {"headers": ["x"], "data": [[1]]}]

    def flaky(sql, timeout):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(client, "_post", flaky)
    assert client.run("SELECT 1", "test").rows == [[1]]


def test_a_waiting_call_honours_a_cool_down_extended_while_it_slept(monkeypatch):
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=1), FakeTracer())
    now, sleeps = [100.0], []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
        if len(sleeps) == 1:  # another thread's 429 extends the cool-down meanwhile
            client._cooldown_until = now[0] + 10
    monkeypatch.setattr(meterless.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(meterless.time, "sleep", sleep)
    client._cooldown_until = 115.0
    client._wait_for_cooldown()
    assert sleeps == [15.0, 10.0]


def test_a_claim_that_failed_code_checks_does_not_head_the_queue():
    state = {
        "C": {"finding": finding("C"), "status": "unresolved", "history": [], "note": "review rounds ran out",
              "verdict": Verdict("C", "reject", "failed code checks",
                                 {"not_named_in_label": (False, "label text contains 'c'")})},
        "D": {"finding": finding("D"), "status": "reviewed", "history": [],
              "verdict": Verdict("D", "accept", "ok", {"cites_evidence": (True, "q-s")})},
    }
    queue = review_queue(state, ctx()["passing"], [], [])
    assert queue[0]["reaction"] == "D"
    c = next(q for q in queue if q["reaction"] == "C")
    assert c["review_priority"] == "insufficient_evidence" and "failed code checks" in c["status_note"]
    assert c["workflow_status"] == "unresolved" and "review rounds ran out" in c["status_note"]
