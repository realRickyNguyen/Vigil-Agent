"""Offline tests for the uncertainty shown beside each screened row, and the dossier's scope statement.
Run: python -I -m pytest tests

Counts marked "recorded" came from Zetaris on 25 Oct with signal_sql (read-only; openFDA data updated 2026-07-30).
The sotagliflozin rows are from the screen behind run 20261025T005413Z-bc34f3, where RENAL PAIN and MICTURITION
URGENCY (4 reports each) went to review next with reasoning such as "statistically significant reporting pattern
(chi2=38.0) based on 4 reports". Expected values are worked out by hand in the comments, then compared."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.analyst import CLASSIFY_SYSTEM, screen_table  # noqa: E402
from app.agents.reviewer import SYSTEM as REVIEW_SYSTEM, Reviewer  # noqa: E402
from app.data.faers import COUNT_LIMIT, DataClerk, scope_sql, scope_summary  # noqa: E402
from app.data.uncertainty import assess, expected, information_component, of, prr_interval  # noqa: E402
from app.orchestration.pipeline import NOT_YET_CHECKED, review_queue  # noqa: E402
from app.schemas import Finding, QueryResult, Signal, Verdict  # noqa: E402

N = 20682701  # recorded, all reports (the serious-flag sum), the same total in every row below
# Recorded rows, as reaction, a, b, c, d, PRR, chi2.
RENAL_PAIN = Signal("RENAL PAIN", a=4, b=540, c=10421, d=20671736, prr=14.59, chi2=38.0)
MICTURITION_URGENCY = Signal("MICTURITION URGENCY", a=4, b=540, c=11183, d=20670974, prr=13.6, chi2=34.9)
POLLAKIURIA = Signal("POLLAKIURIA", a=5, b=539, c=41090, d=20641067, prr=4.63, chi2=10.8)
MYOCARDIAL_INFARCTION = Signal("MYOCARDIAL INFARCTION", a=10, b=534, c=173507, d=20508650, prr=2.19, chi2=5.4)
NIGHTMARE = Signal("NIGHTMARE", a=2028, b=174676, c=32279, d=20473718, prr=7.29, chi2=10368.6)  # montelukast


def test_the_recorded_rows_add_up_to_the_same_total():
    for s in (RENAL_PAIN, MICTURITION_URGENCY, POLLAKIURIA, MYOCARDIAL_INFARCTION, NIGHTMARE):
        assert s.a + s.b + s.c + s.d == N


def test_a_thin_sotagliflozin_row_against_a_hand_calculation():
    # RENAL PAIN, 4 reports.
    # E = (a+b)(a+c)/N = 544 * 10425 / 20682701 = 5671200 / 20682701 = 0.27420
    # PRR = (4/544) / (10421/20682157) = 14.593
    # SE(ln PRR) = sqrt(1/4 - 1/544 + 1/10421 - 1/20682157) = sqrt(0.248258) = 0.498254, times 1.96 = 0.976578
    # 95% CI = exp(2.680551 -/+ 0.976578) = 5.496 to 38.75
    # IC = log2(4.5 / 0.77420) = log2(5.81245) = 2.53915
    # IC025 = 2.53915 - 3.3 / sqrt(4.5) - 2 / 4.5^1.5 = 2.53915 - 1.55564 - 0.20951 = 0.77400
    s = RENAL_PAIN
    assert expected(s.a, s.b, s.c, s.d) == pytest.approx(0.27420, abs=1e-4)
    lo, hi = prr_interval(s.a, s.b, s.c, s.d)
    assert (lo, hi) == (pytest.approx(5.496, abs=2e-3), pytest.approx(38.75, abs=0.01))
    ic, ic025 = information_component(s.a, s.b, s.c, s.d)
    assert (ic, ic025) == (pytest.approx(2.53915, abs=1e-4), pytest.approx(0.77400, abs=1e-4))
    # IC025 is above 0, so the row is thin only because it has fewer than 5 reports.
    assert of(s) == {"expected": 0.27, "prr_ci95": [5.5, 38.75], "ic": 2.54, "ic025": 0.77, "thin_evidence": True,
                     "thin_reasons": ["fewer than 5 reports"]}
    # MICTURITION URGENCY, 4 reports. E = 544 * 11187 / N = 0.29424, IC = log2(4.5 / 0.79424) = 2.50228,
    # IC025 = 2.50228 - 1.55564 - 0.20951 = 0.73713.
    u = of(MICTURITION_URGENCY)
    assert (u["expected"], u["ic025"], u["thin_reasons"]) == (0.29, 0.74, ["fewer than 5 reports"])


def test_ten_reports_can_still_be_thin_by_ic025():
    # MYOCARDIAL INFARCTION, 10 reports. E = 544 * 173517 / N = 4.56388
    # IC = log2(10.5 / 5.06388) = 1.05207, IC025 = 1.05207 - 3.3 / sqrt(10.5) - 2 / 10.5^1.5
    #    = 1.05207 - 1.01840 - 0.05878 = -0.02511
    # PRR 2.19119, SE = sqrt(1/10 - 1/544 + 1/173507 - 1/20682157) = 0.313317, CI = 1.186 to 4.049
    s = MYOCARDIAL_INFARCTION
    assert information_component(s.a, s.b, s.c, s.d)[1] == pytest.approx(-0.02511, abs=1e-4)
    assert prr_interval(s.a, s.b, s.c, s.d) == (pytest.approx(1.186, abs=2e-3), pytest.approx(4.049, abs=2e-3))
    assert of(s)["thin_evidence"] is True and of(s)["thin_reasons"] == ["IC025 at or below 0"]


def test_five_reports_with_ic025_above_zero_is_not_thin():
    # POLLAKIURIA. E = 544 * 41095 / N = 1.08089, IC = log2(5.5 / 1.58089) = 1.79889,
    # IC025 = 1.79889 - 3.3 / sqrt(5.5) - 2 / 5.5^1.5 = 1.79889 - 1.40712 - 0.15506 = 0.23671
    u = of(POLLAKIURIA)
    assert u["ic025"] == 0.24 and u["thin_evidence"] is False and u["thin_reasons"] == []


def test_a_high_volume_montelukast_row_against_a_hand_calculation():
    # NIGHTMARE, 2,028 reports. E = 176704 * 34307 / N = 6062184128 / 20682701 = 293.104
    # PRR = (2028/176704) / (32279/20505997) = 7.2910, SE = sqrt(1/2028 - 1/176704 + 1/32279 - 1/20505997)
    #     = 0.0227677, times 1.96 = 0.0446247, CI = exp(1.986639 -/+ 0.0446247) = 6.973 to 7.624
    # IC = log2(2028.5 / 293.604) = 2.78847, IC025 = 2.78847 - 3.3 / sqrt(2028.5) - 2 / 2028.5^1.5 = 2.71518
    s = NIGHTMARE
    assert expected(s.a, s.b, s.c, s.d) == pytest.approx(293.104, abs=1e-3)
    assert prr_interval(s.a, s.b, s.c, s.d) == (pytest.approx(6.973, abs=2e-3), pytest.approx(7.624, abs=2e-3))
    assert information_component(s.a, s.b, s.c, s.d) == (pytest.approx(2.78847, abs=1e-4),
                                                          pytest.approx(2.71518, abs=1e-4))
    assert of(s)["thin_evidence"] is False


def test_no_interval_without_other_reports_of_the_reaction():
    assert prr_interval(3, 100, 0, 1000) is None and assess(3, 100, 0, 1000)["prr_ci95"] is None


def test_the_ic025_approximation_stays_below_the_exact_gamma_percentile():
    # The paper's approximation errs in the second decimal, on the cautious side. Exact 2.5th percentiles of
    # Gamma(a + 0.5, E + 0.5) on the log2 scale were worked out separately, by bisection on the regularised
    # incomplete gamma function. For MYOCARDIAL INFARCTION the exact value is just above 0 (0.0219) and the
    # approximation just below (-0.0251), so its thin mark rests on the approximation.
    for s, exact in ((RENAL_PAIN, 0.8024), (MYOCARDIAL_INFARCTION, 0.0219), (NIGHTMARE, 2.7250)):
        approx = information_component(s.a, s.b, s.c, s.d)[1]
        assert 0 < exact - approx < 0.05


def test_the_screen_table_shows_the_uncertainty_and_marks_thin_rows():
    table = screen_table([NIGHTMARE, RENAL_PAIN], 5)
    lines = table.splitlines()
    assert lines[0] == "reaction | a (reports with drug) | PRR | chi2 | expected a | PRR 95% CI | IC025 | thin evidence"
    assert lines[1] == "NIGHTMARE | 2028 | 7.29 | 10368.6 | 293.1 | 6.97 to 7.62 | 2.72 | no"
    assert lines[2] == "RENAL PAIN | 4 | 14.59 | 38.0 | 0.27 | 5.5 to 38.75 | 0.77 | yes"
    assert "fewer than 5 reports, or IC025 at or below 0" in lines[3]
    # The order is the caller's (chi2 for the screen); the thin mark never reorders rows.
    assert [l.split(" | ")[0] for l in screen_table([RENAL_PAIN, NIGHTMARE], 5).splitlines()[1:3]] == \
        ["RENAL PAIN", "NIGHTMARE"]
    # The pick step's table keeps its serious and death shares after chi2.
    sev = {"RENAL PAIN": {"serious_share": 0.75, "death_share": 0.0}}
    assert "RENAL PAIN | 4 | 14.59 | 38.0 | 75% | 0% | 0.27 | 5.5 to 38.75 | 0.77 | yes" in screen_table([RENAL_PAIN], 5, sev)


def test_both_prompts_forbid_calling_a_thin_row_strong():
    for prompt in (CLASSIFY_SYSTEM, REVIEW_SYSTEM):
        assert "thin evidence" in prompt and "statistically significant, strong or robust" in prompt
        assert "chi2 as strength" in prompt
    assert "Reject reasoning that calls it statistically significant" in REVIEW_SYSTEM
    assert "Thin evidence alone is not a reason to reject" in REVIEW_SYSTEM


class Capture:
    def __init__(self):
        from types import SimpleNamespace
        self.tracer, self.prompts = SimpleNamespace(event=lambda *a, **k: None), []

    def chat_json(self, agent, model, messages, **kw):
        self.prompts.append(messages[-1]["content"])
        return {"verdicts": [], "missing": []}


class RecordedClerk:
    def recheck(self, drug, reactions, agent="reviewer"):
        rows = {s.reaction: s for s in (RENAL_PAIN, POLLAKIURIA)}
        return QueryResult("q-r", "", [], []), {r: rows[r] for r in reactions if r in rows}


def new_signal(s: Signal, reasoning="x") -> Finding:
    return Finding(reaction=s.reaction, a=s.a, prr=s.prr, label_coverage="not_found", context="clinical_event",
                   review_priority="review_next", reasoning=reasoning, next_check="y", evidence=["q-s"])


def test_the_reviewer_sees_each_findings_uncertainty_from_the_recheck():
    ctx = {"drug": "sotagliflozin", "label": {}, "label_qid": None, "evidence_ids": {"q-s"},
           "passing": [RENAL_PAIN, POLLAKIURIA], "screen_qid": "q-s"}
    llm = Capture()
    Reviewer(llm, "m", RecordedClerk(), parallel=1).review(ctx, [new_signal(RENAL_PAIN), new_signal(POLLAKIURIA)], set())
    findings = {}
    for p in llm.prompts:
        findings.update({f["reaction"]: f for f in json.loads(p.split("Analyst findings with code checks:\n")[1])})
    assert findings["RENAL PAIN"]["uncertainty"]["thin_evidence"] is True
    assert findings["RENAL PAIN"]["uncertainty"]["ic025"] == 0.77
    assert findings["POLLAKIURIA"]["uncertainty"]["thin_evidence"] is False


def test_the_dossier_item_carries_uncertainty_and_the_order_is_unchanged():
    # Made-up counts. The thin row has the higher chi2, so it stays first, because uncertainty is shown, never used
    # to rank.
    strong = Signal("STRONG ROW", a=900, b=100000, c=9000, d=20000000, prr=19.0, chi2=15000.0)
    thin = Signal("THIN ROW", a=4, b=1000, c=10, d=20000000, prr=7000.0, chi2=20000.0)
    state = {s.reaction: {"finding": new_signal(s), "verdict": Verdict(s.reaction, "accept", "ok"),
                          "status": "reviewed", "history": []} for s in (strong, thin)}
    queue = review_queue(state, [strong, thin], [], [])
    assert [q["reaction"] for q in queue] == ["THIN ROW", "STRONG ROW"]
    assert queue[0]["uncertainty"]["thin_evidence"] is True and queue[1]["uncertainty"]["thin_evidence"] is False
    assert queue[0]["review_priority"] == "review_next" and queue[0]["workflow_status"] == "reviewed"


def test_the_scope_query_takes_one_aggregate_per_list():
    sql = scope_sql("sotagliflozin")
    assert sql.count("COUNT(*)") == 2 and sql.count("MIN(reports)") == 2 and "CROSS JOIN" in sql
    assert "openfda.faers_d2_sotagliflozin_reactions" in sql and "openfda.faers_reaction_totals" in sql


def test_the_scope_statement_names_both_caps_and_whether_the_drugs_list_is_full():
    # Recorded 25 Oct. Sotagliflozin's own list has 317 reactions down to 1 report, montelukast's is full at 999 down
    # to 116 reports, and the all-drugs list is full at 999 down to 9,059. The screen kept 83 and 787 rows.
    sota = scope_summary("sotagliflozin", {"drug_terms": "317", "drug_cutoff": "1", "all_terms": "999",
                                           "all_cutoff": "9059"}, 83, "2026-07-30", "q-sc")
    assert sota["drug_list"] == {"reactions": 317, "smallest_count": 1, "full": False}
    assert sota["all_drugs_list"] == {"reactions": 999, "smallest_count": 9059, "full": True}
    text = sota["statement"]
    assert "among openFDA's 999 most-reported reactions for all drugs and among the 999 most-reported with " \
           "sotagliflozin, with at least 3 reports with sotagliflozin" in text
    assert "The sotagliflozin list is not full (317 reactions, the smallest with 1 report), so it holds every " \
           "reaction reported with sotagliflozin." in text
    assert "The all-drugs list is full (999 reactions, the smallest with 9,059 reports)" in text
    assert "83 reactions met all three conditions" in text and "whether or not it was the suspect drug" in text
    assert text.endswith("openFDA data last updated 2026-07-30.") and sota["query_id"] == "q-sc"
    monte = scope_summary("montelukast", {"drug_terms": 999, "drug_cutoff": 116, "all_terms": 999,
                                          "all_cutoff": 9059}, 787, "2026-07-30")
    assert monte["drug_list"]["full"] is True and monte["cap"] == COUNT_LIMIT
    assert "The montelukast list is full (999 reactions, the smallest with 116 reports), so reactions reported " \
           "fewer times with montelukast are not screened." in monte["statement"]
    failed = scope_summary("x", None, 0, "2026-07-30")
    assert failed["drug_list"]["full"] is None and "could not be counted this run" in failed["statement"]


def test_a_failed_scope_query_does_not_stop_the_run():
    from app.adapters.zetaris import ZetarisError

    class Broken:
        def run(self, sql, purpose, **kw):
            raise ZetarisError("HTTP 400")
    assert DataClerk(Broken()).scope("sotagliflozin") == (None, None)


def test_the_untested_factors_name_both_caps():
    assert any("all drugs" in x and "own 999" in x for x in NOT_YET_CHECKED)
