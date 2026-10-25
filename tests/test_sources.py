"""Offline tests for the report-source check on review-next items. Run: python -I -m pytest tests

Counts marked "recorded" were taken from openFDA with the app's drug search on 25 Oct (data updated 2026-07-30).
The first two are finding D in 03_Project_context/Vigil_Workflow_Review_24Oct.md. Other counts are made up and
say so."""
import sys
import time
from concurrent.futures import Future
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.reviewer import Reviewer  # noqa: E402
from app.data.faers import DataClerk, drug_search, phrase, REACTION_FIELD  # noqa: E402
from app.data.sources import assess_sources, check  # noqa: E402
from app.orchestration.pipeline import NOT_YET_CHECKED, review_queue, source_targets  # noqa: E402
from app.schemas import Finding, QueryResult, Signal, Verdict  # noqa: E402

# Recorded. Montelukast FULL BLOOD COUNT ABNORMAL by occurcountry, 1,754 reports, 1,561 with a country.
FBC_COUNTRY = {"CA": 1507, "US": 52, "DE": 1, "IN": 1}
# Recorded. Montelukast's own reports by country in openFDA's top 100 countries, 143,724 in all, with Canada at
# 18,364 (12.8%). The 10,368 reports from the other 95 countries are lumped together here.
MONTELUKAST_COUNTRY = {"US": 102927, "CA": 18364, "GB": 8470, "JP": 2671, "DE": 924, "other": 10368}
MONTELUKAST_REPORTER = {"5": 79713, "1": 39979, "3": 34804, "2": 11265, "4": 2089}  # recorded
# Recorded. Isotretinoin IRRITABLE BOWEL SYNDROME by primarysource.qualification, 2,025 reports, 1,995 say who.
IBS_REPORTER = {"4": 1865, "5": 61, "1": 43, "3": 24, "2": 2}
ISOTRETINOIN_REPORTER = {"1": 19669, "5": 16737, "3": 11025, "4": 5841, "2": 1088}  # recorded


def test_montelukast_full_blood_count_abnormal_is_flagged_for_one_country():
    ev = assess_sources(1754, FBC_COUNTRY, {"5": 600, "1": 700, "3": 400}, MONTELUKAST_COUNTRY,
                        MONTELUKAST_REPORTER, 176704)
    c = ev["country"]
    assert (c["top"], c["top_reports"], c["known"], c["share"], c["usual_share"]) == ("CA", 1507, 1561, 0.9654, 0.1278)
    assert ev["flags"]["one_country"] is True and ev["raised"] == ["one_country"]
    assert "97% of the 1,561 reports with a known country come from CA, against 13% of the drug's reports" in ev["summary"]
    assert "This is context only" in ev["summary"]


def test_isotretinoin_irritable_bowel_syndrome_is_lawyer_reported():
    # The country counts here are made up (isotretinoin is mostly American); the test is about who reported.
    ev = assess_sources(2025, {"US": 1990}, IBS_REPORTER, {"US": 48000, "CA": 900}, ISOTRETINOIN_REPORTER, 57004)
    r = ev["reporter"]
    assert (r["known"], r["lawyer_share"], r["health_professional_share"]) == (1995, 0.9348, 0.0346)
    assert ev["flags"] == {"one_country": False, "lawyer_reports": True, "few_health_professionals": True}
    assert r["usual"]["lawyer_share"] == 0.1075
    assert "93% came from lawyers (drug's usual 11%)" in ev["summary"]


def test_a_country_share_close_to_the_drugs_usual_share_is_not_flagged():
    # isotretinoin is 93% American, so a signal at 96% US is its usual mix
    ev = assess_sources(500, {"US": 480, "CA": 20}, None, {"US": 930, "CA": 70}, None, None)
    assert ev["country"]["share"] == 0.96 and ev["flags"]["one_country"] is False


def test_few_reports_or_few_known_reporters_make_the_checks_unknown():
    ev = assess_sources(100, {"CA": 8}, {"4": 30, "1": 10}, MONTELUKAST_COUNTRY, None, None)
    assert ev["flags"] == {"one_country": "unknown", "lawyer_reports": "unknown",
                           "few_health_professionals": "unknown"}
    assert ev["raised"] == [] and "only 40 of 100 reports say who reported" in ev["summary"]
    # With no usual mix (its query failed), the country flag can't be judged.
    assert assess_sources(100, {"CA": 90}, None, None, None, None)["flags"]["one_country"] == "unknown"


