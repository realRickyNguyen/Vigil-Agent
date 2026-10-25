# Vigil evaluation

Gold set: `eval/gold_newdrugs_v1.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 3.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T102409Z-ddb35c | zuranolone | 15/18 | 17/20 | kept_correct 15, kept_wrong 3 | 3 | 3 (1) | 6 (on_label 2, possible_new_signal (ambiguous) 3, possible_new_signal 1) | 0 | pending 3 |
| 20261025T104447Z-934dbb | sotagliflozin | 10/10 | 11/12 | kept_correct 10 | 3 | 1 (1) | 6 (possible_new_signal (ambiguous) 2, possible_new_signal 1, on_label (ambiguous) 2, likely_indication_or_disease (ambiguous) 1) | 1 | - |
| 20261025T110806Z-5915de | empagliflozin | 11/14 | 11/11 | kept_correct 11, unresolved_was_wrong 3 | 0 | 0 (0) | 4 (possible_new_signal (ambiguous) 1, on_label (ambiguous) 2, likely_indication_or_disease (ambiguous) 1) | 3 | pending 3 |

**Overall:** round-1 accuracy 36/42 = 86%, final accuracy 39/43 = 91%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): kept_correct 36, kept_wrong 3, unresolved_was_wrong 3

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

