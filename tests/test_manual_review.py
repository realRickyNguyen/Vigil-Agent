"""Offline tests for the "needs manual review" flag (eval/MANUAL_REVIEW_RULES.md). Run: python -I -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.orchestration.manual_review import TRIGGERS, manual_review  # noqa: E402
from app.orchestration.pipeline import review_queue  # noqa: E402
from app.schemas import Finding, Signal, Verdict  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# RENAL PAIN, 4 reports, recorded 25 Oct for sotagliflozin with signal_sql. The other rows are made up.
RENAL_PAIN = Signal("RENAL PAIN", a=4, b=540, c=10421, d=20671736, prr=14.59, chi2=38.0)
LABEL = {"adverse_reactions": "Headache and nausea were reported.",
         # Cut from metformin ER's chosen label (25 Oct), which names the condition only as a contraindication.
         "contraindications": "4 CONTRAINDICATIONS Metformin hydrochloride extended-release tablets are "
                              "contraindicated in patients with: Acute or chronic metabolic acidosis, including "
                              "diabetic ketoacidosis, with or without coma."}


def row(name, a=100, chi2=50.0):
    return Signal(name, a=a, b=10000, c=1000, d=20000000, prr=5.0, chi2=chi2)


def finding(name, coverage="covered", priority="lower_priority", a=100, **kw):
    return Finding(reaction=name, a=a, prr=5.0, label_coverage=coverage, context="clinical_event",
                   review_priority=priority, reasoning="x", next_check="y", evidence=["q-s"], **kw)


def entry(f, status="reviewed", history=(), decision="accept"):
    return {"finding": f, "verdict": Verdict(f.reaction, decision, "ok"), "status": status, "history": list(history)}


def accept(rnd=1):
    return {"round": rnd, "decision": "accept"}


def test_an_item_with_no_trigger_is_not_flagged():
    q = review_queue({"HEADACHE": entry(finding("HEADACHE", label_section="adverse_reactions", label_term="headache"),
                                        history=[accept()])}, [row("HEADACHE")], [], [], label=LABEL)
    assert q[0]["manual_review"] == {"needed": False, "reasons": [], "triggers": []}


def test_each_trigger_gives_its_own_reason():
    s = RENAL_PAIN
    few = manual_review({"workflow_status": "reviewed", "history": [accept()]}, s.a)
    assert few == {"needed": True, "reasons": ["fewer than 5 reports (4)"], "triggers": ["few_reports"]}
    assert manual_review({"workflow_status": "reviewed"}, 5)["needed"] is False  # 5 reports is not few
    assert manual_review({"workflow_status": "reviewed", "label_coverage": "unclear"}, 100)["reasons"] == \
        ["label coverage is unclear"]
    rejected = manual_review({"workflow_status": "reviewed", "history": [{"round": 1, "decision": "reject"},
                                                                         {"round": 2, "decision": "accept"}]}, 100)
    assert rejected["triggers"] == ["reviewer_rejected"] and rejected["reasons"] == \
        ["the Reviewer rejected a claim for it (round 1)"]
    for status in ("unresolved", "not_reviewed", "pending", "failed"):
        assert manual_review({"workflow_status": status}, 100)["reasons"] == [f"workflow status is {status}"]
    challenged = manual_review({"workflow_status": "reviewed", "co_reported_drugs": {"outcome": "challenged",
                                                                                     "attenuated_by": []}}, 100)
    assert challenged["reasons"] == ["the Skeptic challenged it"]
    attenuated = manual_review({"workflow_status": "reviewed", "co_reported_drugs": {
        "outcome": "no_challenge", "attenuated_by": ["ASPIRIN", "METOPROLOL"]}}, 100)
    assert attenuated["triggers"] == ["skeptic"] and attenuated["reasons"] == \
        ["adjusting for ASPIRIN, METOPROLOL lowers its PRR by 30% or more"]
    assert manual_review({"workflow_status": "reviewed", "co_reported_drugs": {"outcome": "no_challenge",
                                                                               "attenuated_by": []}}, 100)["needed"] is False


def test_a_name_only_in_the_contraindications_is_flagged_but_one_also_in_an_effect_section_is_not():
    q = review_queue({"METABOLIC ACIDOSIS": entry(finding("METABOLIC ACIDOSIS", "not_found", "review_next"),
                                                  history=[accept()])},
                     [row("METABOLIC ACIDOSIS")], [], [], label=LABEL)
    mr = q[0]["manual_review"]
    assert mr["triggers"] == ["label_unclear"]
    assert mr["reasons"] == ["the label names it only where that never counts as coverage (contraindications)"]
    also = {**LABEL, "warnings_and_cautions": "Metabolic acidosis has been reported."}
    q = review_queue({"METABOLIC ACIDOSIS": entry(finding("METABOLIC ACIDOSIS", label_section="warnings_and_cautions",
                                                          label_term="metabolic acidosis"), history=[accept()])},
                     [row("METABOLIC ACIDOSIS")], [], [], label=also)
    assert q[0]["manual_review"]["needed"] is False


def test_several_triggers_are_all_listed():
    item = {"workflow_status": "unresolved", "label_coverage": "unclear",
            "history": [{"round": 1, "decision": "reject"}, {"round": 2, "decision": "reject"}],
            "co_reported_drugs": {"outcome": "challenged", "attenuated_by": ["OMEPRAZOLE"]}}
    mr = manual_review(item, 4)
    assert mr["triggers"] == list(TRIGGERS)
    assert "round 1, 2" in mr["reasons"][2]
    assert mr["reasons"][4] == "the Skeptic challenged it; adjusting for OMEPRAZOLE lowers its PRR by 30% or more"


def test_the_flag_never_changes_status_priority_or_order():
    # The flagged items (few reports, an unclear label, a rejection, an open status) keep their status and priority,
    # and the queue keeps its order by priority, then status, then chi2.
    rows = [row("A", chi2=90), RENAL_PAIN, row("C", chi2=30), row("D", chi2=20), row("E", chi2=10)]
    state = {
        "A": entry(finding("A", "not_found", "review_next"), history=[accept()]),
        "RENAL PAIN": entry(finding("RENAL PAIN", "not_found", "review_next", a=4), history=[accept()]),
        "C": entry(finding("C", "unclear", "review_next"), history=[accept()]),
        "D": entry(finding("D", "not_found", "review_next"), status="unresolved",
                   history=[{"round": 1, "decision": "reject"}, {"round": 2, "decision": "unresolved"}],
                   decision="unresolved"),
        "E": entry(finding("E"), history=[accept()]),
    }
    q = review_queue(state, rows, [{"reaction": "P", "why": "x"}], [])
    assert [x["reaction"] for x in q] == ["D", "A", "RENAL PAIN", "C", "E", "P"]
    assert [x["manual_review"]["needed"] for x in q] == [True, False, True, True, False, True]
    assert [(x["workflow_status"], x["review_priority"]) for x in q] == [
        ("unresolved", "review_next"), ("reviewed", "review_next"), ("reviewed", "review_next"),
        ("reviewed", "review_next"), ("reviewed", "lower_priority"), ("pending", None)]


def test_the_rules_were_written_down_first_and_name_every_trigger():
    text = (ROOT / "eval" / "MANUAL_REVIEW_RULES.md").read_text(encoding="utf-8")
    assert "25 Oct 2026" in text and "before any run scored them" in text
    for t in TRIGGERS:
        assert f"`{t}`" in text
