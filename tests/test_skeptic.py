"""Offline tests for the Skeptic's co-reported drug check. Run: python -I -m pytest tests"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.skeptic import assess, base_names, pair_stats, rank_co_drugs  # noqa: E402
from app.data.faers import CO_DRUG_FIELDS, REACTION_FIELD, DataClerk, drug_search, phrase  # noqa: E402
from app.schemas import QueryResult  # noqa: E402
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
    assert '"' not in phrase(REACTION_FIELD, 'x" AND y')


class RecordingZetaris:
    def __init__(self):
        self.sql = []

    def ensure(self, sql, purpose):
        self.sql.append(sql)
        return True

    def run(self, sql, purpose, **kw):
        self.sql.append(sql)
        return QueryResult("q-1", sql, ["drug", "reports"], [])


def test_skeptic_queries_use_the_same_drug_search_as_the_screen():
    z = RecordingZetaris()
    clerk = DataClerk(z)
    clerk.co_drugs("montelukast", "DEPRESSION")
    lists = [s for s in z.sql if "CREATE LIGHTNING REST TABLE" in s]
    assert len(lists) == 2 and all(drug_search("montelukast") in s for s in lists)
    assert [f in s for s, f in zip(lists, CO_DRUG_FIELDS)] == [True, True]
    assert "UNION ALL" in z.sql[-1]
    z.sql.clear()
    z.run = lambda sql, purpose, **kw: (z.sql.append(sql), QueryResult("q-2", sql, ["n"], [["1"]]))[1]
    clerk.pair_counts("montelukast", "DEPRESSION", "albuterol")
    tables = [s for s in z.sql if "CREATE LIGHTNING REST TABLE" in s]
    assert len(tables) == 4 and all(drug_search("albuterol") in s for s in tables)
    assert sum(drug_search("montelukast") in s for s in tables) == 2  # n_xy and n_xyr
    assert "faers_d2_montelukast_total" in z.sql[-1] and "faers_d_montelukast" not in z.sql[-1]


def test_base_names_merge_salts_and_split_combinations():
    assert base_names("ALBUTEROL SULFATE") == ["albuterol"]
    assert base_names("FLUTICASONE PROPIONATE AND SALMETEROL XINAFOATE") == ["fluticasone", "salmeterol"]
    assert base_names("POTASSIUM CHLORIDE") == ["potassium chloride"]  # only salt words: kept whole
    assert base_names("ATORVASTATIN CALCIUM, FILM COATED") == ["atorvastatin"]  # a dosage form is not a co-drug
    assert base_names("FLUTICASONE PROPIONATE\\SALMETEROL XINAFOATE") == ["fluticasone", "salmeterol"]


def test_rank_co_drugs_drops_the_drug_itself_and_merges_salts():
    rows = [("MONTELUKAST SODIUM", 3961), ("MONTELUKAST", 2402), ("ALBUTEROL SULFATE", 1325), ("ALBUTEROL", 709),
            ("PREDNISONE", 628), ("FLUTICASONE PROPIONATE", 586), ("CETIRIZINE HYDROCHLORIDE", 584)]
    top = rank_co_drugs(rows, "montelukast", 3)
    assert [t["co_drug"] for t in top] == ["albuterol", "prednisone", "fluticasone"]
    assert top[0]["names"] == ["ALBUTEROL SULFATE", "ALBUTEROL"] and top[0]["reports_ranked"] == 2034
    assert not top[0]["combination_partner"]
    partner = rank_co_drugs([("OXYCODONE AND ACETAMINOPHEN", 300), ("OXYCODONE", 50), ("IBUPROFEN", 100)],
                            "acetaminophen", 2)
    assert partner[0]["co_drug"] == "oxycodone" and partner[0]["combination_partner"]
    assert not partner[1]["combination_partner"]


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
    out = assess([holds, confounded])
    assert out["outcome"] == "challenged" and out["challenge_reasons"] == ["adjusted_below_threshold"]
    assert out["adjusted_below_threshold"] == ["b"]
    # An interaction is context only: it is reported but does not challenge.
    out = assess([holds, interacting])
    assert out["outcome"] == "holds" and out["possible_interactions"] == ["c"]
    assert assess([{"co_drug": "d", "error": "x"}])["outcome"] == "not_checked"


def test_a_pattern_shared_with_most_co_drugs_is_context_not_a_challenge():
    # The co-drug alone has a 6% rate against about 1% elsewhere, so the reaction passes its screen too.
    shared = pair_stats(counts(40, 1000, 300, 10000, 600, 10000, 1000, 100000))
    assert shared["co_drug_passes_screen"] and shared["adjusted_prr"] >= 2
    holds = {"co_drug": "a", **pair_stats(NO_INTERACTION)}
    out = assess([holds, {"co_drug": "e", **shared}, {"co_drug": "f", **shared}])
    assert out["outcome"] == "holds" and out["challenge_reasons"] == []
    assert out["shared_with_co_drugs"] and out["co_drugs_passing_screen"] == ["e", "f"]
    assert not assess([holds, {"co_drug": "e", **shared}, {"co_drug": "g", **holds}])["shared_with_co_drugs"]
    assert not assess([{"co_drug": "e", **shared}])["shared_with_co_drugs"]  # one co-drug is not "most"


class FlakyClerk:
    """co_drugs fails with the given errors first, then answers."""
    def __init__(self, errors):
        self.errors, self.calls = list(errors), 0

    def co_drugs(self, drug, reaction):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return QueryResult("q-list", "", ["drug", "reports"], []), []


def test_co_drug_list_is_retried_once_on_an_openfda_5xx(monkeypatch):
    from app.adapters.zetaris import ZetarisError
    from app.agents.skeptic import Skeptic
    monkeypatch.setattr("app.agents.skeptic.time.sleep", lambda s: None)
    upstream = ZetarisError("HTTP 400: REST API call failed: Server returned HTTP response code: 500 for URL: x")
    clerk = FlakyClerk([upstream])
    ev = Skeptic(clerk).check("x", "R", 3.0)
    assert clerk.calls == 2 and ev["outcome"] == "not_checked" and ev["query_ids"] == ["q-list"]
    clerk = FlakyClerk([upstream, upstream])  # only one retry
    assert Skeptic(clerk).check("x", "R", 3.0)["outcome"] == "failed" and clerk.calls == 2
    clerk = FlakyClerk([ZetarisError("HTTP 400: table or view not found")])  # not an openFDA 5xx: no retry
    assert Skeptic(clerk).check("x", "R", 3.0)["outcome"] == "failed" and clerk.calls == 1


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


class FakeReviewer:
    """Returns the scripted decisions in order, one list per review call."""
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def review(self, ctx, findings, seen):
        self.calls.append([f.reaction for f in findings])
        decisions = self.script.pop(0)
        return [Verdict(f.reaction, decisions[f.reaction], "r", objection="co-drug") for f in findings], [], ""


class FakeAnalyst:
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
    reviewer, analyst = FakeReviewer([]), FakeAnalyst()
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "holds"}), reviewer, analyst, Tracer(), 3)
    assert out == {"checked": 1, "challenged": 0, "challenge_not_reviewed": 0, "priority_changed": 0}
    assert reviewer.calls == [] and "q-A" in ctx["evidence_ids"]
    assert review_queue(state, ctx["passing"], [], [], ctx["skeptic"])[0]["co_reported_drugs"]["outcome"] == "holds"


def test_skeptic_round_challenge_goes_reviewer_analyst_reviewer():
    ctx, state = round_state(["A", "B"])
    reviewer = FakeReviewer([{"A": "reject", "B": "accept"}, {"A": "accept"}])
    analyst = FakeAnalyst()
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "challenged", "B": "challenged"}), reviewer, analyst, Tracer(), 3)
    assert reviewer.calls == [["A", "B"], ["A"]] and len(analyst.calls) == 1
    assert state["A"]["status"] == "reviewed" and state["A"]["finding"].review_priority == "insufficient_evidence"
    assert state["B"]["finding"].review_priority == "review_next"
    assert out == {"checked": 2, "challenged": 2, "challenge_not_reviewed": 0, "priority_changed": 1}
    assert [h["round"] for h in state["A"]["history"]] == ["skeptic", "skeptic_revision"]


def test_skeptic_round_unsettled_dispute_ends_unresolved():
    ctx, state = round_state(["A"])
    reviewer = FakeReviewer([{"A": "reject"}, {"A": "reject"}])
    skeptic_round(ctx, state, FakeSkeptic({"A": "challenged"}), reviewer, FakeAnalyst(), Tracer(), 3)
    assert state["A"]["status"] == "unresolved"


def test_skeptic_round_checks_only_the_top_accepted_review_next_items():
    ctx, state = round_state(["A", "B", "C"])
    state["C"]["finding"].review_priority = "lower_priority"
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "holds", "B": "holds"}), FakeReviewer([]), FakeAnalyst(),
                        Tracer(), 1)
    assert out["checked"] == 1 and list(ctx["skeptic"]) == ["A"]  # A has the highest chi2


def test_failed_challenge_review_keeps_the_round_1_verdict():
    ctx, state = round_state(["A"])
    out = skeptic_round(ctx, state, FakeSkeptic({"A": "challenged"}), FakeReviewer([{"A": "unreviewed"}]),
                        FakeAnalyst(), Tracer(), 3)
    assert state["A"]["status"] == "reviewed" and state["A"]["verdict"].decision == "accept"
    assert state["A"]["finding"].review_priority == "review_next"
    assert "could not be reviewed" in state["A"]["note"]
    assert [h["decision"] for h in state["A"]["history"]] == ["unreviewed"]
    assert out["challenge_not_reviewed"] == 1 and out["priority_changed"] == 0
