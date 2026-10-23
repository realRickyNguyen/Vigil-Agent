"""Offline tests for review integrity: nothing unreviewed is shown as reviewed, nothing the model skipped
disappears, and model or database hiccups degrade one item instead of crashing the run.
Run: python -I -m pytest tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.meterless import MeterlessError, MeterlessUnauthorized, NightshiftClient  # noqa: E402
from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.agents.analyst import Analyst  # noqa: E402
from app.agents.reviewer import NO_VERDICT, RECHECK_FAILED, Reviewer  # noqa: E402
from app.orchestration.pipeline import review_queue  # noqa: E402
from app.schemas import Finding, QueryResult, Signal, Verdict  # noqa: E402

LABEL = {"boxed_warning": "WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS  Serious neuropsychiatric (NP) events have been reported.",
         "adverse_reactions": "Headache and abdominal pain were reported."}
ROWS = [Signal("NIGHTMARE", a=1200, b=170000, c=9000, d=20500000, prr=7.14, chi2=9807.4),
        Signal("SLEEP TERROR", a=700, b=170500, c=3000, d=20506000, prr=14.3, chi2=8000.0),
        Signal("ALOPECIA", a=300, b=170900, c=40000, d=20469000, prr=2.1, chi2=150.0)]


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class FakeLLM:
    """Answers chat_json with a canned reply, or raises the given error."""
    def __init__(self, reply=None, error=None):
        self.tracer, self.reply, self.error = FakeTracer(), reply, error

    def chat_json(self, agent, model, messages, **kw):
        if self.error:
            raise self.error
        return self.reply


class FakeClerk:
    def __init__(self, broken=()):
        self.broken = set(broken)

    def signal(self, drug, reaction, agent="reviewer"):
        if reaction in self.broken:
            raise ZetarisError("HTTP 500")
        s = next(r for r in ROWS if r.reaction == reaction)
        return QueryResult("q-re", "sql", [], []), s


def ctx():
    return {"drug": "montelukast", "label": LABEL, "label_qid": "q-label", "evidence_ids": {"q-1"},
            "passing": ROWS, "screen_qid": "q-1", "screen_shown": 3, "screen_passing": 3, "screen_table": "rows",
            "totals": {"drug_reports": 1, "all_reports": 2, "data_last_updated": "x", "query_id": "q-t"}}


def covered(reaction):
    s = next(r for r in ROWS if r.reaction == reaction)
    return Finding(reaction=reaction, a=s.a, prr=s.prr, label_coverage="covered", context="clinical_event",
                   review_priority="lower_priority", reasoning="r", evidence=["q-1"], label_section="boxed_warning",
                   label_term="neuropsychiatric (NP) events")


def test_missing_or_unknown_verdict_is_not_reviewed_rather_than_accepted():
    llm = FakeLLM({"verdicts": [{"reaction": "nightmare", "decision": "accept", "reason": "ok"},
                                {"reaction": "SLEEP TERROR", "decision": "Reject", "reason": "wrong section"}]})
    verdicts, _, _ = Reviewer(llm, "m", FakeClerk()).review(ctx(), [covered("NIGHTMARE"), covered("SLEEP TERROR"),
                                                                    covered("ALOPECIA")], set())
    by = {v.reaction: v for v in verdicts}
    assert by["NIGHTMARE"].decision == "accept"
    assert by["SLEEP TERROR"].decision == "reject"           # capitalised decisions are understood
    assert by["ALOPECIA"].decision == "unreviewed"           # no verdict in the reply: not an acceptance
    assert by["ALOPECIA"].reason == NO_VERDICT


def test_a_failed_recheck_marks_one_finding_not_reviewed_instead_of_crashing():
    llm = FakeLLM({"verdicts": [{"reaction": "NIGHTMARE", "decision": "accept"}]})
    verdicts, _, _ = Reviewer(llm, "m", FakeClerk(broken={"SLEEP TERROR"})).review(
        ctx(), [covered("NIGHTMARE"), covered("SLEEP TERROR")], set())
    by = {v.reaction: v for v in verdicts}
    assert by["NIGHTMARE"].decision == "accept"
    assert by["SLEEP TERROR"].decision == "unreviewed" and by["SLEEP TERROR"].reason.startswith(RECHECK_FAILED)


def test_a_rejected_token_stops_the_run():
    with pytest.raises(MeterlessUnauthorized):
        Reviewer(FakeLLM(error=MeterlessUnauthorized("401")), "m", FakeClerk()).review(ctx(), [covered("NIGHTMARE")], set())
    with pytest.raises(MeterlessUnauthorized):
        Analyst(FakeLLM(error=MeterlessUnauthorized("401")), "m").classify(ctx(), ["NIGHTMARE"])
    with pytest.raises(MeterlessUnauthorized):
        Analyst(FakeLLM(error=MeterlessUnauthorized("401")), "m").pick(ctx())


def test_reactions_the_reply_leaves_out_are_reported_and_names_are_matched_loosely():
    reply = {"findings": [{"reaction": "sleep  terror", "a": 700, "prr": 14.3, "context": "clinical_event",
                           "label_coverage": "not_found", "review_priority": "insufficient_evidence", "reasoning": "r"}]}
    llm = FakeLLM(reply)
    c = ctx()
    findings, _ = Analyst(llm, "m").classify(c, ["SLEEP TERROR", "ALOPECIA"])
    assert [f.reaction for f in findings] == ["SLEEP TERROR"]          # the table's spelling is kept
    assert c["unclassified"] == ["ALOPECIA"]                            # left out of the reply: reported
    assert any(k == "unclassified" and d["reaction"] == "ALOPECIA" for _, k, d in llm.tracer.events)


def test_an_empty_pick_falls_back_to_the_strongest_rows():
    llm = FakeLLM({"picked": [{"reaction": "NOT IN THE TABLE", "why": "x"}]})
    assert Analyst(llm, "m").pick(ctx()) == [r.reaction for r in ROWS]
    assert any(k == "degraded" for _, k, _ in llm.tracer.events)
    assert Analyst(FakeLLM({"picked": [{"reaction": "alopecia"}]}), "m").pick(ctx()) == ["ALOPECIA"]


class CannedClient(NightshiftClient):
    def __init__(self, replies):
        self.tracer, self.replies = FakeTracer(), list(replies)

    def chat(self, agent, model, messages, **kw):
        return self.replies.pop(0)


def test_two_bad_json_replies_raise_a_model_error_not_a_crash():
    with pytest.raises(MeterlessError):
        CannedClient(["not json", "still not json"]).chat_json("analyst", "m", [{"role": "user", "content": "x"}])
    assert CannedClient(["not json", '{"ok": 1}']).chat_json("analyst", "m", []) == {"ok": 1}


def test_model_numbers_with_commas_or_words_do_not_crash():
    f = Finding.from_dict({"reaction": "NIGHTMARE", "a": "1,200", "prr": "n/a"})
    assert (f.a, f.prr) == (1200, 0.0)


def test_a_claim_that_failed_code_checks_does_not_head_the_queue():
    bad = Finding("PNEUMONIA", a=10, prr=3.0, label_coverage="not_found", context="clinical_event",
                  review_priority="review_next", reasoning="r", next_check="n", evidence=["q-1"])
    good = Finding("NIGHTMARE", a=1200, prr=7.14, label_coverage="not_found", context="clinical_event",
                   review_priority="review_next", reasoning="r", next_check="n", evidence=["q-1"])
    state = {
        "PNEUMONIA": {"finding": bad, "status": "unresolved", "history": [], "note": "rounds ran out",
                      "verdict": Verdict("PNEUMONIA", "reject", "failed code checks",
                                         {"not_named_in_label": (False, "label text contains 'pneumonia'")})},
        "NIGHTMARE": {"finding": good, "status": "reviewed", "history": [],
                      "verdict": Verdict("NIGHTMARE", "accept", "ok", {"cites_evidence": (True, "q-1")})},
    }
    queue = review_queue(state, ROWS, [], [])
    assert queue[0]["reaction"] == "NIGHTMARE"
    pneu = next(q for q in queue if q["reaction"] == "PNEUMONIA")
    assert pneu["review_priority"] == "insufficient_evidence" and "failed code checks" in pneu["status_note"]
    assert pneu["history"] == [] and pneu["workflow_status"] == "unresolved"
