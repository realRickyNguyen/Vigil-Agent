# Vigil evaluation

Gold set: `eval/gold_newdrugs_v1.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 3.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T101337Z-5152c8 | zuranolone | 17/18 | 18/20 | broken 1, kept_correct 16, kept_wrong 1 | 3 | 3 (1) | 6 (on_label 2, possible_new_signal (ambiguous) 3, possible_new_signal 1) | 0 | pending 3 |
| 20261025T103419Z-a9c122 | sotagliflozin | 10/10 | 10/10 | kept_correct 10 | 0 | 1 (1) | 4 (possible_new_signal (ambiguous) 2, on_label (ambiguous) 2) | 1 | pending 3 |
| 20261025T105532Z-47bd9e | empagliflozin | 12/14 | 12/12 | kept_correct 12, unresolved_was_wrong 2 | 0 | 1 (1) | 2 (possible_new_signal 1, likely_indication_or_disease (ambiguous) 1) | 3 | pending 3 |

**Overall:** round-1 accuracy 39/42 = 93%, final accuracy 40/42 = 95%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): broken 1, kept_correct 38, kept_wrong 1, unresolved_was_wrong 2

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

