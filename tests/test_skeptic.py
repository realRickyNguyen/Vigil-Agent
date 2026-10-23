"""Offline tests for the Skeptic's co-reported drug check. Run: python -I -m pytest tests"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.skeptic import assess, base_names, pair_stats, rank_co_drugs  # noqa: E402
from app.data.faers import DRUG_FIELD, REACTION_FIELD, phrase  # noqa: E402
from app.orchestration.pipeline import review_queue, skeptic_round  # noqa: E402
from app.schemas import Finding, Signal, Verdict  # noqa: E402


def counts(r11, n11, r10, n10, r01, n01, r00, n00):
    """The Data Clerk's eight counts from the four exposure groups (both, drug only, co-drug only, neither)."""
    return {"n_xyr": r11, "n_xy": n11, "n_xr": r11 + r10, "n_x": n11 + n10, "n_yr": r11 + r01, "n_y": n11 + n01,
            "n_r": r11 + r10 + r01 + r00, "n": n11 + n10 + n01 + n00}


# Reaction rates: neither 1%, drug only 3%, co-drug only 2%, both 4% (close to what additive odds predict).
NO_INTERACTION = counts(40, 1000, 300, 10000, 200, 10000, 1000, 100000)
# Same, but 15% with both drugs.
INTERACTION = counts(150, 1000, 300, 10000, 200, 10000, 1000, 100000)


def test_phrase_encodes_quotes_and_apostrophes():
    clause = phrase(REACTION_FIELD, "CROHN'S DISEASE")
    assert clause == REACTION_FIELD + ":%22CROHN%27S%20DISEASE%22"
    assert '"' not in phrase(DRUG_FIELD, 'x" AND y')


def test_base_names_merge_salts_and_split_combinations():
    assert base_names("ALBUTEROL SULFATE") == ["albuterol"]
    assert base_names("FLUTICASONE PROPIONATE AND SALMETEROL XINAFOATE") == ["fluticasone", "salmeterol"]
    assert base_names("POTASSIUM CHLORIDE") == ["potassium chloride"]  # only salt words: kept whole


def test_rank_co_drugs_drops_the_drug_itself_and_merges_salts():
    rows = [("MONTELUKAST SODIUM", 3961), ("MONTELUKAST", 2402), ("ALBUTEROL SULFATE", 1325), ("ALBUTEROL", 709),
            ("PREDNISONE", 628), ("FLUTICASONE PROPIONATE", 586), ("CETIRIZINE HYDROCHLORIDE", 584)]
    top = rank_co_drugs(rows, "montelukast", 3)
    assert [t["co_drug"] for t in top] == ["albuterol", "prednisone", "fluticasone"]
    assert top[0]["names"] == ["ALBUTEROL SULFATE", "ALBUTEROL"] and top[0]["reports_ranked"] == 2034


def test_pair_stats_adjusted_prr_and_co_drug_prr_match_hand_calculation():
    s = pair_stats(NO_INTERACTION)
    # Mantel-Haenszel over the two strata: RR 2 with the co-drug, RR 3 without it.
    num = 40 * 10000 / 11000 + 300 * 100000 / 110000
    den = 200 * 1000 / 11000 + 1000 * 10000 / 110000
    assert s["adjusted_prr"] == round(num / den, 2) == 2.83
    # The co-drug's own 2x2: a=240 of 11,000 against 1,300 of 110,000 without it.
    assert s["co_drug_prr"] == 1.85 and not s["co_drug_passes_screen"]
    assert s["share"] == round(40 / 340, 3)


def test_omega_follows_noren_2008():
    s = pair_stats(NO_INTERACTION)
    o = {"00": 1000 / 99000, "10": 300 / 9700, "01": 200 / 9800}
    s11 = 1 - 1 / (max(o["00"], o["10"]) + max(o["00"], o["01"]) - o["00"] + 1)
    omega = math.log2((40 + 0.5) / (s11 * 1000 + 0.5))
    assert s["expected_both"] == round(s11 * 1000, 1)
    assert s["omega"] == round(omega, 2)
    assert s["omega025"] == round(omega - 1.959964 / (math.log(2) * math.sqrt(40)), 2)
    assert not s["possible_interaction"]
    assert pair_stats(INTERACTION)["possible_interaction"]


def test_pair_stats_refuses_inconsistent_counts():
    bad = {**NO_INTERACTION, "n_xyr": NO_INTERACTION["n_xr"] + 1}
    assert "error" in pair_stats(bad)
    assert "error" in pair_stats(counts(0, 1000, 300, 10000, 200, 10000, 1000, 100000))


