"""Shapes passed between the Clerk, the agents and the dossier."""
from dataclasses import dataclass, field, asdict

CLASSIFICATIONS = ("on_label", "possible_new_signal", "likely_indication_or_disease", "not_meaningful")

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
    classification: str
    reasoning: str
    evidence: list[str] = field(default_factory=list)
    label_section: str | None = None
    label_term: str | None = None   # phrase the Hunter says the label uses for this reaction
    label_quote: str | None = None  # sentence around label_term, extracted by code, never by the model
    decided_by: str = "hunter"      # "hunter" (model) or "rule" (app/agents/rules.py)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(
            reaction=str(d.get("reaction", "")).strip(),
            a=int(d.get("a") or 0),
            prr=float(d.get("prr") or 0),
            classification=str(d.get("classification", "")).strip(),
            reasoning=str(d.get("reasoning", "")).strip(),
            evidence=[str(x) for x in (d.get("evidence") or [])],
            label_section=d.get("label_section") or None,
            label_term=d.get("label_term") or None,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    reaction: str
    decision: str  # "accept", "reject", or "unreviewed" (passed code checks; the model review failed)
    reason: str
    checks: dict = field(default_factory=dict)
