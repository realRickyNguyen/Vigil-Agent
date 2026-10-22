"""Offline unit tests: no Zetaris, no Nightshift. Run: python -I -m pytest tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.meterless import MeterlessError, extract_json  # noqa: E402
from app.agents.hunter import Hunter  # noqa: E402
from app.agents.rules import route  # noqa: E402
from app.data.label import excerpt_block, retrieve  # noqa: E402
from app.agents.judge import code_checks, failed  # noqa: E402
from app.data.faers import signal_sql, slug, sql_str, validate_drug  # noqa: E402
from app.orchestration.pipeline import review_queue, settle  # noqa: E402
from app.schemas import Finding, Signal, Verdict  # noqa: E402

LABEL = {"boxed_warning": "WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS  Serious neuropsychiatric (NP) events have been reported."}
FRESH = Signal("NIGHTMARE", a=1200, b=170000, c=9000, d=20500000, prr=7.14, chi2=9807.4)


def finding(**kw):
    base = dict(reaction="NIGHTMARE", a=1200, prr=7.14, label_coverage="covered", context="clinical_event",
                review_priority="lower_priority", reasoning="r", evidence=["q-1"], label_section="boxed_warning",
                label_term="neuropsychiatric (NP) events")
    return Finding(**{**base, **kw})


NEW = dict(label_coverage="not_found", review_priority="review_next", next_check="check reporter types",
           label_term=None, label_section=None)


@pytest.mark.parametrize("bad", ["", "a", "x\"; DROP VIEW openfda.faers_total", "drug%22", "a" * 60, "../etc"])
def test_validate_drug_rejects_unsafe_names(bad):
    with pytest.raises(ValueError):
        validate_drug(bad)


def test_validate_drug_and_slug():
    assert validate_drug(" Montelukast ") == "montelukast"
    assert slug("insulin glargine-yfgn") == "insulin_glargine_yfgn"


def test_sql_str_escapes_quotes():
    assert sql_str("CROHN'S DISEASE") == "'CROHN\\'S DISEASE'"
    assert "dr.reaction = 'CROHN\\'S DISEASE'" in signal_sql("x", reaction="CROHN'S DISEASE")


def test_extract_json_ignores_think_and_fences():
    assert extract_json('<think>{"no": 1}</think>```json\n{"ok": true}\n```') == {"ok": True}
    assert extract_json('The user wants JSON {"no": 1}.</think>{"ok": true}') == {"ok": True}  # Ultra style
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_checks_pass_for_correct_on_label_finding_and_extract_quote():
    f = finding()
    assert failed(code_checks(f, FRESH, LABEL, {"q-1"})) == []
    assert f.label_quote.endswith("neuropsychiatric (np) events have been reported.")


def test_checks_reject_wrong_numbers():
    assert any(m.startswith("numbers_match") for m in failed(code_checks(finding(a=999), FRESH, LABEL, {"q-1"})))


def test_checks_reject_term_not_in_label():
    f = finding(label_term="nightmares")
    assert any(m.startswith("term_in_label") for m in failed(code_checks(f, FRESH, LABEL, {"q-1"})))
    assert f.label_quote is None


def test_checks_reject_new_signal_the_label_names():
    label = {"adverse_reactions": "Dream abnormalities, including nightmares, were reported."}
    f = finding(**NEW)
    assert any(m.startswith("not_named_in_label") for m in failed(code_checks(f, FRESH, label, {"q-1"})))


def test_checks_review_next_must_be_unlabelled_clinical_event_with_next_check():
    assert failed(code_checks(finding(**NEW), FRESH, LABEL, {"q-1"})) == []
    covered = failed(code_checks(finding(review_priority="review_next", next_check="x"), FRESH, LABEL, {"q-1"}))
    assert any(m.startswith("priority_consistent") for m in covered)
    disease = failed(code_checks(finding(**{**NEW, "context": "treated_condition"}), FRESH, LABEL, {"q-1"}))
    assert any(m.startswith("priority_consistent") for m in disease)
    no_check = failed(code_checks(finding(**{**NEW, "next_check": ""}), FRESH, LABEL, {"q-1"}))
    assert any(m.startswith("has_next_check") for m in no_check)


def test_checks_reject_unknown_field_values():
    assert any(m.startswith("valid_fields") for m in failed(code_checks(finding(context="maybe"), FRESH, LABEL, {"q-1"})))


@pytest.mark.parametrize("coverage,context,expected", [
    ("covered", "clinical_event", "on_label"), ("not_found", "clinical_event", "possible_new_signal"),
    ("unclear", "clinical_event", "possible_new_signal"), ("not_assessed", "treated_condition", "likely_indication_or_disease"),
    ("covered", "treated_condition", "on_label"), ("not_assessed", "non_clinical", "not_meaningful")])
def test_derived_category_follows_gold_precedence(coverage, context, expected):
    assert finding(label_coverage=coverage, context=context).classification == expected


def test_from_dict_defaults_are_cautious():
    f = Finding.from_dict({"reaction": "X", "a": 3, "prr": 2.5})
    assert (f.label_coverage, f.context, f.review_priority) == ("not_assessed", "clinical_event", "insufficient_evidence")


def test_settle_closes_a_dispute_that_goes_round_in_circles():
    f = finding(**NEW)
    reject = Verdict("NIGHTMARE", "reject", "label covers it", objection="dream abnormalities")
    assert settle(f, reject, []) == ("rejected", "")
    history = [{"decision": "reject", "claim": dict(zip(("label_coverage", "context", "review_priority"), f.key()))}]
    status, note = settle(f, reject, history)
    assert status == "unresolved" and "already rejected" in note
    assert settle(f, Verdict("NIGHTMARE", "accept", "ok"), history) == ("reviewed", "")
    assert settle(f, Verdict("NIGHTMARE", "unresolved", "narrower term only"), [])[0] == "unresolved"


def test_review_queue_ranks_review_next_first_and_keeps_open_items():
    passing = [Signal(n, a=10, b=1, c=1, d=1, prr=3.0, chi2=c) for n, c in (("A", 90), ("B", 50), ("P", 40), ("F", 30))]
    state = {
        "A": {"finding": finding(reaction="A"), "verdict": Verdict("A", "accept", "ok"), "status": "reviewed", "history": []},
        "B": {"finding": finding(reaction="B", **NEW), "verdict": Verdict("B", "accept", "ok", objection="vague"),
              "status": "reviewed", "history": []},
    }
    q = review_queue(state, passing, [{"reaction": "P", "why": "strong"}], ["F"])
    assert [x["reaction"] for x in q] == ["B", "A", "P", "F"]
    assert [x["workflow_status"] for x in q] == ["reviewed", "reviewed", "pending", "failed"]
    assert q[0]["strongest_objection"] == "vague" and q[0]["next_check"] == "check reporter types"


def test_checks_reject_missing_evidence_and_unknown_reaction():
    bad = failed(code_checks(finding(evidence=["made-up"]), None, LABEL, {"q-1"}))
    assert any(m.startswith("cites_evidence") for m in bad)
    assert any(m.startswith("in_database") for m in bad)


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class FakeLLM:
    """Fails any call whose prompt mentions a reaction in `fail_on`, or every call if fail_all."""
    def __init__(self, fail_on=(), fail_all=False):
        self.tracer, self.fail_on, self.fail_all = FakeTracer(), set(fail_on), fail_all

    def chat_json(self, agent, model, messages, **kw):
        user = messages[-1]["content"]
        if self.fail_all or any(r in user for r in self.fail_on):
            raise MeterlessError("empty_response")
        rows = [l.split(" | ") for l in user.splitlines() if l.count(" | ") == 3 and not l.startswith("reaction")]
        return {"findings": [{"reaction": r[0], "a": int(r[1]), "prr": float(r[2]), "context": "clinical_event",
                              "label_coverage": "not_found", "review_priority": "review_next", "reasoning": "x",
                              "next_check": "y", "evidence": ["q-s"]}
                             for r in rows], "summary": ""}


def hunter_ctx():
    passing = [Signal(n, a=10, b=1, c=1, d=1, prr=3.0, chi2=50 - i) for i, n in enumerate("ABCDEFGHIJ")]
    return {"drug": "x", "passing": passing, "label": {}, "label_qid": "q-l", "screen_qid": "q-s",
            "label_text": "", "screen_table": "", "screen_shown": 10, "screen_passing": 10,
            "totals": {"drug_reports": 1, "all_reports": 2, "data_last_updated": "d", "query_id": "q-t"}}


def test_pick_falls_back_to_top_chi2_when_model_fails():
    h = Hunter(FakeLLM(fail_all=True), "m")
    assert h.pick(hunter_ctx()) == list("ABCDEFGHIJ")
    assert any(k == "degraded" for _, k, _ in h.llm.tracer.events)


def test_classify_splits_failed_batch_and_reports_unclassified():
    ctx = hunter_ctx()
    h = Hunter(FakeLLM(fail_on={"B |"}), "m")
    findings, _ = h.classify(ctx, ["A", "B", "C", "D"])
    assert [f.reaction for f in findings] == ["A", "C", "D"]
    assert ctx["unclassified"] == ["B"]


MONTELUKAST_LIKE = {
    "indications_and_usage": "Montelukast is indicated for prophylaxis and chronic treatment of asthma.",
    "boxed_warning": "Serious neuropsychiatric events have been reported. Events included agitation, aggression, "
                     "depression, sleep disturbances, suicidal thoughts and behavior.",
    "adverse_reactions": "Common adverse reactions were headache, cough and gastroesophageal reflux.",
    "effective_time": "20260305",
}


def test_retrieve_finds_stems_and_british_spelling():
    hits = retrieve("SUICIDAL IDEATION", MONTELUKAST_LIKE)
    assert hits and "suicidal thoughts" in hits[0][1]
    assert any("gastroesophageal" in s for _, s in retrieve("GASTROOESOPHAGEAL REFLUX DISEASE", MONTELUKAST_LIKE))
    assert retrieve("SPUTUM DISCOLOURED", MONTELUKAST_LIKE) == []


def test_excerpt_block_always_includes_indication_and_boxed_warning():
    block = excerpt_block(["NIGHTMARE"], MONTELUKAST_LIKE, "q-l")
    assert "chronic treatment of asthma" in block and "Serious neuropsychiatric" in block
    assert "NIGHTMARE: (no label sentence shares its words)" in block


def test_rules_route_easy_cases():
    sig = lambda r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    assert route(sig("OFF LABEL USE"), MONTELUKAST_LIKE, ["q"]).classification == "not_meaningful"
    assert route(sig("ASTHMA"), MONTELUKAST_LIKE, ["q"]).classification == "likely_indication_or_disease"
    cough = route(sig("COUGH"), MONTELUKAST_LIKE, ["q"])
    assert (cough.classification, cough.label_section, cough.decided_by) == ("on_label", "adverse_reactions", "rule")
    assert route(sig("NIGHTMARE"), MONTELUKAST_LIKE, ["q"]) is None
    assert route(sig("PRODUCTIVE COUGH"), MONTELUKAST_LIKE, ["q"]) is None  # 'PRODUCT' is not a word here


def test_rule_finding_passes_judge_code_checks():
    cough = route(Signal("COUGH", a=10, b=1, c=1, d=1, prr=3.0, chi2=50), MONTELUKAST_LIKE, ["q-1"])
    fresh = Signal("COUGH", a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    assert failed(code_checks(cough, fresh, MONTELUKAST_LIKE, {"q-1"})) == []
    assert "cough" in cough.label_quote


def test_rejected_rule_finding_goes_to_the_model():
    ctx = hunter_ctx()
    ctx["label"] = {"adverse_reactions": "Reactions included A and B."}
    h = Hunter(FakeLLM(), "m")
    routed, _ = h.classify(ctx, ["A"])
    assert routed[0].decided_by == "rule"
    revised, _ = h.classify(ctx, ["A"], {"rejected": [{"reaction": "A", "reason": "x"}], "missing": []})
    assert revised[0].decided_by == "hunter"


def test_checks_new_signal_must_pass_screen():
    weak = Signal("RASH", a=2, b=1, c=1, d=1, prr=1.5, chi2=1.0)
    f = finding(reaction="RASH", a=2, prr=1.5, **NEW)
    assert any(m.startswith("passes_screen") for m in failed(code_checks(f, weak, LABEL, {"q-1"})))
