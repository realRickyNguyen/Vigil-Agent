# "Needs manual review" rules (v1, 25 Oct 2026)

These rules were written down and fixed on 25 Oct 2026, before any run scored them. No evaluation, gold set or dossier was scored against them before this file was committed, and the code that applies them (`app/orchestration/manual_review.py`) was written after it.

## Why the rules are fixed first

The flag tells a person which items to distrust first. It comes from an earlier idea that was tested after the fact. A clinical review on 25 Oct (`Vigil_Clinical_Reliability_Review.md`, Section 3.6, in the project notes outside the repo) tried 13 triggers on the 7 runs of PR #10. On one build, two label triggers flagged 5 of 55 items, and all 5 were wrong, against 1 of the 50 unflagged items. Those triggers were chosen after seeing 6 errors from 2 drugs, so the result is a hypothesis, not a finding. It also did not carry over to an earlier build, whose errors were confident "not found" calls.

So the trigger list is fixed here, before the next evaluation, and that evaluation tests it. A change to any trigger needs a new dated version of this file, and results under each version are reported separately.

## What the flag does

Every dossier item has `manual_review` with `needed` (true or false), `reasons` (one plain sentence per trigger that fired) and `triggers` (the IDs below). The dossier's `counts` has `manual_review`, the number of items flagged.

It is context only. It never changes an item's workflow status, review priority or place in the queue, and neither agent sees it.

## The triggers

An item needs manual review if any of these hold. Each gives its own reason.

| ID | Trigger | Where it is read from |
|---|---|---|
| `few_reports` | Fewer than 5 reports with the drug | The screen's `a`, counted in Zetaris |
| `label_unclear` | Label coverage is `unclear`, or the code's label search names the reaction only where it never counts as coverage (every `found` entry of `label.search()` has kind `not_coverage`, the case its summary words as "Named only where it never counts as coverage"). A name only in the contraindications is this case | `label_coverage` and `label_search` |
| `reviewer_rejected` | Any Reviewer rejection in the item's history, in any round, whether from code checks or the model | `history` entries with decision `reject` |
| `not_reviewed` | Any workflow status other than `reviewed` (`unresolved`, `not_reviewed`, `pending`, `failed`) | `workflow_status` |
| `skeptic` | The Skeptic found co-drugs that lower the PRR by 30% or more without taking it below 2 (`attenuated_by` not empty), or its outcome is `challenged` | `co_reported_drugs` |

An item the Skeptic did not check, or a pending or failed item with no label coverage, is judged only on the fields it has.

## Considered and left out

From the 13 triggers in Section 3.6, these are not in v1. IC025 at or below 0 and a PRR lower bound below 2 (thin evidence is shown separately in each item's `uncertainty`, and only the report count is a trigger here), a label quote missing the matched term, a likely section not fetched, disagreement across repeated samples, and one country holding most reports.

## How the next evaluation will score it

On the next evaluation run, for gold items that are not marked ambiguous, report the following, whatever they show.
- The share of items flagged, per drug and overall.
- The final error rate of flagged and of unflagged items, with counts, and a two-sided Fisher exact test.
- The same for each trigger on its own.

Say which gold version and which commit were used. The gold labels were made by an AI and are not yet reviewed by a person, so these numbers are a development check, not clinical validation.
