# Vigil evaluation

Gold set: `eval/gold_v2.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 5.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T072719Z-dcfa6b | montelukast | 8/9 | 7/7 | kept_correct 7, not_reviewed 1, unresolved_was_wrong 1 | 0 | 0 (0) | 4 (likely_indication_or_disease (ambiguous) 1, possible_new_signal (ambiguous) 2, not in gold 1) | 2 | failed 1 |
| 20261025T080114Z-0cdb6f | atorvastatin | 9/9 | 8/8 | kept_correct 6, not_reviewed 3 | 2 | 0 (0) | 7 (possible_new_signal (ambiguous) 4, not in gold 3) | 1 | - |
| 20261025T081259Z-d4c33c | metformin | 12/13 | 12/13 | kept_correct 12, kept_wrong 1 | 0 | 1 (0) | 5 (possible_new_signal (ambiguous) 4, on_label 1) | 2 | pending 3 |
| 20261025T084640Z-188701 | sertraline | 12/13 | 10/11 | kept_correct 10, kept_wrong 1, unresolved_was_correct 2 | 0 | 0 (0) | 1 (not in gold 1) | 3 | pending 3 |
| 20261025T090814Z-16518f | isotretinoin | 14/14 | 12/12 | kept_correct 12, not_reviewed 2 | 0 | 1 (1) | 4 (not_meaningful (ambiguous) 1, possible_new_signal 1, possible_new_signal (ambiguous) 1, not in gold 1) | 2 | - |

**Overall:** round-1 accuracy 55/58 = 95%, final accuracy 49/51 = 96%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 47, kept_wrong 2, not_reviewed 6, unresolved_was_correct 2, unresolved_was_wrong 1

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

