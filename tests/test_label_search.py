"""Offline tests for the code search of every label section. Run: python -I -m pytest tests

The label text is cut from the labels the app chose on 25 Oct (openFDA, through Zetaris): sertraline set_id
7d598f1a (20260903), Ozempic 42bdd912 (20260730), metformin ER 05999192 (20260909). Each section keeps only the
passages these tests need, copied verbatim."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.reviewer import code_checks, failed  # noqa: E402
from app.agents.rules import route  # noqa: E402
from app.data.faers import LABEL_FIELDS, DataClerk  # noqa: E402
from app.data.label import (clinical_pharmacology_parts, excerpt_block, indication_parts,  # noqa: E402
                            leaflet_parts, search)
from app.orchestration.pipeline import review_queue  # noqa: E402
from app.schemas import Finding, QueryResult, Signal, Verdict  # noqa: E402

SERTRALINE = {
    "indications_and_usage": "1 INDICATIONS AND USAGE Sertraline hydrochloride tablets are indicated for the treatment "
                             "of the following [See Clinical Studies (14) ] : Major depressive disorder (MDD) "
                             "Obsessive-compulsive disorder (OCD) Panic disorder (PD) Posttraumatic stress disorder "
                             "(PTSD) Social anxiety disorder (SAD) Premenstrual dysphoric disorder (PMDD)",
    "warnings_and_cautions": "5.5 Discontinuation Syndrome Adverse reactions after discontinuation of serotonergic "
                             "antidepressants, particularly after abrupt discontinuation, include: nausea, sweating, "
                             "dysphoric mood, irritability, agitation, dizziness, sensory disturbances (e.g., "
                             "paresthesia, such as electric shock sensations), tremor, anxiety, confusion, headache, "
                             "lethargy, emotional lability, insomnia, hypomania, tinnitus, and seizures.",
    "spl_medguide": "Medication Guide Sertraline Hydrochloride Tablets, USP (SIR-trah-leen hye-droe-klor-ide)) What is "
                    "the most important information I should know about sertraline hydrochloride tablets? Sertraline "
                    "hydrochloride tablets and other antidepressant medicines may cause serious side effects. "
                    "⚬ acting on dangerous impulses ⚬ thoughts about suicide or dying ⚬ new or worse anxiety or panic "
                    "attacks ⚬ trouble sleeping ⚬ other unusual changes in behavior or mood What are sertraline "
                    "hydrochloride tablets? Sertraline hydrochloride tablets are a prescription medicine used to treat: "
                    "Major Depressive Disorder (MDD) Panic Disorder Social Anxiety Disorder Obsessive Compulsive "
                    "Disorder (OCD) Who should not take sertraline hydrochloride tablets? Do not take sertraline "
                    "hydrochloride tablets if you: take a monoamine oxidase inhibitor (MAOI).",
    "effective_time": "20260903",
}
OZEMPIC = {
    "adverse_reactions": "6 ADVERSE REACTIONS The following serious adverse reactions are described below or elsewhere "
                         "in the prescribing information: • Risk of Thyroid C-cell Tumors [see Warnings and Precautions "
                         "( 5.1 )] • Acute Pancreatitis [see Warnings and Precautions ( 5.2) ]",
    "spl_medguide": "• you have had a serious allergic reaction to semaglutide or any of the ingredients in OZEMPIC. See "
                    "the end of this Medication Guide for a complete list of ingredients in OZEMPIC. See “What are the "
                    "possible side effects of OZEMPIC?” for symptoms of a serious allergic reaction. Before using "
                    "OZEMPIC, tell your healthcare provider if you have any other medical conditions, including if you: "
                    "• have or have had problems with your pancreas.",
    "pharmacodynamics": "12.2 Pharmacodynamics Semaglutide lowers fasting and postprandial blood glucose and reduces "
                        "body weight. All pharmacodynamic evaluations were performed after 12 weeks of treatment "
                        "(including dose escalation) at steady state with semaglutide 1 mg.",
    "pharmacokinetics": "The exposure of semaglutide decreases with an increase in body weight.",
    "effective_time": "20260730",
}
METFORMIN = {
    "boxed_warning": "WARNING: LACTIC ACIDOSIS Postmarketing cases of metformin-associated lactic acidosis have resulted "
                     "in death, hypothermia, hypotension, and resistant bradyarrhythmias.",
    "contraindications": "4 CONTRAINDICATIONS Metformin hydrochloride extended-release tablets are contraindicated in "
                         "patients with: • Severe renal impairment (eGFR below 30 mL/min/1.73 m 2 ) [see Warnings and "
                         "Precautions (5.1) ]. • Hypersensitivity to metformin. • Acute or chronic metabolic acidosis, "
                         "including diabetic ketoacidosis, with or without coma.",
    "drug_interactions": "Carbonic Anhydrase Inhibitors Clinical Impact: Carbonic anhydrase inhibitors frequently cause "
                         "a decrease in serum bicarbonate and induce non-anion gap, hyperchloremic metabolic acidosis. "
                         "Concomitant use of these drugs with metformin hydrochloride extended-release tablets may "
                         "increase the risk for lactic acidosis.",
    "pharmacokinetics": "Cimetidine 400 mg 850 mg metformin 1.4 1.61 Carbonic anhydrase inhibitors may cause metabolic "
                        "acidosis [see Warnings and Precautions (5.1) and Drug Interactions (7.1) .]",
    "effective_time": "20260909",
}


def sig(name):
    return Signal(name, a=100, b=1000, c=500, d=100000, prr=5.0, chi2=300.0)


def claim(reaction, coverage, section=None, term=None):
    return Finding(reaction=reaction, a=100, prr=5.0, label_coverage=coverage, context="clinical_event",
                   review_priority="lower_priority", reasoning="x", evidence=["q-1"], label_section=section,
                   label_term=term)


def check(f, label):
    return failed(code_checks(f, sig(f.reaction), label, {"q-1"}))


def test_label_fields_add_patient_pharmacology_and_non_coverage_sections():
    for field in ("spl_medguide", "spl_patient_package_insert", "information_for_patients", "pharmacodynamics",
                  "mechanism_of_action", "drug_interactions", "pharmacokinetics"):
        assert field in LABEL_FIELDS
    assert LABEL_FIELDS[:7] == ("boxed_warning", "warnings_and_cautions", "warnings", "precautions",
                                "adverse_reactions", "contraindications", "indications_and_usage")


def test_sertraline_panic_attack_is_covered_by_the_medication_guide_only():
    # Patient text settles nothing by rule (its "most important information" also lists risk factors), so the model
    # decides. Code then accepts coverage cited from the Medication Guide and rejects "not found".
    assert route(sig("PANIC ATTACK"), SERTRALINE, ["q-1"]) is None
    f = claim("PANIC ATTACK", "covered", "spl_medguide", "panic attacks")
    assert check(f, SERTRALINE) == [] and "panic attacks" in f.label_quote
    assert any(m.startswith("not_named_in_label") for m in check(claim("PANIC ATTACK", "not_found"), SERTRALINE))
    s = search("PANIC ATTACK", SERTRALINE)
    assert [(h["section"], h["kind"]) for h in s["found"]] == [("spl_medguide", "effect")]
    assert "spl_medguide (side effects)" in s["summary"]


def test_only_the_side_effect_parts_of_a_medication_guide_count():
    effect, other = leaflet_parts(SERTRALINE["spl_medguide"])
    assert "panic attacks" in effect and "Panic Disorder" not in effect and "Panic Disorder" in other
    assert "monoamine oxidase" in other
    # MAOI use is named only under "Who should not take", so it is not coverage.
    assert any(m.startswith("term_in_label") for m in check(
        claim("MONOAMINE OXIDASE INHIBITOR", "covered", "spl_medguide", "monoamine oxidase inhibitor"), SERTRALINE))
    # A quoted heading is a cross-reference, so the text after it is still "Who should not use".
    effect, _ = leaflet_parts(OZEMPIC["spl_medguide"])
    assert effect == ""
    # Metformin's and isotretinoin's leaflets put a space inside the quote.
    effect, other = leaflet_parts("How should I take X? Check your blood sugar. See “ What are the possible side "
                                  "effects of X? ” Stay on your diet. What should I avoid while taking X? No alcohol.")
    assert effect == "" and "Stay on your diet" in other


def test_a_leaflet_risk_factor_is_not_settled_as_coverage_by_rule():
    # Metformin ER's leaflet, "What is the most important information": dehydration is a lactic acidosis risk factor.
    label = {"spl_patient_package_insert": "What is the most important information I should know about metformin "
                                           "hydrochloride extended-release tablets? You have a higher chance of getting "
                                           "lactic acidosis if you: • get dehydrated (lose a large amount of body "
                                           "fluids). Dehydration can also happen when you sweat a lot.",
             "warnings_and_cautions": "Lactic acidosis has occurred."}
    assert route(sig("DEHYDRATION"), label, ["q-1"]) is None


def test_semaglutide_weight_decreased_is_an_expected_effect_not_not_found():
    s = search("WEIGHT DECREASED", OZEMPIC)
    expected = [h for h in s["found"] if h["kind"] == "expected_effect"]
    assert [(h["section"], h["how"]) for h in expected] == [("pharmacodynamics", "change")]
    assert "reduces body weight" in expected[0]["quote"]
    assert 'Expected effect of the drug (pharmacodynamics' in s["summary"] and "reduces body weight" in s["summary"]
    assert s["named_in"] == ["pharmacodynamics"]
    assert any(m.startswith("not_named_in_label") for m in check(claim("WEIGHT DECREASED", "not_found"), OZEMPIC))
    # Pharmacology is never coverage, and the pharmacokinetic sentence about body weight is not an effect.
    bad = check(claim("WEIGHT DECREASED", "covered", "pharmacodynamics", "reduces body weight"), OZEMPIC)
    assert any(m.startswith("coverage_section") for m in bad)
    assert check(claim("WEIGHT DECREASED", "unclear"), OZEMPIC) == []
    assert route(sig("WEIGHT DECREASED"), OZEMPIC, ["q-1"]) is None
    # The opposite direction is not an expected effect.
    assert search("WEIGHT INCREASED", OZEMPIC)["named_in"] == []


def test_semaglutide_decreased_appetite_records_every_section_searched():
    s = search("DECREASED APPETITE", OZEMPIC)
    assert s["found"] == [] and s["named_in"] == []
    assert s["searched"] == ["adverse_reactions", "spl_medguide", "pharmacodynamics", "pharmacokinetics"]
    assert s["summary"] == ("Not named in any section searched. That is about the label only, not whether it is the "
                            "treated condition. Searched 4 sections: adverse_reactions, spl_medguide, pharmacodynamics, "
                            "pharmacokinetics.")
    ok = code_checks(claim("DECREASED APPETITE", "not_found"), sig("DECREASED APPETITE"), OZEMPIC, {"q-1"})
    assert ok["not_named_in_label"] == (True, "label text does not name 'decreased appetite'")


def test_metformin_metabolic_acidosis_is_named_only_where_it_never_counts():
    s = search("METABOLIC ACIDOSIS", METFORMIN)
    assert [h["section"] for h in s["found"]] == ["contraindications", "drug_interactions", "pharmacokinetics"]
    assert {h["kind"] for h in s["found"]} == {"not_coverage"} and s["named_in"] == []
    assert "Named only where it never counts as coverage" in s["summary"]
    assert route(sig("METABOLIC ACIDOSIS"), METFORMIN, ["q-1"]) is None
    for section in ("contraindications", "drug_interactions", "pharmacokinetics"):
        bad = check(claim("METABOLIC ACIDOSIS", "covered", section, "metabolic acidosis"), METFORMIN)
        assert any(m.startswith("coverage_section") for m in bad) and any(m.startswith("term_in_label") for m in bad)
    # With no section given, only effect text is searched, so the contraindication still does not count.
    assert any(m.startswith("term_in_label") for m in
               check(claim("METABOLIC ACIDOSIS", "covered", None, "metabolic acidosis"), METFORMIN))
    assert check(claim("METABOLIC ACIDOSIS", "not_found"), METFORMIN) == []
    lactic = route(sig("LACTIC ACIDOSIS"), METFORMIN, ["q-1"])
    assert lactic.label_section == "boxed_warning" and check(lactic, METFORMIN) == []


def test_sertraline_withdrawal_syndrome_is_covered_as_discontinuation_syndrome():
    f = route(sig("WITHDRAWAL SYNDROME"), SERTRALINE, ["q-1"])
    assert (f.label_coverage, f.label_section, f.label_term) == ("covered", "warnings_and_cautions",
                                                                  "discontinuation syndrome")
    assert check(f, SERTRALINE) == []
    assert any(m.startswith("not_named_in_label") for m in check(claim("WITHDRAWAL SYNDROME", "not_found"), SERTRALINE))
    # Only the same event: alcohol withdrawal and neonatal withdrawal are not antidepressant discontinuation.
    for other in ("ALCOHOL WITHDRAWAL SYNDROME", "DRUG WITHDRAWAL SYNDROME NEONATAL"):
        assert search(other, SERTRALINE)["found"] == [] and route(sig(other), SERTRALINE, ["q-1"]) is None


def test_a_limitation_of_use_is_neither_the_indication_nor_coverage():
    # Shaped like a canagliflozin label before its 2015 ketoacidosis warning.
    label = {"indications_and_usage": "1 INDICATIONS AND USAGE 1.1 Glycemic control. It is indicated as an adjunct "
                                      "to diet and exercise. Limitations of Use: Not for the treatment of type 1 "
                                      "diabetes mellitus or diabetic ketoacidosis. 1.2 Other uses. None.",
             "adverse_reactions": "Genital mycotic infections were common."}
    ind, lim = indication_parts(label["indications_and_usage"])
    assert "ketoacidosis" in lim and "ketoacidosis" not in ind and "1.2 Other uses" in ind
    assert route(sig("DIABETIC KETOACIDOSIS"), label, ["q-1"]) is None
    assert check(claim("DIABETIC KETOACIDOSIS", "not_found"), label) == []
    s = search("DIABETIC KETOACIDOSIS", label)
    assert s["named_in"] == [] and "indications_and_usage (Limitation of Use)" in s["summary"]
    # Without subsection numbers the passage ends where the next indication starts (Wegovy's layout), so a later
    # indication still counts as the treated condition.
    text = "Drug X is indicated for hypertension. Limitations of Use: not for children under 6. Drug X is also "            "indicated for angina."
    ind, lim = indication_parts(text)
    assert lim == "Limitations of Use: not for children under 6." and "angina" in ind
    assert route(sig("ANGINA"), {"indications_and_usage": text}, ["q-1"]).context == "treated_condition"
    ind, lim = indication_parts("Limitations of Use • X is not indicated for use in patients with type 1 diabetes "
                                "mellitus. X is a GLP-1 receptor agonist indicated as an adjunct to diet.")
    assert "type 1 diabetes" in lim and "adjunct to diet" in ind


def test_clinical_pharmacology_is_split_by_its_numbered_headings():
    text = ("12 CLINICAL PHARMACOLOGY 12.1 Mechanism of Action The drug lowers plasma glucose. 12.2 Pharmacodynamics "
            "It reduces body weight. 12.3 Pharmacokinetics Exposure rises with dose [see Clinical Pharmacology (12.3)]. "
            "12.5 Pharmacogenomics None.")
    out = clinical_pharmacology_parts(text)
    # A part is named by its title, and a volume such as "12.5 L" does not end it.
    odd = clinical_pharmacology_parts("12.2 Pharmacokinetics The volume is approximately 12.5 L. Half-life 7 days.")
    assert list(odd) == ["pharmacokinetics"] and odd["pharmacokinetics"].endswith("Half-life 7 days.")
    assert out["mechanism_of_action"].endswith("lowers plasma glucose.")
    assert out["pharmacodynamics"] == "12.2 Pharmacodynamics It reduces body weight."
    assert out["pharmacokinetics"].endswith("(12.3)].") and "Pharmacogenomics" not in out["pharmacokinetics"]


class LabelZetaris:
    def __init__(self, record):
        self.record = record

    def run(self, sql, purpose, **kw):
        return QueryResult("q-lab", sql, ["label"], [[json.dumps(self.record)]])


def test_data_clerk_keeps_the_new_sections_and_splits_clinical_pharmacology():
    record = {"openfda": {"generic_name": ["X"], "product_type": ["HUMAN PRESCRIPTION DRUG"]},
              "spl_medguide": ["What are the possible side effects of X? Headache."],
              "pharmacokinetics": ["Own pharmacokinetics field."],
              "clinical_pharmacology": ["12.1 Mechanism of Action Blocks Y. 12.3 Pharmacokinetics Ignored here."],
              "clinical_studies": ["Not fetched."], "effective_time": "20260101"}
    _, label = DataClerk(LabelZetaris(record)).label("x")
    assert label["spl_medguide"].startswith("What are the possible side effects")
    assert label["mechanism_of_action"] == "12.1 Mechanism of Action Blocks Y."
    assert label["pharmacokinetics"] == "Own pharmacokinetics field." and "clinical_studies" not in label


def test_the_prompt_says_what_was_searched_and_quotes_the_medication_guide():
    block = excerpt_block(["PANIC ATTACK", "DECREASED APPETITE"], {**SERTRALINE, **{"pharmacodynamics": "None."}},
                          "q-l")
    assert "Code searched 4 label sections for each reaction's name: indications_and_usage, warnings_and_cautions, " \
           "spl_medguide, pharmacodynamics." in block
    assert "Code search: Named in sections that can support coverage: spl_medguide (side effects)." in block
    assert "[spl_medguide] (side effects) " in block and "panic attacks" in block
    # A pharmacology sentence that only names the reaction is shown, so the model can judge what it says.
    pharm = excerpt_block(["ASTHMA"], {"mechanism_of_action": "Leukotrienes are linked to the pathophysiology of "
                                                              "asthma."}, "q-l")
    assert "[mechanism_of_action] (pharmacology, not coverage) leukotrienes are linked" in pharm
    assert "- DECREASED APPETITE: (no label sentence shares its words)\n  Code search: Not named in any section " \
           "searched." in block


def test_the_dossier_item_carries_the_label_search():
    f = claim("DECREASED APPETITE", "not_found")
    state = {f.reaction: {"finding": f, "verdict": Verdict(f.reaction, "accept", "ok"), "status": "reviewed",
                          "history": []}}
    queue = review_queue(state, [sig(f.reaction)], [{"reaction": "WEIGHT DECREASED", "why": "x"}], [], label=OZEMPIC)
    by = {q["reaction"]: q for q in queue}
    assert by["DECREASED APPETITE"]["label_search"]["summary"].startswith("Not named in any section searched.")
    assert "reduces body weight" in by["WEIGHT DECREASED"]["label_search"]["summary"]


def test_a_curated_synonym_names_the_reaction_before_the_expected_effect():
    # Ozempic's chosen label (25 Oct). The warning names hypoglycemia, and the pharmacology lowers blood glucose. On
    # 25 Oct the search line showed only the pharmacology, and the Analyst marked BLOOD GLUCOSE DECREASED unclear.
    label = {"warnings_and_cautions": "( 5.4 ) • Hypoglycemia: Concomitant use with an insulin secretagogue or insulin "
                                      "may increase the risk of hypoglycemia, including severe hypoglycemia.",
             "mechanism_of_action": "Semaglutide reduces blood glucose through a mechanism where it stimulates insulin "
                                    "secretion and lowers glucagon secretion, both in a glucose-dependent manner.",
             "pharmacokinetics": "Hepatic impairment did not change exposure."}
    s = search("BLOOD GLUCOSE DECREASED", label)
    assert [(h["section"], h["how"], h["match"]) for h in s["found"] if h["kind"] == "effect"] ==         [("warnings_and_cautions", "related", "hypoglycemia")]
    assert s["summary"].startswith('Named by a related term ("hypoglycemia") in sections that can support coverage: '
                                   'warnings_and_cautions. Also an expected effect of the drug (mechanism_of_action')
    assert "warnings_and_cautions" in s["named_in"]
    assert any(m.startswith("not_named_in_label") for m in check(claim("BLOOD GLUCOSE DECREASED", "not_found"), label))
    # A related term never settles coverage by rule, and the broad liver stems name nothing.
    assert route(sig("BLOOD GLUCOSE DECREASED"), label, ["q-1"]) is None
    assert search("TRANSAMINASES INCREASED", label)["found"] == []
    block = excerpt_block(["BLOOD GLUCOSE DECREASED"], label, "q-l")
    assert "Code search: Named by a related term" in block
