"""Offline tests for label excerpts and the not-meaningful rule terms. Run: python -I -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.rules import route  # noqa: E402
from app.data.label import SENTENCE_CHARS, around, retrieve  # noqa: E402
from app.schemas import Signal  # noqa: E402

# Shaped like montelukast's paediatric list, one long sentence with pneumonia far past 300 characters.
LIST = ("Adverse experiences occurring in patients 2 to 5 years of age with a frequency of at least 2% included "
        + ", ".join(f"event number {i}" for i in range(40)) + ", pneumonia, dermatitis and otitis media.")


def sig(name):
    return Signal(name, a=100, b=1000, c=500, d=100000, prr=5.0, chi2=300.0)


def test_an_excerpt_from_a_long_sentence_shows_the_reaction():
    hits = retrieve("PNEUMONIA", {"adverse_reactions": LIST})
    assert hits and "pneumonia" in hits[0][1].lower() and len(hits[0][1]) <= SENTENCE_CHARS


def test_the_excerpt_centres_on_the_strongest_stem_not_the_first():
    # "blood" comes first, but the synonym "hypoglyc" is what earned this sentence its place.
    filler = ", ".join(f"finding number {i}" for i in range(30))
    label = {"warnings": f"Lactic acidosis presents with elevated blood lactate levels, {filler}, and hypoglycemia "
                         f"can occur with insulin."}
    hits = retrieve("BLOOD GLUCOSE DECREASED", label)
    assert hits and "hypoglycemia" in hits[0][1] and len(hits[0][1]) <= SENTENCE_CHARS


def test_a_short_sentence_is_kept_whole():
    assert around("Headache was common.", ["headach"]) == "Headache was common."


def test_labelling_rules_non_clinical_terms_are_routed():
    for term in ("TREATMENT FAILURE", "THERAPEUTIC RESPONSE DECREASED", "DRUG INTERACTION"):
        f = route(sig(term), {}, ["q-1"])
        assert f is not None and f.context == "non_clinical", term
    for term in ("SEROTONIN SYNDROME", "INTENTIONAL OVERDOSE", "DRUG INTERACTION POTENTIATION", "HYPERTENSION"):
        assert route(sig(term), {}, ["q-1"]) is None, term   # clinical events still go to the model
