"""Shapes passed between the Clerk, the agents and the dossier.

The decision contract keeps separate questions apart:
- label_coverage: does the current label already describe this reaction?
- context: is the term a clinical event, the treated condition, or not a clinical event at all?
- review_priority: should an analyst look at it next?
- workflow_status (set by the orchestrator): did the review finish, and how?
The older single category (`classification`) is derived from coverage and context, for the gold set."""
from dataclasses import dataclass, field, asdict

CLASSIFICATIONS = ("on_label", "possible_new_signal", "likely_indication_or_disease", "not_meaningful")
COVERAGE = ("covered", "not_found", "unclear", "not_assessed")
CONTEXT = ("clinical_event", "treated_condition", "non_clinical")
PRIORITY = ("review_next", "insufficient_evidence", "lower_priority")
# reviewed: the Judge accepted it. unresolved: the Judge and Hunter could not settle it, or the rounds ran out.
# not_reviewed: passed code checks but the Judge's model review failed. pending: named for review, never done.
# failed: the Hunter's model could not classify it.
STATUS = ("reviewed", "unresolved", "not_reviewed", "pending", "failed")

CAVEAT = ("FAERS reports show an association between a drug and a reported event, not that the drug caused it. "
          "Reports are voluntary, unverified and affected by reporting bias. This is not medical advice; "
          "openFDA asks that its data not be relied on for medical decisions.")


@dataclass
class QueryResult:
    query_id: str
    sql: str
    headers: list[str]
    rows: list[list]

    def records(self) -> list[dict]:
        return [dict(zip(self.headers, r)) for r in self.rows]


@dataclass
class Signal:
    reaction: str
    a: int
    b: int
    c: int
    d: int
    prr: float
    chi2: float


@dataclass
class Finding:
    reaction: str
    a: int
    prr: float
    label_coverage: str
    context: str
    review_priority: str
    reasoning: str                  # why this priority, in one sentence
    next_check: str = ""            # the concrete check that would settle or advance it
    evidence: list[str] = field(default_factory=list)
    label_section: str | None = None
    label_term: str | None = None   # phrase the Hunter says the label uses for this reaction
    label_quote: str | None = None  # sentence around label_term, extracted by code, never by the model
    decided_by: str = "hunter"      # "hunter" (model) or "rule" (app/agents/rules.py)

    @property
    def classification(self) -> str:
        """The single category used by the gold set, derived in the gold set's precedence order."""
        if self.context == "non_clinical":
            return "not_meaningful"
        if self.label_coverage == "covered":
            return "on_label"
        if self.context == "treated_condition":
            return "likely_indication_or_disease"
        return "possible_new_signal"

    def key(self) -> tuple:
        """What the Hunter claimed, for spotting a revision that returns to an already rejected claim."""
        return (self.label_coverage, self.context, self.review_priority)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        def pick(name, default):
            # Missing values get the cautious default; unknown values are kept so the Judge's checks reject them.
            return str(d.get(name) or "").strip() or default
        return cls(
            reaction=str(d.get("reaction", "")).strip(),
            a=int(d.get("a") or 0),
            prr=float(d.get("prr") or 0),
            label_coverage=pick("label_coverage", "not_assessed"),
            context=pick("context", "clinical_event"),
            review_priority=pick("review_priority", "insufficient_evidence"),
            reasoning=str(d.get("reasoning", "")).strip(),
            next_check=str(d.get("next_check") or "").strip(),
            evidence=[str(x) for x in (d.get("evidence") or [])],
            label_section=d.get("label_section") or None,
            label_term=d.get("label_term") or None,
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "classification": self.classification}


@dataclass
class Verdict:
    reaction: str
    decision: str  # "accept", "reject", "unresolved" (cannot be settled), or "unreviewed" (model review failed)
    reason: str
    checks: dict = field(default_factory=dict)
    objection: str = ""   # the strongest objection to the finding as it stands
    next_check: str = ""  # the Judge's version of the check that would settle it
