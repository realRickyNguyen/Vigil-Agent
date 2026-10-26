"""Tests for the reporting-cluster marker on review-next items (app/data/sources.py, cluster_check): strong
one-country or lawyer clusters are marked "check the reporting cluster first", display only, never ranking.
Counts come from Bryan's recorded fixtures in tests/test_sources.py. No network. Run: python -I -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.sources import CLUSTER_NOTE, assess_sources, cluster_check  # noqa: E402
from test_sources import (FBC_COUNTRY, IBS_REPORTER, ISOTRETINOIN_REPORTER, MONTELUKAST_COUNTRY,  # noqa: E402
                          MONTELUKAST_REPORTER)


def ev(country=None, reporter=None, usual_country=None, usual_reporter=None, reports=1561, drug_reports=170000):
    return assess_sources(reports, country, reporter, usual_country, usual_reporter, drug_reports)


def test_montelukast_full_blood_count_abnormal_is_a_strong_country_cluster():
    # 1,507 of 1,561 reports from Canada, against about 13% for the drug.
    out = cluster_check(ev(FBC_COUNTRY, None, MONTELUKAST_COUNTRY))
    assert out["needed"] is True and out["note"] == CLUSTER_NOTE
    assert len(out["reasons"]) == 1 and "come from CA" in out["reasons"][0] and "re-filed" in out["reasons"][0]
    assert "priority is unchanged" in out["why"]


def test_isotretinoin_irritable_bowel_syndrome_is_a_strong_lawyer_cluster():
    out = cluster_check(ev(None, IBS_REPORTER, None, ISOTRETINOIN_REPORTER, reports=1995, drug_reports=48360))
    assert out["needed"] is True and "lawyers" in out["reasons"][0] and "litigation" in out["reasons"][0]


def test_a_flag_that_is_not_strong_is_not_marked():
    # 70% from one country, 50 points above usual: Bryan's flag is raised, but under the 80% strong share.
    flagged = ev({"US": 70, "CA": 30}, None, {"US": 20, "CA": 80}, reports=100)
    assert flagged["flags"]["one_country"] is True and cluster_check(flagged)["needed"] is False
    # 90% from one country but only 40 points above the drug's usual share.
    assert cluster_check(ev({"US": 90, "CA": 10}, None, {"US": 50, "CA": 50}, reports=100))["needed"] is False
    # 30% lawyers: flagged, not strong.
    lawyers = ev(None, {"4": 30, "1": 70}, reports=100)
    assert lawyers["flags"]["lawyer_reports"] is True and cluster_check(lawyers)["needed"] is False


def test_the_strong_thresholds_are_exact_at_their_boundaries():
    # Exactly 80% and exactly 50 points above usual is strong; one report fewer is not.
    assert cluster_check(ev({"US": 80, "CA": 20}, None, {"US": 30, "CA": 70}, reports=100))["needed"] is True
    assert cluster_check(ev({"US": 79, "CA": 21}, None, {"US": 29, "CA": 71}, reports=100))["needed"] is False
    assert cluster_check(ev({"US": 80, "CA": 20}, None, {"US": 31, "CA": 69}, reports=100))["needed"] is False
    # Exactly half of the reporters being lawyers is strong.
    assert cluster_check(ev(None, {"4": 50, "1": 50}, reports=100))["needed"] is True
    assert cluster_check(ev(None, {"4": 49, "1": 51}, reports=100))["needed"] is False


def test_unknown_or_missing_sources_are_never_marked():
    assert cluster_check(None) == {"needed": False, "reasons": [],
                                   "why": "report sources were not checked for this item"}
    assert cluster_check({"reaction": "X", "status": "failed"})["needed"] is False
    few = ev({"CA": 9}, None, MONTELUKAST_COUNTRY, reports=9)  # under 10 reports: the country check is unknown
    assert few["flags"]["one_country"] == "unknown" and cluster_check(few)["needed"] is False
    no_usual = ev(FBC_COUNTRY, None, None)  # the drug's usual mix failed
    assert cluster_check(no_usual)["needed"] is False
    unknown_reporters = ev(None, {"4": 9}, reports=1000)  # too few reports say who reported
    assert cluster_check(unknown_reporters)["needed"] is False
    assert cluster_check(ev(None, MONTELUKAST_REPORTER, reports=168000))["needed"] is False


def test_a_whole_run_marks_only_review_next_items_and_keeps_the_order(tmp_path, monkeypatch):
    from app.orchestration import pipeline
    from app.server import success_body, summary
    from test_sources import RunClerk, RunLLM, run_settings
    llms = []
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: RunClerk())
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: llms.append(RunLLM(tracer)) or llms[-1])
    settings = run_settings(tmp_path)
    dossier = pipeline.investigate({"drug": "montelukast"}, settings, pipeline.Tracer(tmp_path, echo=False))
    queue = dossier["review_queue"]
    by = {q["reaction"]: q for q in queue}
    fbc = by["FULL BLOOD COUNT ABNORMAL"]
    assert fbc["review_priority"] == "review_next" and fbc["reporting_cluster"]["needed"] is True
    assert all("reporting_cluster" not in q for q in queue if q.get("review_priority") != "review_next")
    assert dossier["counts"]["review_next_check_cluster_first"] == 1
    # Display only: the queue is in the order its own sort key gives, which does not read the marker.
    key = lambda q: (pipeline.PRIORITY_ORDER.get(q.get("review_priority"), 3),  # noqa: E731
                     pipeline.STATUS_ORDER.get(q["workflow_status"], 5), -(q.get("chi2") or 0))
    assert queue == sorted(queue, key=key)
    assert not any("reporting_cluster" in p or "check the reporting cluster" in p for p in llms[0].reviews)
    out = success_body(dossier, settings, 1.0)["output"]
    assert out["check_reporting_cluster_first"] == ["FULL BLOOD COUNT ABNORMAL"]
    assert "(1 of them to check for a reporting cluster first)" in summary(dossier)