class SourceZetaris:
    """Answers the report-source queries with fixed counts, by which REST table the SQL reads."""
    def __init__(self, fields):
        self.fields, self.tables, self.sql = fields, {}, []

    def ensure(self, sql, purpose):
        name = sql.split()[4]
        self.tables[name] = sql
        return True

    def run(self, sql, purpose, **kw):
        self.sql.append(sql)
        table = next(n for n in self.tables if f"openfda_rest.{n} " in sql)
        rows = self.fields[next(f for f in self.fields if f in self.tables[table])]
        total = 1754 if "faers_d2_montelukast_reactions" in sql else 176704
        return QueryResult("q-" + table[-4:], sql, ["term", "reports", "total"], [[t, n, total] for t, n in rows.items()])


def test_report_sources_are_zetaris_rest_tables_with_the_apps_drug_search():
    z = SourceZetaris({"occurcountry.exact": FBC_COUNTRY, "primarysource.qualification": {"5": 900, "1": 500}})
    qids, out = DataClerk(z).report_sources("montelukast", "FULL BLOOD COUNT ABNORMAL")
    assert out["country"] == FBC_COUNTRY and out["reporter"] == {"5": 900, "1": 500} and out["reports"] == 1754
    assert len(qids) == 2
    tables = list(z.tables.values())
    search = f"{drug_search('montelukast')}+AND+{phrase(REACTION_FIELD, 'FULL BLOOD COUNT ABNORMAL')}"
    assert all("api.fda.gov/drug/event.json?search=" + search in t for t in tables)
    assert any("count=occurcountry.exact&limit=999" in t for t in tables)
    assert any("count=primarysource.qualification&limit=999" in t for t in tables)
    # The drug's usual mix uses the drug's search alone and its report total.
    _, usual = DataClerk(SourceZetaris({"occurcountry.exact": MONTELUKAST_COUNTRY,
                                        "primarysource.qualification": MONTELUKAST_REPORTER})).report_sources("montelukast")
    assert usual["reports"] == 176704 and usual["reporter"]["4"] == 2089


def test_a_failed_part_is_unknown_not_a_crash():
    from app.adapters.zetaris import ZetarisError

    class Failing(SourceZetaris):
        def run(self, sql, purpose, **kw):
            if any(f"openfda_rest.{n} " in sql and "qualification" in t for n, t in self.tables.items()):
                raise ZetarisError("HTTP 400: openFDA 404")
            return super().run(sql, purpose, **kw)
    z = Failing({"occurcountry.exact": FBC_COUNTRY})
    usual = Future()
    usual.set_result(([], {"country": MONTELUKAST_COUNTRY, "reporter": None, "reports": 176704}))
    ev = check(DataClerk(z), "montelukast", "FULL BLOOD COUNT ABNORMAL", usual)
    assert ev["flags"]["one_country"] is True and ev["flags"]["lawyer_reports"] == "unknown"
    assert ev["reaction"] == "FULL BLOOD COUNT ABNORMAL" and len(ev["query_ids"]) == 1


def finding(reaction, priority):
    return Finding(reaction=reaction, a=100, prr=5.0, label_coverage="not_found", context="clinical_event",
                   review_priority=priority, reasoning="x", next_check="y", evidence=["q-s"])


def test_only_review_next_items_are_checked_up_to_the_cap():
    fs = [finding("A", "review_next"), finding("B", "lower_priority"), finding("C", "review_next"),
          finding("D", "review_next")]
    assert source_targets(fs, {"A"}, cap=2) == ["C"]
    assert source_targets(fs, set(), cap=10) == ["A", "C", "D"]


class FakeTracer:
    def event(self, *a, **k):
        pass


class CaptureLLM:
    """Accepts every finding and keeps each prompt, in call order."""
    def __init__(self):
        self.tracer, self.prompts = FakeTracer(), []

    def chat_json(self, agent, model, messages, **kw):
        user = messages[-1]["content"]
        self.prompts.append(user)
        names = [r for r in ("A", "B") if f'"reaction": "{r}"' in user]
        return {"verdicts": [{"reaction": r, "decision": "accept", "reason": "ok"} for r in names], "missing": []}


class SignalClerk:
    def recheck(self, drug, reactions, agent="reviewer"):
        from types import SimpleNamespace
        return SimpleNamespace(query_id="q-r"), {r: Signal(r, a=100, b=1, c=1, d=1, prr=5.0, chi2=50) for r in reactions}


def review_ctx(sources):
    passing = [Signal(r, a=100, b=1, c=1, d=1, prr=5.0, chi2=50) for r in "AB"]
    return {"drug": "x", "passing": passing, "label": {}, "label_qid": "q-l", "screen_qid": "q-s", "evidence_ids": {"q-s"},
            "sources": sources}


