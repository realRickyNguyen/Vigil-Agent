"""Offline tests for label quotes, excerpts and rule routing. Run: python -I -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.rules import route  # noqa: E402
from app.data.label import SENTENCE_CHARS, label_sentence, retrieve  # noqa: E402
from app.schemas import Signal  # noqa: E402

# Shaped like montelukast's paediatric list: one long sentence, with pneumonia far past 300 characters.
LIST = ("Adverse experiences occurring in patients 2 to 5 years of age with a frequency of at least 2% included "
        + ", ".join(f"event number {i}" for i in range(40)) + ", pneumonia, dermatitis and otitis media.")


def sig(name):
    return Signal(name, a=100, b=1000, c=500, d=100000, prr=5.0, chi2=300.0)


def test_a_quote_from_a_long_sentence_keeps_the_term():
    quote = label_sentence(LIST, "pneumonia")
    assert "pneumonia" in quote and len(quote) <= SENTENCE_CHARS + 6
    assert quote.startswith("...")                         # the cut is marked
    assert label_sentence("Headache was common.", "headache") == "headache was common."   # short ones unchanged


def test_an_excerpt_from_a_long_sentence_shows_the_reaction():
    hits = retrieve("PNEUMONIA", {"adverse_reactions": LIST})
    assert hits and "pneumonia" in hits[0][1].lower()


def test_a_term_named_in_the_indications_and_a_warning_goes_to_the_model():
    label = {"indications_and_usage": "Sertraline is indicated for social anxiety disorder.",
             "warnings_and_cautions": "Anxiety, agitation, panic attacks and insomnia have been reported."}
    assert route(sig("ANXIETY"), label, ["q-1"]) is None
    treated = route(sig("ANXIETY"), {"indications_and_usage": label["indications_and_usage"]}, ["q-1"])
    assert treated.context == "treated_condition"           # indications only: still the treated condition


def test_a_contraindication_alone_does_not_settle_coverage():
    label = {"contraindications": "Contraindicated in acute or chronic metabolic acidosis, including diabetic "
                                  "ketoacidosis.",
             "boxed_warning": "WARNING: LACTIC ACIDOSIS can occur."}
    assert route(sig("DIABETIC KETOACIDOSIS"), label, ["q-1"]) is None
    assert route(sig("LACTIC ACIDOSIS"), label, ["q-1"]).label_coverage == "covered"


def test_labelling_rules_non_clinical_terms_are_routed():
    for term in ("TREATMENT FAILURE", "THERAPEUTIC RESPONSE DECREASED", "DRUG INTERACTION", "ABORTION INDUCED",
                 "LOSS OF PERSONAL INDEPENDENCE IN DAILY ACTIVITIES"):
        f = route(sig(term), {}, ["q-1"])
        assert f is not None and f.context == "non_clinical", term
    for term in ("SEROTONIN SYNDROME", "INTENTIONAL OVERDOSE", "DRUG INTERACTION POTENTIATION", "HYPERTENSION"):
        assert route(sig(term), {}, ["q-1"]) is None, term   # clinical events still go to the model


def test_dosing_and_handling_errors_are_routed_aside():
    # All in openFDA's top 999. The tirzepatide run of 24 Oct left the second and third to the model.
    for term in ("EXTRA DOSE ADMINISTERED", "ACCIDENTAL UNDERDOSE", "UNDERDOSE", "ACCIDENTAL OVERDOSE",
                 "DRUG ADMINISTRATION ERROR", "DRUG PRESCRIBING ERROR", "DRUG DISPENSING ERROR",
                 "INCORRECT DRUG ADMINISTRATION DURATION", "DRUG ADMINISTERED AT INAPPROPRIATE SITE", "NEEDLE ISSUE",
                 "SYRINGE ISSUE", "INTENTIONAL DRUG MISUSE"):
        f = route(sig(term), {}, ["q-1"])
        assert f is not None and f.context == "non_clinical", term
    # Clinical terms that share words with them stay with the model.
    for term in ("OVERDOSE", "INJECTION SITE PAIN", "INAPPROPRIATE ANTIDIURETIC HORMONE SECRETION"):
        assert route(sig(term), {}, ["q-1"]) is None, term


# Atorvastatin's chosen label (set_id 6600f22e, 20261015), the passages that matter here.
ATORVASTATIN = {
    "indications_and_usage": "To reduce the risk of: MI and stroke in adults with type 2 diabetes mellitus with "
                             "multiple risk factors for CHD but without clinically evident CHD.",
    "adverse_reactions": "Diabetes was reported as an adverse reaction in (6.1%) of subjects in the atorvastatin group.",
}


def test_a_population_in_the_indications_is_not_settled_as_the_treated_condition():
    # On 24 Oct the rule called atorvastatin TYPE 2 DIABETES MELLITUS the treated condition. The adverse reactions
    # name diabetes, so the model decides.
    assert route(sig("TYPE 2 DIABETES MELLITUS"), ATORVASTATIN, ["q-1"]) is None
    assert route(sig("DIABETES MELLITUS"), ATORVASTATIN, ["q-1"]) is None
    # A treated condition the safety sections never mention is still settled by rule.
    label = {"indications_and_usage": "Indicated to improve glycemic control in adults with type 2 diabetes mellitus.",
             "adverse_reactions": "Nausea and vomiting were common."}
    f = route(sig("TYPE 2 DIABETES MELLITUS"), label, ["q-1"])
    assert f is not None and f.context == "treated_condition"
