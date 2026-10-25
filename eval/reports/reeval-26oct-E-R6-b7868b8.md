# Vigil evaluation

Gold set: `eval/gold_v2.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 2.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T143718Z-7da6db | atorvastatin | 9/9 | 10/10 | kept_correct 9 | 3 | 0 (0) | 5 (possible_new_signal (ambiguous) 2, not in gold 3) | 0 | pending 3 |
| 20261025T144913Z-7daaa6 | montelukast | 10/10 | 10/10 | kept_correct 9, not_reviewed 1 | 2 | 0 (0) | 5 (likely_indication_or_disease (ambiguous) 1, possible_new_signal (ambiguous) 3, not in gold 1) | 0 | - |

**Overall:** round-1 accuracy 19/19 = 100%, final accuracy 20/20 = 100%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 18, not_reviewed 1

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

