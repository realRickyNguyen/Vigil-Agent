# Vigil evaluation

Gold set: `eval/gold_newdrugs_v1_reviewed.jsonl` (labelled by an AI assistant, not yet reviewed by a person; ambiguous rows excluded from accuracy). Runs: 3.

| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |
|---|---|---|---|---|---|---|---|---|---|
| 20261025T162622Z-a375af | zuranolone | 15/17 | 16/18 | kept_correct 15, kept_wrong 2 | 2 | 3 (1) | 5 (possible_new_signal (ambiguous) 2, on_label 2, possible_new_signal 1) | 0 | pending 3, failed 1 |
| 20261025T164743Z-1a7b50 | sotagliflozin | 10/10 | 10/10 | kept_correct 10 | 0 | 1 (1) | 6 (possible_new_signal (ambiguous) 2, possible_new_signal 1, on_label (ambiguous) 2, likely_indication_or_disease (ambiguous) 1) | 2 | pending 2 |
| 20261025T173105Z-51dc64 | empagliflozin | 12/14 | 14/14 | fixed 1, kept_correct 12, unresolved_was_wrong 1 | 2 | 1 (1) | 3 (possible_new_signal (ambiguous) 1, possible_new_signal 1, not in gold 1) | 3 | pending 3 |

**Overall:** round-1 accuracy 37/41 = 90%, final accuracy 40/42 = 95%.

Reviewer effect across runs (clear gold items the Analyst classified in round 1): fixed 1, kept_correct 37, kept_wrong 2, unresolved_was_wrong 1

- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.
- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.
- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.
- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; this says whether the Analyst's round-1 answer had been right.
- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.

