"""Rule routing: settle the easy reactions in code so only ambiguous ones cost a model call.
Rule findings go to the Judge like any other; if the Judge rejects one, the Hunter's model re-classifies it."""
import re

from app.data.label import INDICATION, find_term
from app.schemas import Finding, Signal

# MedDRA terms about the product, its use or the reporting process rather than a clinical event.
ADMINISTRATIVE = re.compile(
    r"\bPRODUCT\b|OFF LABEL|DRUG INEFFECTIVE|DOSE OMISSION|MEDICATION ERROR|WRONG |INAPPROPRIATE SCHEDULE|"
    r"INCORRECT (DOSE|ROUTE)|EXPIRED|NO ADVERSE EVENT|UNEVALUABLE|THERAPY (INTERRUPTED|CESSATION|CHANGE)|"
    r"INTENTIONAL|ACCIDENTAL EXPOSURE|EXPOSURE (VIA|DURING)|DEVICE |TREATMENT NONCOMPLIANCE|PRESCRIBED "
    r"(OVERDOSE|UNDERDOSE)|INSURANCE|DRUG ABUSE|CIRCUMSTANCE OR INFORMATION")


def route(s: Signal, label: dict, evidence: list[str]) -> Finding | None:
    """A rule finding for this reaction, or None if it needs the model."""
    base = dict(reaction=s.reaction, a=s.a, prr=s.prr, evidence=evidence, decided_by="rule")
    if ADMINISTRATIVE.search(s.reaction):
        return Finding(**base, classification="not_meaningful",
                       reasoning="Rule: administrative MedDRA term about product use or reporting, not a clinical event.")
    hit = find_term(s.reaction, label)
    if hit is None:
        return None
    section, term = hit
    if section == INDICATION:
        return Finding(**base, classification="likely_indication_or_disease",
                       reasoning=f"Rule: the label's indications section names '{term}', the condition being treated.")
    return Finding(**base, classification="on_label", label_section=section, label_term=term,
                   reasoning=f"Rule: the label's {section} section names '{term}'.")
