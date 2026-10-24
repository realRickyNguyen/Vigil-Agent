"""Offline unit tests: no Zetaris, no Nightshift. Run: python -I -m pytest tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.meterless import MeterlessError, extract_json  # noqa: E402
from app.agents.analyst import Analyst  # noqa: E402
from app.agents.rules import route  # noqa: E402
from app.data.label import excerpt_block, retrieve  # noqa: E402
from app.agents.reviewer import code_checks, failed  # noqa: E402
from app.data.faers import DataClerk, drug_search, signal_sql, slug, sql_str, validate_drug  # noqa: E402
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


def test_drug_search_uses_both_fields_fully_encoded():
    s = drug_search("insulin glargine")
    assert s == ("%28patient.drug.openfda.generic_name%3A%22insulin%20glargine%22%20OR%20"
                 "patient.drug.activesubstance.activesubstancename%3A%22insulin%20glargine%22%29")
    assert not any(ch in s for ch in "\"'() ")


class RecordingZetaris:
    def __init__(self):
        self.sql = []

    def ensure(self, sql, purpose):
        self.sql.append(sql)
        return True

    def run(self, sql, purpose, **kw):
        self.sql.append(sql)


def test_register_drug_uses_new_tables_and_combined_search():
    z = RecordingZetaris()
    DataClerk(z).register_drug("atorvastatin")
    event_tables = [s for s in z.sql if "event.json" in s]
    assert len(event_tables) == 2 and all(drug_search("atorvastatin") in s for s in event_tables)
    assert all("faers_d2_atorvastatin_" in s for s in event_tables)
    assert not any("faers_d_atorvastatin" in s for s in z.sql)  # old one-field tables are never reused
    label = next(s for s in z.sql if "label.json" in s)
    assert "search=openfda.generic_name:%22atorvastatin%22" in label  # label search uses one field
    assert "faers_d2_x_reactions" in signal_sql("x")


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


def test_chat_retries_when_nightshift_drops_the_connection(monkeypatch):
    from types import SimpleNamespace
    from app.adapters import meterless
    monkeypatch.setattr(meterless.time, "sleep", lambda s: None)
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=2), FakeTracer())
    replies = [ConnectionResetError(10054, "forcibly closed"), {"choices": [{"message": {"content": "ok"}}]}]

    def post(body):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(client, "_post", post)
    assert client.chat("analyst", "m", [{"role": "user", "content": "hi"}]) == "ok"
    assert [k for _, k, _ in client.tracer.events] == ["llm_retry", "llm_call"]


def test_trace_keeps_full_prompt_and_reply_but_not_the_token(monkeypatch):
    import json
    from types import SimpleNamespace
    from app.adapters import meterless
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="secret-token-xyz", max_retries=0,
                                                        meterless_url="http://x", meterless_app="a",
                                                        model_timeout=1), FakeTracer())
    messages = [{"role": "system", "content": "You are the Reviewer."}, {"role": "user", "content": "Drug: x"}]
    reply = "thinking...</think>{\"verdicts\": []}"
    monkeypatch.setattr(client, "_post", lambda body: {"model": "served", "choices": [
        {"message": {"content": reply, "reasoning_content": "hidden steps"}}]})
    client.chat("reviewer", "m", messages)
    (_, kind, data), = client.tracer.events
    assert kind == "llm_call" and data["messages"] == messages and data["reply"] == reply
    assert data["reasoning"] == "hidden steps" and data["served_by"] == "served"
    assert "secret-token-xyz" not in json.dumps(client.tracer.events)
    assert data["nightshift"] is None  # no inline receipt in this reply


def test_trace_records_nightshift_memory_and_scaffold_from_the_receipt():
    from app.adapters.meterless import nightshift_steps
    # Shape of a real Nightshift 1.2.1 reply on 23 Oct, trimmed to the fields we read.
    reply = {"choices": [], "meterless": {"receipt": {
        "receipt_id": "rcpt_req_1qp86xv3", "mode": "fast",
        "hmem": {"ids": ["mem_a", "mem_b", "mem_c"], "injected": 3, "strategy": "comprehensive"},
        "reasoning_scaffold": {"active": True, "variant": "with-plan"},
        "phases": [{"phase": "planning"}, {"phase": "code_patch"}],
        "egress": {"sent": {"context_sources": ["messages", "hmem:3 records"]}}}}}
    assert nightshift_steps(reply) == {"receipt_id": "rcpt_req_1qp86xv3", "hmem_injected": 3,
                                       "hmem_ids": ["mem_a", "mem_b", "mem_c"], "scaffold_active": True,
                                       "scaffold_variant": "with-plan", "phases": ["planning", "code_patch"],
                                       "context_sources": ["messages", "hmem:3 records"], "mode": "fast"}
    plain = {"meterless": {"receipt": {"receipt_id": "r", "hmem": None, "reasoning_scaffold": None, "phases": []}}}
    assert nightshift_steps(plain)["hmem_injected"] == 0 and not nightshift_steps(plain)["scaffold_active"]
    assert nightshift_steps({"choices": []}) is None


def analyst_ctx():
    passing = [Signal(n, a=10, b=1, c=1, d=1, prr=3.0, chi2=50 - i) for i, n in enumerate("ABCDEFGHIJ")]
    return {"drug": "x", "passing": passing, "label": {}, "label_qid": "q-l", "screen_qid": "q-s",
            "label_text": "", "screen_table": "", "screen_shown": 10, "screen_passing": 10,
            "totals": {"drug_reports": 1, "all_reports": 2, "data_last_updated": "d", "query_id": "q-t"}}


def test_selection_always_assesses_the_top_rows_and_survives_a_failed_pick():
    ctx = analyst_ctx()
    h = Analyst(FakeLLM(fail_all=True), "m", top=4, extra=2)
    assert h.pick(ctx) == []  # the model's extra picks are lost, nothing else
    assert any(k == "degraded" for _, k, _ in h.llm.tracer.events)
    h = Analyst(FakeLLM(), "m", top=4, extra=2)
    h.run(ctx)
    assert ctx["selection"]["always"] == list("ABCD") and ctx["picked"][:4] == list("ABCD")
    assert Analyst(FakeLLM(), "m", top=10, extra=2).pick(analyst_ctx()) == []  # no rows left to choose from


def test_classify_fails_fast_on_nightshift_deadline_only_for_batches(monkeypatch):
    import io
    import urllib.error
    from types import SimpleNamespace
    from app.adapters import meterless
    monkeypatch.setattr(meterless.time, "sleep", lambda s: None)
    calls = []

    def deadline(body):
        calls.append(1)
        raise urllib.error.HTTPError("u", 502, "bad gateway", {}, io.BytesIO(
            b'{"error":{"code":"provider_error","meterless_detail":"provider_deadline"}}'))
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=2), FakeTracer())
    monkeypatch.setattr(client, "_post", deadline)
    with pytest.raises(meterless.MeterlessDeadline):
        client.chat("analyst", "m", [{"role": "user", "content": "x"}], fail_fast=True)
    assert len(calls) == 1 and client.tracer.events[-1][1] == "llm_deadline"
    calls.clear()
    with pytest.raises(MeterlessError):
        client.chat("analyst", "m", [{"role": "user", "content": "x"}])  # a single item still gets its retries
    assert len(calls) == 3


def label_record(name, rx=True, date="20260101", boxed=True, set_id="s"):
    return {"set_id": set_id, "effective_time": date, **({"boxed_warning": ["B"]} if boxed else {}),
            "openfda": {"generic_name": [name], "brand_name": [name.title()],
                        "product_type": ["HUMAN PRESCRIPTION DRUG" if rx else "HUMAN OTC DRUG"]}}


def test_choose_label_prefers_single_ingredient_prescription_labels():
    from app.data.faers import choose_label
    combo = label_record("SITAGLIPTIN AND METFORMIN HYDROCHLORIDE", date="20260909", set_id="combo")
    otc = label_record("METFORMIN HYDROCHLORIDE", rx=False, date="20260908", set_id="otc")
    rx = label_record("METFORMIN HYDROCHLORIDE", date="20260901", set_id="rx")
    rec, why = choose_label([combo, otc, rx])
    assert rec["set_id"] == "rx" and why["rule"] == "single-ingredient prescription label" and why["candidates"] == 3
    assert choose_label([combo, otc])[0]["set_id"] == "otc"
    assert choose_label([combo])[1]["rule"] == "newest label"


def test_combination_summary_counts_products_that_contain_the_drug():
    from app.data.faers import combination_summary
    rows = [("generic_name", "ACETAMINOPHEN", 500), ("generic_name", "OXYCODONE AND ACETAMINOPHEN", 300),
            ("generic_name", "HYDROCODONE BITARTRATE AND ACETAMINOPHEN", 150), ("generic_name", "IBUPROFEN", 400),
            ("activesubstancename", "OXYCODONE HYDROCHLORIDE\\ACETAMINOPHEN", 200)]
    c = combination_summary(rows, "acetaminophen", 1000)
    assert c["reports"] == 450 and c["share"] == 0.45 and c["field"] == "generic_name"
    assert c["top_products"][0] == {"name": "OXYCODONE AND ACETAMINOPHEN", "reports": 300}
    assert c["partners"] == ["OXYCODONE", "HYDROCODONE BITARTRATE"]
    assert combination_summary([("generic_name", "ATORVASTATIN CALCIUM", 10)], "atorvastatin", 10)["share"] == 0.0


def test_register_drug_fetches_the_newest_labels():
    z = RecordingZetaris()
    DataClerk(z).register_drug("montelukast")
    label = next(s for s in z.sql if "label.json" in s)
    assert "label_d2_montelukast_raw" in label and "sort=effective_time:desc&limit=10" in label


def test_classify_splits_failed_batch_and_reports_unclassified():
    ctx = analyst_ctx()
    h = Analyst(FakeLLM(fail_on={"B |"}), "m")
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


def test_rules_send_social_terms_aside():
    sig = lambda r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    f = route(sig("LOSS OF PERSONAL INDEPENDENCE IN DAILY ACTIVITIES"), MONTELUKAST_LIKE, ["q"])
    assert (f.classification, f.review_priority) == ("not_meaningful", "lower_priority")
    assert route(sig("DISABILITY"), MONTELUKAST_LIKE, ["q"]).context == "non_clinical"
    assert route(sig("LEARNING DISABILITY"), MONTELUKAST_LIKE, ["q"]) is None  # a clinical term


def test_rules_leave_indication_plus_warning_to_the_model():
    # sertraline: the indications name social anxiety disorder, the warnings list anxiety as an effect
    label = {"indications_and_usage": "Sertraline is indicated for panic disorder and social anxiety disorder.",
             "warnings_and_cautions": "Symptoms include anxiety, agitation, panic attacks and insomnia."}
    assert route(Signal("ANXIETY", a=10, b=1, c=1, d=1, prr=3.0, chi2=50), label, ["q"]) is None


def test_rules_do_not_count_a_contraindication_as_coverage():
    # metformin names diabetic ketoacidosis only as a condition it must not be used in
    label = {"indications_and_usage": "Metformin is indicated to improve glycemic control in type 2 diabetes.",
             "contraindications": "Acute or chronic metabolic acidosis, including diabetic ketoacidosis.",
             "warnings_and_cautions": "Lactic acidosis has occurred."}
    sig = lambda r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    assert route(sig("DIABETIC KETOACIDOSIS"), label, ["q"]) is None
    assert route(sig("LACTIC ACIDOSIS"), label, ["q"]).label_section == "warnings_and_cautions"


def test_analyst_prompt_checks_coverage_for_treated_conditions():
    from app.agents.analyst import CLASSIFY_SYSTEM
    assert "treated condition and the label does not say the drug may cause or worsen it" in CLASSIFY_SYSTEM
    assert "only in the contraindications" in CLASSIFY_SYSTEM
    f = Finding(reaction="BLOOD GLUCOSE DECREASED", a=10, prr=3.0, label_coverage="covered",
                context="treated_condition", review_priority="lower_priority", reasoning="hypoglycemia warning")
    assert f.classification == "on_label"


def test_rule_finding_passes_reviewer_code_checks():
    cough = route(Signal("COUGH", a=10, b=1, c=1, d=1, prr=3.0, chi2=50), MONTELUKAST_LIKE, ["q-1"])
    fresh = Signal("COUGH", a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    assert failed(code_checks(cough, fresh, MONTELUKAST_LIKE, {"q-1"})) == []
    assert "cough" in cough.label_quote


def test_rejected_rule_finding_goes_to_the_model():
    ctx = analyst_ctx()
    ctx["label"] = {"adverse_reactions": "Reactions included A and B."}
    h = Analyst(FakeLLM(), "m")
    routed, _ = h.classify(ctx, ["A"])
    assert routed[0].decided_by == "rule"
    revised, _ = h.classify(ctx, ["A"], {"rejected": [{"reaction": "A", "reason": "x"}], "missing": []})
    assert revised[0].decided_by == "analyst"


def test_checks_new_signal_must_pass_screen():
    weak = Signal("RASH", a=2, b=1, c=1, d=1, prr=1.5, chi2=1.0)
    f = finding(reaction="RASH", a=2, prr=1.5, **NEW)
    assert any(m.startswith("passes_screen") for m in failed(code_checks(f, weak, LABEL, {"q-1"})))


DKA_LABEL = {"indications_and_usage": "Metformin is indicated to improve glycemic control in type 2 diabetes.",
             "contraindications": "Acute or chronic metabolic acidosis, including diabetic ketoacidosis.",
             "warnings_and_cautions": "Lactic acidosis has occurred. Hypoglycemia can occur with insulin.",
             "effective_time": "20260909"}


def test_not_found_is_allowed_for_a_contraindication_only_name():
    sig = Signal("DIABETIC KETOACIDOSIS", a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    f = Finding(reaction=sig.reaction, a=10, prr=3.0, label_coverage="not_found", context="clinical_event",
                review_priority="lower_priority", reasoning="x", evidence=["q-1"])
    assert failed(code_checks(f, sig, DKA_LABEL, {"q-1"})) == []
    lactic = Finding(reaction="LACTIC ACIDOSIS", a=10, prr=3.0, label_coverage="not_found", context="clinical_event",
                     review_priority="lower_priority", reasoning="x", evidence=["q-1"])
    assert any(m.startswith("not_named_in_label") for m in
               failed(code_checks(lactic, Signal("LACTIC ACIDOSIS", 10, 1, 1, 1, 3.0, 50), DKA_LABEL, {"q-1"})))


class OneVerdictLLM:
    """A Reviewer reply that judges only the first finding of the batch."""
    def __init__(self, reply):
        self.tracer, self.reply = FakeTracer(), reply

    def chat_json(self, agent, model, messages, **kw):
        return self.reply


class SignalClerk:
    def recheck(self, drug, reactions, agent="reviewer"):
        from types import SimpleNamespace
        return SimpleNamespace(query_id="q-r"), {r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in reactions}


def test_recheck_is_one_query_for_all_findings():
    sql = signal_sql("metformin", min_a=1, reactions=["DIARRHOEA", "CROHN'S DISEASE"])
    assert "dr.reaction IN ('DIARRHOEA', 'CROHN\\'S DISEASE')" in sql and "dr.reports >= 1" in sql


def test_reviewer_marks_a_finding_left_out_of_its_reply_unreviewed():
    from app.agents.reviewer import Reviewer
    ctx = {**analyst_ctx(), "evidence_ids": {"q-s"}}
    fs = [Finding(reaction=r, a=10, prr=3.0, label_coverage="not_found", context="clinical_event",
                  review_priority="review_next", reasoning="x", next_check="y", evidence=["q-s"]) for r in "AB"]
    llm = OneVerdictLLM({"verdicts": [{"reaction": "A", "decision": "accept", "reason": "ok"},
                                      {"reaction": "B", "decision": "maybe"}]})
    verdicts, _, _ = Reviewer(llm, "m", SignalClerk(), parallel=1).review(ctx, fs, set())
    assert [(v.reaction, v.decision) for v in verdicts] == [("A", "accept"), ("B", "unreviewed")]
    assert "no valid verdict" in verdicts[1].reason


class OmittingLLM(FakeLLM):
    """Leaves `omit` out of any reply that also names another reaction."""
    def __init__(self, omit):
        super().__init__()
        self.omit = omit

    def chat_json(self, agent, model, messages, **kw):
        out = super().chat_json(agent, model, messages, **kw)
        if len(out["findings"]) > 1:
            out["findings"] = [f for f in out["findings"] if f["reaction"] != self.omit]
        return out


def test_analyst_retries_a_reaction_left_out_of_the_reply():
    ctx = analyst_ctx()
    findings, _ = Analyst(OmittingLLM("B"), "m").classify(ctx, ["A", "B", "C"])
    assert sorted(f.reaction for f in findings) == ["A", "B", "C"] and not ctx.get("unclassified")


def test_analyst_reports_a_reaction_the_model_never_returns_as_failed():
    class NeverB(FakeLLM):
        def chat_json(self, agent, model, messages, **kw):
            out = super().chat_json(agent, model, messages, **kw)
            out["findings"] = [f for f in out["findings"] if f["reaction"] != "B"]
            return out
    ctx = analyst_ctx()
    h = Analyst(NeverB(), "m")
    findings, _ = h.classify(ctx, ["A", "B", "C"])
    assert sorted(f.reaction for f in findings) == ["A", "C"] and ctx["unclassified"] == ["B"]
    assert any(k == "omitted" for _, k, _ in h.llm.tracer.events)


def test_label_quote_always_contains_the_term():
    from app.data.label import label_sentence
    long = "Adverse reactions: " + "lactic acidosis and other events, " * 15 + "nausea, diarrhea and vomiting."
    q = label_sentence(long, "diarrhea")
    assert "diarrhea" in q and len(q) <= 300
    assert label_sentence("Short sentence with headache. Next one.", "headache") == "short sentence with headache."


def test_retrieval_finds_label_words_for_lab_terms():
    assert any("hypoglycemia" in s.lower() for _, s in retrieve("BLOOD GLUCOSE DECREASED", DKA_LABEL))
    assert not any("hypoglycemia" in s.lower() for _, s in retrieve("BLOOD GLUCOSE DECREASED", {}))
    # metformin's real label: "blood" and "hypoglyc" each hit 5 sentences, lactate sentences first
    lactate = " ".join(f"Lactic acidosis case {i} had elevated blood lactate levels." for i in range(5))
    hypo = " ".join(f"Hypoglycemia note {i} applies with insulin." for i in range(5))
    hits = retrieve("BLOOD GLUCOSE DECREASED", {"boxed_warning": lactate, "warnings_and_cautions": hypo})
    assert all("hypoglycemia" in s.lower() for _, s in hits)


def test_pregnancy_exposure_gets_a_pregnancy_check_not_dismissal():
    f = route(Signal("EXPOSURE DURING PREGNANCY", a=10, b=1, c=1, d=1, prr=3.0, chi2=50), {}, ["q"])
    assert f.context == "non_clinical" and "pregnancy outcomes" in f.next_check
    assert "None needed" not in f.next_check
    assert route(Signal("FOETAL EXPOSURE DURING PREGNANCY", 10, 1, 1, 1, 3.0, 50), {}, ["q"]).next_check == f.next_check
    assert route(Signal("PRODUCT USE ISSUE", 10, 1, 1, 1, 3.0, 50), {}, ["q"]).next_check == "None needed for safety review."


def test_prompts_forbid_comparing_reporting_with_incidence():
    from app.agents.analyst import CLASSIFY_SYSTEM
    from app.agents.reviewer import SYSTEM
    assert "no denominator" in CLASSIFY_SYSTEM and "no denominator" in SYSTEM


def test_classify_prompt_has_no_seriousness():
    class Capture(FakeLLM):
        def chat_json(self, agent, model, messages, **kw):
            self.last = messages[-1]["content"]
            return super().chat_json(agent, model, messages, **kw)
    ctx = {**analyst_ctx(), "seriousness": {r: {"serious_share": 0.9, "death_share": 0.07} for r in "ABC"}}
    llm = Capture()
    Analyst(llm, "m").classify(ctx, ["A"])
    assert "death" not in llm.last and "90%" not in llm.last


def test_seriousness_summary_and_table():
    from app.agents.analyst import screen_table
    from app.data.faers import seriousness_summary
    recs = [{"reaction": "A", "a": "200", "serious": "150", "death": "10", "serious_terms": "999", "death_terms": "40"},
            {"reaction": "B", "a": "50", "serious": None, "death": None, "serious_terms": "999", "death_terms": "40"}]
    sev = seriousness_summary(recs)
    assert sev["A"] == {"serious": 150, "death": 10, "serious_share": 0.75, "death_share": 0.05}
    # B is below the full serious list's cutoff (unknown) and absent from the short death list (none)
    assert sev["B"] == {"serious": None, "death": 0, "serious_share": None, "death_share": 0.0}
    table = screen_table([Signal("A", 200, 1, 1, 1, 3.0, 50), Signal("B", 50, 1, 1, 1, 2.5, 9)], 5, sev)
    assert "A | 200 | 3.0 | 50 | 75% | 5%" in table and "B | 50 | 2.5 | 9 | n/a | 0%" in table
    assert "whole report" in table.splitlines()[0]


def test_seriousness_query_counts_serious_and_fatal_reports():
    from app.data.faers import COUNT_LIMIT
    from app.schemas import QueryResult

    class Z(RecordingZetaris):
        def run(self, sql, purpose, **kw):
            self.sql.append(sql)
            return QueryResult("q-sev", sql, [], [])
    z = Z()
    res, sev = DataClerk(z).seriousness("metformin")
    assert res.query_id == "q-sev" and sev == {}
    rest = [s for s in z.sql if "CREATE LIGHTNING REST TABLE" in s]
    assert any("serious%3A1" in s or "serious:1" in s for s in rest)
    assert any("seriousnessdeath:1" in s for s in rest) and all(f"limit={COUNT_LIMIT}" in s for s in rest)
    assert "LEFT JOIN" in z.sql[-1] and "faers_d2_metformin_reactions" in z.sql[-1]


def test_progress_lines_name_the_agent_and_the_model():
    from app.tracing import progress_line
    call = {"agent": "reviewer", "event": "llm_call", "model": "m", "served_by": "nvidia/nemotron-3-ultra-550b-a55b",
            "ms": 23400, "attempt": 0}
    assert progress_line(call) == "Reviewer model call served by nvidia/nemotron-3-ultra-550b-a55b via Nightshift in 23 s"
    verdicts = {"agent": "reviewer", "event": "verdicts", "round": 1, "missing": [{"reaction": "X"}],
                "verdicts": [{"decision": "accept"}, {"decision": "accept"}, {"decision": "reject"}]}
    assert progress_line(verdicts) == ("Reviewer round 1: 2 accepted, 1 rejected, 0 unresolved, 0 not reviewed, "
                                       "1 missing named")
    assert progress_line({"agent": "analyst", "event": "picked", "reactions": []}) is None


def test_console_output_never_breaks_a_run(tmp_path, capsys):
    from app.tracing import Tracer
    t = Tracer(tmp_path)
    t.event("reviewer", "verdicts", round=1)  # missing fields: prints a fallback line, does not raise
    t.event("skeptic", "co_drug_check", reaction="R \u2265 2", outcome="no_challenge")
    out = capsys.readouterr().out
    assert "reviewer verdicts" in out and "co-reported drugs: no_challenge" in out
    assert len(t.path.read_text(encoding="utf-8").splitlines()) == 2
    Tracer(tmp_path, echo=False).event("reviewer", "verdicts", round=1)
    assert capsys.readouterr().out == ""


def test_a_single_reaction_that_fails_is_not_retried_again():
    class Counting(FakeLLM):
        calls = 0

        def chat_json(self, agent, model, messages, **kw):
            Counting.calls += 1
            return super().chat_json(agent, model, messages, **kw)
    ctx = analyst_ctx()
    h = Analyst(Counting(fail_on={"B |"}), "m")
    findings, _ = h.classify(ctx, ["A", "B"])
    assert [f.reaction for f in findings] == ["A"] and ctx["unclassified"] == ["B"]
    assert Counting.calls == 2  # one call each; the client's own retry is inside chat_json
    assert not any(k == "degraded" for _, k, _ in h.llm.tracer.events)


def test_extra_picks_are_classified_after_the_top_rows():
    class Picker(FakeLLM):
        def chat_json(self, agent, model, messages, **kw):
            if "choose up to" in messages[0]["content"]:
                return {"picked": [{"reaction": "F", "why": "x"}, {"reaction": "A", "why": "dup"}]}
            return super().chat_json(agent, model, messages, **kw)
    ctx = analyst_ctx()
    findings, _ = Analyst(Picker(), "m", top=3, extra=2).run(ctx)
    assert ctx["selection"]["chosen"] == ["F"] and sorted(f.reaction for f in findings) == ["A", "B", "C", "F"]


def test_coverage_must_fit_the_context():
    sig = Signal("HYPERGLYCAEMIA", a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
    f = lambda cov, ctx_: Finding(reaction=sig.reaction, a=10, prr=3.0, label_coverage=cov, context=ctx_,
                                  review_priority="lower_priority", reasoning="x", evidence=["q-1"])
    assert any(m.startswith("coverage_fits_context") for m in
               failed(code_checks(f("not_found", "treated_condition"), sig, {}, {"q-1"})))
    assert failed(code_checks(f("not_assessed", "treated_condition"), sig, {}, {"q-1"})) == []
    assert any(m.startswith("coverage_fits_context") for m in
               failed(code_checks(f("unclear", "non_clinical"), sig, {}, {"q-1"})))


def test_prompt_examples_avoid_the_evaluation_drugs():
    from app.agents.analyst import CLASSIFY_SYSTEM, PICK_SYSTEM
    from app.agents.reviewer import SYSTEM
    text = (CLASSIFY_SYSTEM + PICK_SYSTEM + SYSTEM).lower()
    for word in ("diabetes", "glucose", "antidepressant", "statin", "asthma", "acne", "metformin", "sertraline",
                 "montelukast", "atorvastatin", "isotretinoin"):
        assert word not in text, word