def done(value):
    f = Future()
    f.set_result(value)
    return f


def test_the_reviewer_sees_the_report_sources_and_reviews_those_items_last():
    ev = {**assess_sources(1754, FBC_COUNTRY, None, MONTELUKAST_COUNTRY, None, None), "query_ids": ["q-c", "q-u"]}
    llm = CaptureLLM()
    fs = [finding("A", "review_next"), finding("B", "lower_priority")]
    verdicts, _, _ = Reviewer(llm, "m", SignalClerk(), parallel=1).review(review_ctx({"A": done(ev)}), fs, set())
    assert [v.decision for v in verdicts] == ["accept", "accept"]
    assert '"reaction": "B"' in llm.prompts[0] and '"reaction": "A"' in llm.prompts[1]
    assert '"report_sources"' in llm.prompts[1] and "come from CA" in llm.prompts[1]
    assert '"report_sources"' not in llm.prompts[0]


def test_the_reviewer_does_not_wait_long_for_an_unfinished_check(monkeypatch):
    monkeypatch.setattr(Reviewer, "source_wait", 0.01)
    llm, start = CaptureLLM(), time.monotonic()
    Reviewer(llm, "m", SignalClerk(), parallel=1).review(review_ctx({"A": Future()}), [finding("A", "review_next")], set())
    assert time.monotonic() - start < 2 and "not finished" in llm.prompts[0]


def test_the_dossier_item_carries_the_report_sources():
    f = finding("A", "review_next")
    ev = assess_sources(1754, FBC_COUNTRY, None, MONTELUKAST_COUNTRY, None, None)
    state = {"A": {"finding": f, "verdict": Verdict("A", "accept", "ok"), "status": "reviewed", "history": []}}
    queue = review_queue(state, [Signal("A", a=100, b=1, c=1, d=1, prr=5.0, chi2=50)], [], [], sources={"A": ev})
    assert queue[0]["report_sources"]["flags"]["one_country"] is True
    assert any("Reporter type" in x and "review-next" in x for x in NOT_YET_CHECKED)


class RunClerk:
    """A Data Clerk with fixed answers, for one whole run without Zetaris."""
    label_choice = {"rule": "test label"}
    label_missing, label_error = False, None  # the label below is found

    def __init__(self):
        self.sources_asked = []
        self.rows = [Signal("FULL BLOOD COUNT ABNORMAL", a=1754, b=174950, c=20000, d=19800000, prr=9.9, chi2=9000.0),
                     Signal("HEADACHE", a=900, b=175804, c=90000, d=19700000, prr=1.1, chi2=3.0),
                     Signal("COUGH", a=800, b=175904, c=10000, d=19800000, prr=9.0, chi2=6000.0)]

    def register_drug(self, drug):
        return {}

    def totals(self, drug):
        return {"drug_reports": 176704, "all_reports": 20000000, "data_last_updated": "2026-07-30", "query_id": "q-t"}

    def signals(self, drug):
        return QueryResult("q-s", "", [], []), self.rows

    def label(self, drug):
        return "q-l", {"adverse_reactions": "Cough was common.", "effective_time": "20260804"}

    def combination_products(self, drug, reports):
        return None, None

    def seriousness(self, drug):
        return None, {}

    def scope(self, drug):
        return QueryResult("q-sc", "", [], []), {"drug_terms": 999, "drug_cutoff": 116, "all_terms": 999,
                                                 "all_cutoff": 9059}

    def recheck(self, drug, reactions, agent="reviewer"):
        return QueryResult("q-r", "", [], []), {s.reaction: s for s in self.rows if s.reaction in reactions}

    def report_sources(self, drug, reaction=None):
        self.sources_asked.append(reaction)
        if reaction is None:
            return ["q-u"], {"country": MONTELUKAST_COUNTRY, "reporter": MONTELUKAST_REPORTER, "reports": 176704}
        return ["q-c"], {"country": FBC_COUNTRY, "reporter": {"5": 600, "1": 700, "3": 400}, "reports": 1754}

    def co_drugs(self, drug, reaction, limit=100):
        from app.adapters.zetaris import ZetarisError
        raise ZetarisError("not in this test")


