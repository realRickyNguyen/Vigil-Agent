"""Rule routing: settle the easy reactions in code so only ambiguous ones cost a model call.
Rule findings go to the Reviewer like any other; if the Reviewer rejects one, the Analyst's model re-classifies it."""
import re

from app.data.label import INDICATION, find_term
from app.schemas import Finding, Signal

# MedDRA terms about the product, its use or the reporting process rather than a clinical event.
# "INTENTIONAL" alone is not enough: INTENTIONAL SELF-INJURY and INTENTIONAL OVERDOSE are clinical events.
# The last line follows eval/LABELLING_RULES.md (not_meaningful): efficacy terms like "drug ineffective", a
# bare "drug interaction" with no named event, induced abortion and social-circumstance terms.
ADMINISTRATIVE = re.compile(
    r"\bPRODUCT\b|OFF LABEL|DRUG INEFFECTIVE|DOSE OMISSION|MEDICATION ERROR|WRONG |INAPPROPRIATE SCHEDULE|"
    r"INCORRECT (DOSE|ROUTE)|EXPIRED|NO ADVERSE EVENT|UNEVALUABLE|THERAPY (INTERRUPTED|CESSATION|CHANGE)|"
    r"INTENTIONAL PRODUCT|ACCIDENTAL EXPOSURE|EXPOSURE (VIA|DURING)|DEVICE |TREATMENT NONCOMPLIANCE|PRESCRIBED "
    r"(OVERDOSE|UNDERDOSE)|INSURANCE|DRUG ABUSE|CIRCUMSTANCE OR INFORMATION|"
    r"TREATMENT FAILURE|THERAPEUTIC RESPONSE|^DRUG INTERACTION$|^ABORTION INDUCED$|LOSS OF PERSONAL INDEPENDENCE")


def route(s: Signal, label: dict, evidence: list[str]) -> Finding | None:
    """A rule finding for this reaction, or None if it needs the model."""
    base = dict(reaction=s.reaction, a=s.a, prr=s.prr, evidence=evidence, decided_by="rule",
                review_priority="lower_priority")
    if ADMINISTRATIVE.search(s.reaction):
        return Finding(**base, label_coverage="not_assessed", context="non_clinical",
                       reasoning="Rule: administrative MedDRA term about product use or reporting, not a clinical event.",
                       next_check="None needed for safety review.")
    hit = find_term(s.reaction, label)
    if hit is None:
        return None
    section, term = hit
    if section == INDICATION:
        # A term also named outside the indications may be something the drug causes or worsens, as with anxiety
        # for sertraline (indicated for social anxiety disorder, with anxiety among its warnings), so the model
        # weighs both.
        if find_term(s.reaction, {k: v for k, v in label.items() if k != INDICATION}):
            return None
        return Finding(**base, label_coverage="not_assessed", context="treated_condition",
                       reasoning=f"Rule: the label's indications section names '{term}', the condition being treated.",
                       next_check="Compare with reports for other treatments of the same condition.")
    if section == "contraindications":
        # A contraindication names who should not take the drug, not something the drug causes (metformin is
        # contraindicated in diabetic ketoacidosis), so it does not settle label coverage.
        return None
    return Finding(**base, label_coverage="covered", context="clinical_event", label_section=section,
                   label_term=term, reasoning=f"Rule: the label's {section} section names '{term}'.",
                   next_check="Already labelled; review only if reporting is rising or more severe than described.")
