# Vigil evaluation

Gold set: `eval/gold_v2.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 5.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T091934Z-8d4142 | montelukast | 10/10 | 10/10 | kept_correct 10 | 0 | 0 (0) | 6 (likely_indication_or_disease (ambiguous) 1, possible_new_signal (ambiguous) 4, not in gold 1) | 0 | pending 3 |
| 20261025T093028Z-dd472b | atorvastatin | 9/9 | 9/9 | kept_correct 9 | 0 | 0 (0) | 6 (possible_new_signal (ambiguous) 4, not in gold 2) | 1 | pending 3 |
| 20261025T094242Z-36dbff | metformin | 11/12 | 11/12 | kept_correct 11, kept_wrong 1 | 0 | 1 (0) | 5 (possible_new_signal (ambiguous) 3, on_label 1, not in gold 1) | 1 | pending 3 |
| 20261025T095355Z-b5d91a | sertraline | 13/13 | 13/13 | kept_correct 13 | 3 | 0 (0) | 2 (on_label (ambiguous) 2) | 0 | pending 3 |
| 20261025T100333Z-999438 | isotretinoin | 13/13 | 13/13 | kept_correct 13 | 3 | 1 (1) | 4 (not_meaningful (ambiguous) 2, possible_new_signal 1, possible_new_signal (ambiguous) 1) | 0 | pending 3, failed 1 |

**Overall:** round-1 accuracy 56/57 = 98%, final accuracy 56/57 = 98%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 56, kept_wrong 1

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

