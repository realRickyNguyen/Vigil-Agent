# Vigil evaluation

Gold set: `eval/gold_v2_reviewed.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 3.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T153908Z-eee925 | metformin | 12/12 | 9/9 | kept_correct 9, not_reviewed 3 | 0 | 0 (0) | 4 (possible_new_signal (ambiguous) 4) | 2 | - |
| 20261025T160326Z-ee1771 | sertraline | 12/12 | 11/11 | kept_correct 11, not_reviewed 1 | 3 | 0 (0) | 1 (on_label (ambiguous) 1) | 0 | pending 3 |
| 20261025T172203Z-2e5486 | isotretinoin | 14/14 | 15/15 | kept_correct 14 | 3 | 1 (1) | 4 (not_meaningful (ambiguous) 1, possible_new_signal 1, possible_new_signal (ambiguous) 1, not in gold 1) | 0 | pending 3 |

**Overall:** round-1 accuracy 38/38 = 100%, final accuracy 35/35 = 100%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 34, not_reviewed 4

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

