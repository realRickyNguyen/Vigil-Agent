# Vigil evaluation

Gold set: `eval/gold_v2_reviewed.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 5.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T073949Z-689367 | montelukast | 8/8 | 8/8 | kept_correct 8 | 0 | 0 (0) | 4 (likely_indication_or_disease (ambiguous) 1, possible_new_signal (ambiguous) 3) | 0 | pending 3 |
| 20261025T074922Z-d516b4 | atorvastatin | 9/9 | 10/10 | kept_correct 9 | 1 | 0 (0) | 7 (possible_new_signal (ambiguous) 4, not in gold 3) | 1 | - |
| 20261025T082354Z-93ed65 | metformin | 12/12 | 13/13 | kept_correct 12 | 3 | 1 (1) | 7 (possible_new_signal (ambiguous) 3, possible_new_signal 1, not in gold 3) | 0 | pending 3 |
| 20261025T083541Z-0c29aa | sertraline | 12/12 | 12/12 | kept_correct 12 | 3 | 0 (0) | 2 (on_label (ambiguous) 1, not in gold 1) | 1 | pending 3 |
| 20261025T085657Z-1df654 | isotretinoin | 14/14 | 14/14 | kept_correct 14 | 3 | 1 (1) | 2 (possible_new_signal 1, possible_new_signal (ambiguous) 1) | 0 | pending 3 |

**Overall:** round-1 accuracy 55/55 = 100%, final accuracy 57/57 = 100%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 55

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

