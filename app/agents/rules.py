"""Rule routing: settle the easy reactions in code so only ambiguous ones cost a model call.
Rule findings go to the Reviewer like any other; if the Reviewer rejects one, the Analyst's model re-classifies it."""
import re

from app.data.label import INDICATION, SAFETY, find_term
from app.schemas import Finding, Signal

# MedDRA terms about the product, its use or the reporting process rather than a clinical event.
# "INTENTIONAL" alone is not enough: INTENTIONAL SELF-INJURY and INTENTIONAL OVERDOSE are clinical events.
ADMINISTRATIVE = re.compile(
    r"\bPRODUCT\b|OFF LABEL|DRUG INEFFECTIVE|DOSE OMISSION|MEDICATION ERROR|WRONG |INAPPROPRIATE SCHEDULE|"
    r"INCORRECT (DOSE|ROUTE)|EXPIRED|NO ADVERSE EVENT|UNEVALUABLE|THERAPY (INTERRUPTED|CESSATION|CHANGE)|"
    r"INTENTIONAL PRODUCT|ACCIDENTAL EXPOSURE|EXPOSURE (VIA|DURING)|DEVICE |TREATMENT NONCOMPLIANCE|PRESCRIBED "
    r"(OVERDOSE|UNDERDOSE)|INSURANCE|DRUG ABUSE|CIRCUMSTANCE OR INFORMATION")
# MedDRA social-circumstance terms: consequences in a person's life, not the clinical event behind them.
# In the 23 Oct evaluation montelukast LOSS OF PERSONAL INDEPENDENCE IN DAILY ACTIVITIES went to review next twice.
SOCIAL = re.compile(
    r"LOSS OF PERSONAL INDEPENDENCE|IMPAIRED WORK ABILITY|LOSS OF EMPLOYMENT|ECONOMIC PROBLEM|"
    r"FINANCIAL (DIFFICULTY|PROBLEM)|^DISABILITY$|^BEDRIDDEN$|WHEELCHAIR USER|WALKING AID USER")


# Exposure in pregnancy or breastfeeding: not an adverse event itself, but not "nothing to review" either
# (isotretinoin has a pregnancy-prevention programme). Checked before ADMINISTRATIVE, which also matches them.
PREGNANCY_EXPOSURE = re.compile(r"EXPOSURE.*(PREGNANCY|BREAST MILK)|(FOETAL|FETAL|MATERNAL|PATERNAL) EXPOSURE")


def route(s: Signal, label: dict, evidence: list[str]) -> Finding | None:
    """A rule finding for this reaction, or None if it needs the model."""
    base = dict(reaction=s.reaction, a=s.a, prr=s.prr, evidence=evidence, decided_by="rule",
                review_priority="lower_priority")
    if PREGNANCY_EXPOSURE.search(s.reaction):
        return Finding(**base, label_coverage="not_assessed", context="non_clinical",
                       reasoning="Rule: exposure during pregnancy or breastfeeding, not an adverse event in itself; "
                                 "the outcomes reported with it decide whether it matters.",
                       next_check="Count pregnancy outcomes (abortion, congenital anomaly, foetal disorders) in the "
                                  "same reports, and check the label's pregnancy section and any pregnancy-prevention "
                                  "programme.")
    if ADMINISTRATIVE.search(s.reaction):
        return Finding(**base, label_coverage="not_assessed", context="non_clinical",
                       reasoning="Rule: administrative MedDRA term about product use or reporting, not a clinical event.",
                       next_check="None needed for safety review.")
    if SOCIAL.search(s.reaction):
        return Finding(**base, label_coverage="not_assessed", context="non_clinical",
                       reasoning="Rule: MedDRA social-circumstance term, a consequence in the person's life rather "
                                 "than a clinical event.",
                       next_check="Look at the clinical events named in the same reports.")
    indication = find_term(s.reaction, label, only=(INDICATION,))
    safety = find_term(s.reaction, label, only=SAFETY)
    # Named in both places, for example sertraline ANXIETY: the indications name social anxiety disorder
    # and the warnings list anxiety as an effect. Only the model can tell which applies.
    if indication and safety:
        return None
    if indication:
        return Finding(**base, label_coverage="not_assessed", context="treated_condition",
                       reasoning=f"Rule: the label's indications section names '{indication[1]}', the condition "
                                 f"being treated.",
                       next_check="Compare with reports for other treatments of the same condition.")
    # A name found only in the contraindications is a condition the drug must not be used in, not an effect
    # the label attributes to it (metformin DIABETIC KETOACIDOSIS), so it goes to the model too.
    if safety is None:
        return None
    section, term = safety
    return Finding(**base, label_coverage="covered", context="clinical_event", label_section=section,
                   label_term=term, reasoning=f"Rule: the label's {section} section names '{term}'.",
                   next_check="Already labelled; review only if reporting is rising or more severe than described.")
