"""The "needs manual review" flag on each dossier item, from the triggers fixed in eval/MANUAL_REVIEW_RULES.md
(v1, 25 Oct 2026) before any run scored them. Each trigger that fires gives its own reason. Context only, so it
never changes an item's status, priority or place in the queue, and no agent sees it. On one earlier build two
label triggers, chosen after the fact, flagged 5 of 55 items and all 5 were wrong; that is a hypothesis the next
evaluation tests, which is why the rules are written down first."""
from app.data.label import where

FEW_REPORTS = 5
TRIGGERS = ("few_reports", "label_unclear", "reviewer_rejected", "not_reviewed", "skeptic")


def manual_review(item: dict, reports: int | None) -> dict:
    """{"needed", "reasons", "triggers"} for one review-queue item. reports is the screen's a from Zetaris (None
    if unknown, which fires nothing). An item without a field, such as a pending one with no label coverage, is
    judged only on the fields it has."""
    fired = []
    if reports is not None and reports < FEW_REPORTS:
        fired.append(("few_reports", f"fewer than {FEW_REPORTS} reports ({reports})"))
    found = (item.get("label_search") or {}).get("found") or []
    if item.get("label_coverage") == "unclear":
        fired.append(("label_unclear", "label coverage is unclear"))
    elif found and all(h["kind"] == "not_coverage" for h in found):
        fired.append(("label_unclear", "the label names it only where that never counts as coverage ("
                                       + ", ".join(dict.fromkeys(where(h) for h in found)) + ")"))
    rejected = [str(h.get("round")) for h in item.get("history") or [] if h.get("decision") == "reject"]
    if rejected:
        fired.append(("reviewer_rejected", f"the Reviewer rejected a claim for it (round {', '.join(rejected)})"))
    if item.get("workflow_status") != "reviewed":
        fired.append(("not_reviewed", f"workflow status is {item.get('workflow_status')}"))
    sk = item.get("co_reported_drugs") or {}
    parts = (["the Skeptic challenged it"] if sk.get("outcome") == "challenged" else []) + \
            ([f"adjusting for {', '.join(sk['attenuated_by'])} lowers its PRR by 30% or more"]
             if sk.get("attenuated_by") else [])
    if parts:
        fired.append(("skeptic", "; ".join(parts)))
    return {"needed": bool(fired), "reasons": [r for _, r in fired], "triggers": [t for t, _ in fired]}