class RunLLM:
    """Classifies every table row as review_next and accepts every finding; keeps the Reviewer's prompts."""
    def __init__(self, tracer):
        self.tracer, self.reviews = tracer, []

    def chat_json(self, agent, model, messages, **kw):
        user = messages[-1]["content"]
        if agent == "reviewer":
            self.reviews.append(user)
            names = [s.reaction for s in RunClerk().rows if f'"reaction": "{s.reaction}"' in user]
            return {"verdicts": [{"reaction": r, "decision": "accept", "reason": "ok"} for r in names], "missing": []}
        if "picked" in messages[0]["content"]:
            return {"picked": []}
        # A classify table row: reaction | a | PRR | chi2 | expected a | PRR 95% CI | IC025 | thin evidence
        rows = [l.split(" | ") for l in user.splitlines() if l.count(" | ") == 7 and not l.startswith("reaction")]
        return {"findings": [{"reaction": r[0], "a": int(r[1]), "prr": float(r[2]), "context": "clinical_event",
                              "label_coverage": "not_found", "review_priority": "review_next", "reasoning": "x",
                              "next_check": "y", "evidence": ["q-s"]} for r in rows], "summary": ""}


def test_a_whole_run_checks_report_sources_for_review_next_items_only(tmp_path, monkeypatch):
    from app.config import Settings
    from app.orchestration import pipeline
    clerk, llms = RunClerk(), []
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: clerk)
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: llms.append(RunLLM(tracer)) or llms[-1])
    settings = Settings(zetaris_url="z", zetaris_key="k", zetaris_org="1", meterless_url="m", meterless_token="t",
                        meterless_app="vigil", analyst_model="a", reviewer_model="r", source_timeout=20,
                        model_timeout=90, model_stream=True, max_retries=0, reviewer_rounds=1, parallel=2,
                        run_budget=600, sample_mode=False, logs_dir=tmp_path, world_path=tmp_path / "world.json")
    dossier = pipeline.investigate({"drug": "montelukast"}, settings, pipeline.Tracer(tmp_path, echo=False))
    by = {q["reaction"]: q for q in dossier["review_queue"]}
    fbc = by["FULL BLOOD COUNT ABNORMAL"]
    assert fbc["review_priority"] == "review_next" and fbc["report_sources"]["flags"]["one_country"] is True
    assert "report_sources" not in by["COUGH"]  # covered by rule, so not review next
    assert sorted(clerk.sources_asked, key=str) == ["FULL BLOOD COUNT ABNORMAL", None]
    assert dossier["counts"]["report_sources_checked"] == 1 and dossier["counts"]["report_sources_flagged"] == 1
    assert "come from CA" in next(p for p in llms[0].reviews if "FULL BLOOD COUNT ABNORMAL" in p)
    assert fbc["label_search"]["summary"].startswith("Not named in any section searched.")


def test_a_whole_run_states_its_scope_and_each_items_uncertainty(tmp_path, monkeypatch):
    from app.orchestration import pipeline
    llms = []
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: RunClerk())
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: llms.append(RunLLM(tracer)) or llms[-1])
    dossier = pipeline.investigate({"drug": "montelukast"}, run_settings(tmp_path), pipeline.Tracer(tmp_path, echo=False))
    scope = dossier["data"]["scope"]
    assert scope["drug_list"]["full"] is True and scope["query_id"] == "q-sc" and scope["screened"] == 3
    assert "The montelukast list is full (999 reactions, the smallest with 116 reports)" in scope["statement"]
    assert all("uncertainty" in q for q in dossier["review_queue"])
    assert dossier["counts"]["thin_evidence"] == 0  # every row here has hundreds of reports
    assert llms[0].reviews and all('"uncertainty"' in p for p in llms[0].reviews)
    # Every item has the manual review flag; here all were accepted with enough reports, so none needs it.
    assert all(q["manual_review"] == {"needed": False, "reasons": [], "triggers": []} for q in dossier["review_queue"])
    assert dossier["counts"]["manual_review"] == 0
    assert not any("manual_review" in p for p in llms[0].reviews)  # no agent sees it


def test_the_thresholds_are_exact_at_their_boundaries():
    # Exactly 30 points above the usual share is flagged (0.7 - 0.4 is not 0.2999...).
    assert assess_sources(10, {"US": 7, "CA": 3}, None, {"US": 40, "CA": 60}, None, None)["flags"]["one_country"] is True
    # Exactly 20% lawyers is flagged, 4,999 of 25,000 is not, and exactly 50% health professionals is not "few".
    assert assess_sources(10, None, {"4": 2, "1": 8}, None, None, None)["flags"]["lawyer_reports"] is True
    assert assess_sources(25000, None, {"4": 4999, "1": 20001}, None, None, None)["flags"]["lawyer_reports"] is False
    assert assess_sources(10, None, {"1": 5, "5": 5}, None, None, None)["flags"]["few_health_professionals"] is False
    # Under 10 reports that say who reported is unknown, even when they are all the item has.
    assert assess_sources(9, None, {"4": 9}, None, None, None)["flags"]["lawyer_reports"] == "unknown"


