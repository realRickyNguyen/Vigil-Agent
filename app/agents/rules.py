"""Rule routing: settle the easy reactions in code so only ambiguous ones cost a model call.
Rule findings go to the Reviewer like any other; if the Reviewer rejects one, the Analyst's model re-classifies it."""
import re

from app.data.label import SAFETY, STOP, effect_text, find_term, norm, us, word_stems
from app.schemas import Finding, Signal

# MedDRA terms about the product, its use or the reporting process rather than a clinical event.
# "INTENTIONAL" alone is not enough: INTENTIONAL SELF-INJURY and INTENTIONAL OVERDOSE are clinical events.
# The last line follows eval/LABELLING_RULES.md (not_meaningful): efficacy terms like "drug ineffective", a
# bare "drug interaction" with no named event and induced abortion. Social-circumstance terms are in SOCIAL.
ADMINISTRATIVE = re.compile(
    r"\bPRODUCT\b|OFF LABEL|DRUG INEFFECTIVE|DOSE OMISSION|MEDICATION ERROR|WRONG |INAPPROPRIATE SCHEDULE|"
    r"INCORRECT (DOSE|ROUTE)|EXPIRED|NO ADVERSE EVENT|UNEVALUABLE|THERAPY (INTERRUPTED|CESSATION|CHANGE)|"
    r"INTENTIONAL PRODUCT|ACCIDENTAL EXPOSURE|EXPOSURE (VIA|DURING)|DEVICE |TREATMENT NONCOMPLIANCE|PRESCRIBED "
    r"(OVERDOSE|UNDERDOSE)|INSURANCE|DRUG ABUSE|CIRCUMSTANCE OR INFORMATION|"
    r"TREATMENT FAILURE|THERAPEUTIC RESPONSE|^DRUG INTERACTION$|^ABORTION INDUCED$|"
    # Dosing and handling errors the model had to settle on 24 Oct (tirzepatide EXTRA DOSE ADMINISTERED, ACCIDENTAL
    # UNDERDOSE), all in openFDA's top 999. OVERDOSE and INTENTIONAL OVERDOSE stay clinical.
    r"EXTRA DOSE|UNDERDOSE|ACCIDENTAL OVERDOSE|(DRUG|PRODUCT) (ADMINISTRATION|PRESCRIBING|DISPENSING|PREPARATION) "
    r"ERROR|INCORRECT (DRUG|PRODUCT) ADMINISTRATION|DRUG ADMINISTERED (AT|TO) |^(NEEDLE|SYRINGE) ISSUE$|"
    r"INTENTIONAL DRUG MISUSE")
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
    # Named means the MedDRA name or a phrase for the same event (label.NAMED_AS). The indications leave out their
    # Limitation of Use. Only the professional safety sections settle coverage here, because a patient leaflet's "most
    # important information" also lists risk factors (metformin's "get dehydrated"), so patient text can support
    # coverage only through the model, whose claim the Reviewer's code checks then test.
    indication = find_term(s.reaction, label, kinds=("indication",))
    safety = find_term(s.reaction, label, kinds=("effect",), only=SAFETY)
    # Named in both places, for example sertraline ANXIETY: the indications name social anxiety disorder
    # and the warnings list anxiety as an effect. Only the model can tell which applies.
    if indication and safety:
        return None
    # The indications can name a term as the population rather than the condition treated. Atorvastatin is for adults
    # "with type 2 diabetes mellitus", and its adverse reactions list diabetes. When a safety section uses the term's
    # head word, the model decides (on 24 Oct the rule settled atorvastatin TYPE 2 DIABETES MELLITUS, and the
    # Reviewer's late objection left it unresolved).
    if indication and head_word_in_safety(s.reaction, label):
        return None
    if indication:
        return Finding(**base, label_coverage="not_assessed", context="treated_condition",
                       reasoning=f"Rule: the label's indications section names '{indication[1]}', the condition "
                                 f"being treated.",
                       next_check="Compare with reports for other treatments of the same condition.")
    # A name found only in the contraindications is a condition the drug must not be used in, not an effect
    # the label attributes to it (metformin DIABETIC KETOACIDOSIS), so it goes to the model too. So does one found
    # only in a Limitation of Use, the drug interactions, the pharmacokinetics or the pharmacology.
    if safety is None:
        return None
    section, term = safety
    return Finding(**base, label_coverage="covered", context="clinical_event", label_section=section,
                   label_term=term, reasoning=f"Rule: the label's {section} section names '{term}'.",
                   next_check="Already labelled; review only if reporting is rising or more severe than described.")


# Words that don't name a condition by themselves, so a term's head word is its first word that isn't one of these.
NOT_HEAD = STOP | {"chronic", "acute", "disease", "mellitus"}


def head_word_in_safety(reaction: str, label: dict) -> str | None:
    """The label word that a safety section uses for the term's head word, such as "diabetes" for TYPE 2 DIABETES
    MELLITUS, or None."""
    heads = word_stems(reaction, NOT_HEAD)
    if not heads:
        return None
    text = us(norm(" ".join(effect_text(label, sec) for sec in SAFETY)))
    m = re.search(rf"\b{re.escape(heads[0])}[a-z]*", text)
    return m.group(0) if m else None
