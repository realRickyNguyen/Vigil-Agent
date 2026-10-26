# Vigil evaluation

Gold set: `eval/gold_v2_reviewed.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 3.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T161311Z-fe8e30 | metformin | 11/12 | 11/12 | kept_correct 11, kept_wrong 1 | 0 | 0 (0) | 4 (possible_new_signal (ambiguous) 4) | 1 | pending 3, failed 1 |
| 20261025T163715Z-2903a9 | sertraline | 11/11 | 8/8 | kept_correct 8, not_reviewed 3 | 0 | 0 (0) | 1 (not in gold 1) | 1 | failed 1 |
| 20261025T171203Z-6183bf | isotretinoin | 14/14 | 14/14 | kept_correct 14 | 3 | 1 (1) | 2 (possible_new_signal 1, possible_new_signal (ambiguous) 1) | 1 | pending 3 |

**Overall:** round-1 accuracy 36/37 = 97%, final accuracy 33/34 = 97%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 33, kept_wrong 1, not_reviewed 3

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