def test_report_source_terms_are_normalised_and_quotes_are_safe():
    z = SourceZetaris({"occurcountry.exact": {"CA": 12}, "primarysource.qualification": {"1.0": 5, 4: 7}})
    _, out = DataClerk(z).report_sources("montelukast", "CROHN'S DISEASE")
    assert out["reporter"] == {"1": 5, "4": 7}
    assert all("reaction = 'CROHN\\'S DISEASE'" in s for s in z.sql)
    assert all("CROHN%27S%20DISEASE" in t and "'" not in t.split("endpoint")[1].split("method")[0]
               for t in z.tables.values())


def test_collect_sources_records_unfinished_and_failed_checks():
    from app.orchestration.pipeline import collect_sources

    class Tracer:
        def __init__(self):
            self.events = []

        def event(self, agent, kind, **data):
            self.events.append((kind, data))
    failing = Future()
    failing.set_exception(RuntimeError("boom"))
    ok = done({**assess_sources(1754, FBC_COUNTRY, None, MONTELUKAST_COUNTRY, None, None), "query_ids": ["q-c"]})
    ctx, tracer, start = {"sources": {"A": ok, "B": Future(), "C": failing}, "evidence_ids": set()}, Tracer(), time.monotonic()
    out = collect_sources(ctx, tracer, 0.05)
    assert time.monotonic() - start < 2
    assert out["B"] == {"status": "not finished"} and out["C"]["status"].startswith("failed: boom")
    assert out["A"]["flags"]["one_country"] is True and ctx["evidence_ids"] == {"q-c"}
    assert [d["reaction"] for k, d in tracer.events if k == "degraded"] == ["B", "C"]


def test_one_review_waits_once_for_all_unfinished_checks(monkeypatch):
    monkeypatch.setattr(Reviewer, "source_wait", 0.3)
    llm, start = CaptureLLM(), time.monotonic()
    Reviewer(llm, "m", SignalClerk(), parallel=1).review(review_ctx({"A": Future(), "B": Future()}),
                                                         [finding("A", "review_next"), finding("B", "review_next")], set())
    assert time.monotonic() - start < 0.55  # two separate waits would take at least 0.6 s
    assert all("not finished" in p for p in llm.prompts)


def run_settings(tmp_path, **kw):
    from app.config import Settings
    return Settings(zetaris_url="z", zetaris_key="k", zetaris_org="1", meterless_url="m", meterless_token="t",
                    meterless_app="vigil", analyst_model="a", reviewer_model="r", source_timeout=20, model_timeout=90,
                    model_stream=True, max_retries=0, reviewer_rounds=1, parallel=2, run_budget=600, sample_mode=False,
                    logs_dir=tmp_path, world_path=tmp_path / "world.json", **kw)


def test_source_items_zero_makes_no_source_calls(tmp_path, monkeypatch):
    from app.orchestration import pipeline
    clerk = RunClerk()
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: clerk)
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: RunLLM(tracer))
    monkeypatch.setattr(pipeline, "SOURCE_ITEMS", 0)
    dossier = pipeline.investigate({"drug": "montelukast"}, run_settings(tmp_path),
                                   pipeline.Tracer(tmp_path, echo=False))
    assert clerk.sources_asked == [] and dossier["counts"]["report_sources_checked"] == 0


def test_a_run_that_stops_on_an_error_shuts_the_source_pool(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.adapters.meterless import MeterlessUnauthorized
    from app.orchestration import pipeline
    import pytest
    closed = []

    class SpyPool(ThreadPoolExecutor):
        def shutdown(self, wait=True, cancel_futures=False):
            closed.append(cancel_futures)
            super().shutdown(wait=wait, cancel_futures=cancel_futures)

    class BadTokenLLM(RunLLM):
        def chat_json(self, agent, model, messages, **kw):
            if agent == "reviewer":
                raise MeterlessUnauthorized("401")
            return super().chat_json(agent, model, messages, **kw)
    monkeypatch.setattr(pipeline, "ThreadPoolExecutor", SpyPool)
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: RunClerk())
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: BadTokenLLM(tracer))
    with pytest.raises(MeterlessUnauthorized):
        pipeline.investigate({"drug": "montelukast"}, run_settings(tmp_path), pipeline.Tracer(tmp_path, echo=False))
    assert True in closed  # the source pool, cancelling what is still queued