def test_assess_outcomes():
    holds = {"co_drug": "a", **pair_stats(NO_INTERACTION)}
    # Drug alone 1% like background, co-drug 2%, both 2%: the co-drug explains it, no interaction.
    confounded = {"co_drug": "b", **pair_stats(counts(20, 1000, 100, 10000, 200, 10000, 1000, 100000))}
    interacting = {"co_drug": "c", **pair_stats(INTERACTION)}
    assert assess([holds])["outcome"] == "holds"
    out = assess([holds, confounded, interacting])
    assert out["outcome"] == "challenged"
    assert out["adjusted_below_threshold"] == ["b"] and out["possible_interactions"] == ["c"]
    assert assess([{"co_drug": "d", "error": "x"}])["outcome"] == "not_checked"


# --- the Skeptic round in the pipeline -------------------------------------------------------------

class Tracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class FakeSkeptic:
    def __init__(self, outcomes):
        self.outcomes = outcomes

    def check(self, drug, reaction, prr):
        return {"reaction": reaction, "outcome": self.outcomes[reaction], "pairs": [], "query_ids": [f"q-{reaction}"],
                "summary": "s"}


class FakeJudge:
    """Returns the scripted decisions in order, one list per review call."""
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def review(self, ctx, findings, seen):
        self.calls.append([f.reaction for f in findings])
        decisions = self.script.pop(0)
        return [Verdict(f.reaction, decisions[f.reaction], "r", objection="co-drug") for f in findings], [], ""


class FakeHunter:
    def __init__(self):
        self.calls = []

    def revise(self, ctx, rejected, feedback):
        self.calls.append(feedback)
        return [Finding(**{**f.__dict__, "review_priority": "insufficient_evidence", "label_quote": None})
                for f in rejected], ""


def round_state(reactions):
    passing = [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50 - i) for i, r in enumerate(reactions)]
    state = {r: {"finding": Finding(r, 10, 3.0, "not_found", "clinical_event", "review_next", "x", "y", ["q-s"]),
                 "verdict": Verdict(r, "accept", "ok"), "status": "reviewed", "history": [], "note": ""}
             for r in reactions}
    return {"drug": "x", "passing": passing, "evidence_ids": {"q-s"}}, state


def test_skeptic_round_holds_needs_no_model_call():
    ctx, state = round_state(["A"])
    reviewer, analyst = FakeJudge([]), FakeHunter()
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "holds"}), reviewer, analyst, Tracer(), 3)
    assert out == {"checked": 1, "challenged": 0, "priority_changed": 0}
    assert reviewer.calls == [] and "q-A" in ctx["evidence_ids"]
    assert review_queue(state, ctx["passing"], [], [], ctx["skeptic"])[0]["co_reported_drugs"]["outcome"] == "holds"


def test_skeptic_round_challenge_goes_reviewer_analyst_reviewer():
    ctx, state = round_state(["A", "B"])
    reviewer = FakeJudge([{"A": "reject", "B": "accept"}, {"A": "accept"}])
    analyst = FakeHunter()
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "challenged", "B": "challenged"}), reviewer, analyst, Tracer(), 3)
    assert reviewer.calls == [["A", "B"], ["A"]] and len(analyst.calls) == 1
    assert state["A"]["status"] == "reviewed" and state["A"]["finding"].review_priority == "insufficient_evidence"
    assert state["B"]["finding"].review_priority == "review_next"
    assert out == {"checked": 2, "challenged": 2, "priority_changed": 1}
    assert [h["round"] for h in state["A"]["history"]] == ["skeptic", "skeptic_revision"]


def test_skeptic_round_unsettled_dispute_ends_unresolved():
    ctx, state = round_state(["A"])
    reviewer = FakeJudge([{"A": "reject"}, {"A": "reject"}])
    skeptic_round(ctx, state, FakeSkeptic({"A": "challenged"}), reviewer, FakeHunter(), Tracer(), 3)
    assert state["A"]["status"] == "unresolved"


def test_skeptic_round_checks_only_the_top_accepted_review_next_items():
    ctx, state = round_state(["A", "B", "C"])
    state["C"]["finding"].review_priority = "lower_priority"
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "holds", "B": "holds"}), FakeJudge([]), FakeHunter(),
                        Tracer(), 1)
    assert out["checked"] == 1 and list(ctx["skeptic"]) == ["A"]  # A has the highest chi2
