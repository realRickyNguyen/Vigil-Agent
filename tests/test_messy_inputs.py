"""Offline tests for messy drug names, such as a brand name, a misspelling, an unknown drug, a drug with no current
label, a combination product and odd spacing. Run: python -I -m pytest tests

openFDA answers a search that matches nothing with a 404, and Zetaris reports a failed openFDA call as "HTTP 400: REST
API call failed: " and the Java error. The fake below answers each statement by what it reads, with the no-match in
the form Java gives a 404, the URL alone (JAVA_404, recorded on 26 Oct for vigilamab and seven other names), unless
a test asks for the plain "response code: 404" form. Counts are made up unless marked otherwise."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.data.faers import (SPELLING_HINT, DataClerk, DrugNotFound, NoCurrentLabel, combination_summary,  # noqa: E402
                            drug_search, no_match, slug, validate_drug)
from app.schemas import QueryResult  # noqa: E402

# Recorded 26 Oct, cut short. Zetaris adds a second line naming the URL again, which no_match() ignores.
URL = "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22vigilamab%22%20OR"
JAVA_404 = f"HTTP 400: REST API call failed: {URL}\n  URL: GET {URL}"
JAVA_404_NAMED = f"HTTP 400: REST API call failed: java.io.FileNotFoundException: {URL}"
PLAIN_404 = f"HTTP 400: REST API call failed: Server returned HTTP response code: 404 for URL: {URL}"
OUTAGE = f"HTTP 400: REST API call failed: Server returned HTTP response code: 502 for URL: {URL}"
REPORTS = 4127  # made up
LABEL = {"adverse_reactions": ["Nausea was reported."], "effective_time": "20260101",
         "openfda": {"generic_name": ["SEMAGLUTIDE"], "product_type": ["HUMAN PRESCRIPTION DRUG"]}}  # made up


class FakeZ:
    """Zetaris over openFDA.
    - absent holds table names whose openFDA search matches nothing. fails_at says where that shows, as "create" (the
      REST table), "view" (a view over it) or "read" (only a SELECT or CACHE TABLE), and no_match_text how it reads.
    - fail holds text whose reads fail with an openFDA 5xx, and create_fail text whose REST tables fail to be created.
    - brand_rows are the openfda blocks a brand-name label search returns, and label the record a label read returns."""
    def __init__(self, absent=(), brand_rows=(), fails_at="create", no_match_text=JAVA_404, fail=None,
                 create_fail=None, label=LABEL):
        self.absent, self.brand_rows = tuple(absent), list(brand_rows)
        self.fails_at, self.text = fails_at, no_match_text
        self.fail, self.create_fail, self.label = fail, create_fail, label
        self.sql = []

    def missing(self, sql):
        return any(a in sql for a in self.absent)

    def ensure(self, sql, purpose):
        self.sql.append(sql)
        if "REST TABLE" in sql and self.create_fail and self.create_fail in sql:
            raise ZetarisError(OUTAGE)
        if self.missing(sql) and (self.fails_at == "create" and "REST TABLE" in sql
                                  or self.fails_at == "view" and "SCHEMASTORE VIEW" in sql):
            raise ZetarisError(self.text)
        return True

    def run(self, sql, purpose, agent="data_clerk", ddl=False):
        self.sql.append(sql)
        if self.fail and self.fail in sql:
            raise ZetarisError(OUTAGE)
        if self.missing(sql):
            raise ZetarisError(self.text)
        if "label_brand_" in sql:
            return QueryResult("q-b", sql, ["o"], [[json.dumps(r)] for r in self.brand_rows])
        if "AS drug_reports" in sql:
            return QueryResult("q-t", sql, ["drug_reports", "all_reports", "data_last_updated"],
                               [[str(REPORTS), "20000000", "2026-07-30"]])
        if "label_d2_" in sql and "LATERAL VIEW" in sql:
            return QueryResult("q-l", sql, ["label"], [[json.dumps(self.label)]])
        return QueryResult("q-x", sql, [], [])


def test_spaces_inside_a_name_become_one_and_bad_names_still_fail():
    assert validate_drug(" Metformin  Hydrochloride ") == "metformin hydrochloride"
    assert slug("metformin hydrochloride") == slug("metformin  hydrochloride")  # same tables as before
    for bad in ("", " ", "x", "met/formin", "a" * 50, "metformin; drop"):
        with pytest.raises(ValueError):
            validate_drug(bad)


def test_only_openfdas_no_match_counts_as_a_missing_drug():
    for text in (JAVA_404, JAVA_404_NAMED, PLAIN_404):
        assert no_match(ZetarisError(text))
    for text in (OUTAGE, "URLError: <urlopen error [WinError 10061] No connection could be made>",
                 "HTTP 400: Table or view not found"):
        assert not no_match(ZetarisError(text))
    assert not no_match(ValueError(JAVA_404))


@pytest.mark.parametrize("text", [JAVA_404, PLAIN_404])
@pytest.mark.parametrize("drug", ["vigilamab", "metfromin", "semaglutid"])
def test_an_unknown_or_misspelt_name_stops_at_registration_with_a_plain_message(drug, text):
    z = FakeZ(absent=(f"faers_d2_{slug(drug)}_", "label_brand_"), no_match_text=text)
    with pytest.raises(DrugNotFound) as e:
        DataClerk(z).register_drug(drug)
    msg = str(e.value)
    assert msg.startswith(f"No FAERS reports in openFDA name '{drug}' as a generic name or active substance")
    assert msg.endswith(SPELLING_HINT)
    # No guessed spelling. The hint is the same fixed example for every name.
    assert "'metformin'" not in msg and "'semaglutide'" not in msg
    # It stopped before the views, the caches and the evidence queries that would fail on the same search.
    assert not any("SCHEMASTORE VIEW" in s or "CACHE TABLE" in s for s in z.sql)
    assert not any(s.startswith("SELECT") and "faers_d2_" in s for s in z.sql)


@pytest.mark.parametrize("fails_at", ["view", "read"])
def test_a_no_match_that_shows_only_later_stops_the_same_way(fails_at):
    z = FakeZ(absent=("faers_d2_vigilamab_", "label_brand_"), fails_at=fails_at)
    with pytest.raises(DrugNotFound, match="No FAERS reports in openFDA name 'vigilamab'"):
        DataClerk(z).register_drug("vigilamab")


def test_a_brand_name_is_named_with_its_generic_from_openfdas_labels_and_not_swapped():
    # The search is a phrase search, so it can return other brands. Only a brand equal to the input counts.
    rows = [{"brand_name": ["Ozempic"], "generic_name": ["SEMAGLUTIDE"]},
            {"brand_name": ["OZEMPIC"], "generic_name": ["SEMAGLUTIDE"]},
            {"brand_name": ["Ozempic Pen Starter Kit"], "generic_name": ["SOMETHING ELSE"]}]
    z = FakeZ(absent=("faers_d2_ozempic_",), brand_rows=rows)
    clerk = DataClerk(z)
    assert clerk.brand_generics("ozempic") == ["SEMAGLUTIDE"]
    with pytest.raises(DrugNotFound) as e:
        clerk.register_drug("ozempic")
    msg = str(e.value)
    assert "openFDA's drug labels give 'ozempic' as a brand name of 'semaglutide'" in msg
    assert "doesn't swap a brand for its generic itself, so run it again as 'semaglutide'" in msg
    assert "something else" not in msg
    # Nothing was registered or searched under the generic, so the run never swapped the name.
    assert not any("semaglutide" in s for s in z.sql if "label_brand_" not in s)


def test_a_combination_brand_names_the_combination_as_a_name_vigil_accepts():
    rows = [{"brand_name": ["Janumet"], "generic_name": ["SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"]},
            {"brand_name": ["Janumet XR"], "generic_name": ["SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"]}]
    clerk = DataClerk(FakeZ(absent=("faers_d2_janumet_",), brand_rows=rows))
    with pytest.raises(DrugNotFound) as e:
        clerk.register_drug("janumet")
    assert "run it again as 'sitagliptin and metformin hydrochloride'" in str(e.value)
    assert validate_drug("sitagliptin and metformin hydrochloride")


def test_a_brand_whose_generic_vigil_cannot_take_is_named_but_not_offered_as_a_run():
    # openFDA writes some generics with commas, and this one is 54 characters (Biktarvy's, as openFDA writes it).
    rows = [{"brand_name": ["Biktarvy"], "generic_name": ["BICTEGRAVIR, EMTRICITABINE, AND TENOFOVIR ALAFENAMIDE"]}]
    clerk = DataClerk(FakeZ(absent=("faers_d2_biktarvy_",), brand_rows=rows))
    with pytest.raises(DrugNotFound) as e:
        clerk.register_drug("biktarvy")
    msg = str(e.value)
    assert "brand name of 'bictegravir, emtricitabine, and tenofovir alafenamide'" in msg
    assert "run it again" not in msg and "this drug can't be run by name yet" in msg
    # With one name it takes and one it doesn't, only the one it takes is offered as a run.
    rows.append({"brand_name": ["Biktarvy"], "generic_name": ["BICTEGRAVIR"]})
    msg = DataClerk(FakeZ(brand_rows=rows)).not_found_message("biktarvy")
    assert msg.endswith("so run it again as 'bictegravir'.")


def test_a_failed_brand_lookup_falls_back_to_the_spelling_hint():
    clerk = DataClerk(FakeZ(absent=("faers_d2_ozempic_",), fail="label_brand_"))
    assert clerk.brand_generics("ozempic") == []
    assert clerk.not_found_message("ozempic").endswith(SPELLING_HINT)


def test_an_openfda_outage_is_not_called_a_missing_drug():
    clerk = DataClerk(FakeZ(fail="faers_d2_metformin_total"))
    with pytest.raises(ZetarisError) as e:
        clerk.totals("metformin")
    assert not isinstance(e.value, DrugNotFound)
    for z in (FakeZ(fail="CACHE TABLE"), FakeZ(create_fail="faers_d2_metformin_total_raw")):
        with pytest.raises(ZetarisError) as e:
            DataClerk(z).register_drug("metformin")
        assert not isinstance(e.value, DrugNotFound)


@pytest.mark.parametrize("fails_at", ["create", "read"])
def test_no_label_under_the_name_is_recorded_not_raised_at_registration(fails_at):
    clerk = DataClerk(FakeZ(absent=("label_d2_rofecoxib_raw",), fails_at=fails_at))
    created = clerk.register_drug("rofecoxib")
    assert clerk.label_missing and clerk.label_error is None
    assert clerk.label("rofecoxib") == (None, {})
    if fails_at == "create":
        assert created["label_raw"] is None


def test_a_combination_input_names_no_partner_of_its_own_ingredients():
    # (field, product name, reports), made up.
    rows = [("generic_name", "SITAGLIPTIN AND METFORMIN HYDROCHLORIDE", 900),
            ("generic_name", "METFORMIN HYDROCHLORIDE", 5000), ("generic_name", "SITAGLIPTIN", 300)]
    combo = combination_summary(rows, "sitagliptin and metformin", 1000)
    assert combo["share"] == 0.0 and combo["partners"] == []
    # A single-ingredient drug is unchanged, and the combination is a partner product for it.
    single = combination_summary(rows, "metformin", 5900)
    assert single["share"] == round(900 / 5900, 3) and single["partners"] == ["SITAGLIPTIN"]
    # The search names the whole combination as one phrase in both fields.
    assert "sitagliptin%20and%20metformin" in drug_search("sitagliptin and metformin")


# A whole run, with the model replaced by one that fails the test if it is ever called.
class NoModel:
    def __init__(self, tracer):
        self.tracer = tracer

    def chat_json(self, *a, **kw):
        raise AssertionError("the model was called")


def run_settings(tmp_path):
    from app.config import Settings
    return Settings(zetaris_url="z", zetaris_key="k", zetaris_org="1", meterless_url="m", meterless_token="t",
                    meterless_app="vigil", analyst_model="a", reviewer_model="r", source_timeout=20,
                    model_timeout=90, model_stream=True, max_retries=0, reviewer_rounds=1, parallel=2,
                    run_budget=600, sample_mode=False, logs_dir=tmp_path, world_path=tmp_path / "world.json")


def run(tmp_path, monkeypatch, drug, z):
    from app.orchestration import pipeline
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: z)
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: NoModel(tracer))
    return pipeline.investigate({"drug": drug}, run_settings(tmp_path), pipeline.Tracer(tmp_path, echo=False))


def trace_kinds(tmp_path):
    return [json.loads(line)["event"] for p in tmp_path.glob("trace-*.jsonl")
            for line in p.read_text(encoding="utf-8").splitlines()]


def test_a_drug_with_reports_but_no_label_stops_before_any_model_call(tmp_path, monkeypatch):
    z = FakeZ(absent=("label_d2_rofecoxib_raw", "label_brand_"))
    with pytest.raises(NoCurrentLabel) as e:
        run(tmp_path, monkeypatch, "rofecoxib", z)
    msg = str(e.value)
    assert msg.startswith(f"openFDA has {REPORTS:,} adverse event reports naming 'rofecoxib' but no drug label under "
                          f"that generic name, so no reaction can be checked against a label.")
    assert "The run stopped before any model call." in msg and "withdrawn long ago" in msg
    kinds = trace_kinds(tmp_path)
    assert "no_current_label" in kinds and "drug_not_found" not in kinds
    # It stopped at registration, so the screen, seriousness, combination and scope queries never ran.
    assert not any("faers_q_" in s or "faers_reaction_totals" in s for s in z.sql)


def test_a_brand_that_matches_a_few_reports_but_no_label_names_its_generic(tmp_path, monkeypatch):
    # A brand name can still match a few reports through the active substance field, so it passes the totals.
    z = FakeZ(absent=("label_d2_ozempic_raw",),
              brand_rows=[{"brand_name": ["Ozempic"], "generic_name": ["SEMAGLUTIDE"]}])
    with pytest.raises(NoCurrentLabel, match="run it again as 'semaglutide'"):
        run(tmp_path, monkeypatch, "ozempic", z)


def test_a_label_with_none_of_the_sections_vigil_reads_stops_with_its_own_message(tmp_path, monkeypatch):
    z = FakeZ(label={"effective_time": "20260101", "set_id": "s", "openfda": LABEL["openfda"]})
    with pytest.raises(NoCurrentLabel) as e:
        run(tmp_path, monkeypatch, "semaglutide", z)
    assert "but the label Vigil picked for it has none of the sections Vigil reads" in str(e.value)
    assert "no drug label under that generic name" not in str(e.value)


def test_an_unknown_drug_stops_the_whole_run_before_any_model_call(tmp_path, monkeypatch):
    with pytest.raises(DrugNotFound, match="No FAERS reports in openFDA name 'vigilamab'"):
        run(tmp_path, monkeypatch, "vigilamab", FakeZ(absent=("faers_d2_vigilamab_", "label_brand_")))
    assert "drug_not_found" in trace_kinds(tmp_path)


def test_a_failed_label_query_stops_as_a_recoverable_zetaris_error(tmp_path, monkeypatch):
    from app.server import classify_error
    with pytest.raises(ZetarisError) as e:
        run(tmp_path, monkeypatch, "semaglutide", FakeZ(fail="label_d2_semaglutide_raw LATERAL"))
    assert "the label query for 'semaglutide' failed, so the run stopped before any model call" in str(e.value)
    assert classify_error(e.value) == ("ZetarisUnavailable", 502, True)


def test_the_api_passes_each_message_through_as_an_error(tmp_path, monkeypatch):
    # Ricky's app/server.py is unchanged. A DrugNotFound (NoCurrentLabel is one) is a 404 that keeps its message.
    from app.orchestration import pipeline
    from app.server import Runner, classify_error, parse_request
    assert classify_error(NoCurrentLabel("x")) == classify_error(DrugNotFound("x")) == ("DrugNotFound", 404, False)
    assert parse_request({"drug": " Metformin  Hydrochloride "})[1] == {"drug": " Metformin  Hydrochloride "}
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: FakeZ(absent=("label_d2_rofecoxib_raw",
                                                                                          "label_brand_")))
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: NoModel(tracer))
    status, out = Runner(run_settings(tmp_path), pipeline.investigate).run({"drug": "rofecoxib"})
    assert status == 404 and out["status"] == "error" and out["error"]["type"] == "DrugNotFound"
    assert out["error"]["message"].startswith("NoCurrentLabel: openFDA has 4,127 adverse event reports naming "
                                              "'rofecoxib'")
    assert out["error"]["recoverable"] is False
    assert len(out["error"]["message"]) < 500  # app/server.py cuts messages at 500 characters
