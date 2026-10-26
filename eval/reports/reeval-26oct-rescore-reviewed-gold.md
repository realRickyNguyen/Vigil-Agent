# Re-score against the reviewed gold (26 Oct 2026)

On 26 Oct a team member reviewed gold v2's 71 clear rows and the newer-drug set's 15 serious terms outside the screen, with AI assistance ([GOLD_REVIEW.md](../GOLD_REVIEW.md)). This re-scores all 38 runs of the 25 to 26 Oct re-evaluation ([reeval-25oct-summary.md](reeval-25oct-summary.md)) against the reviewed files, `eval/gold_v2_reviewed.jsonl` and `eval/gold_newdrugs_v1_reviewed.jsonl`. No comparison's conclusion changed.

**How it was scored.** Every phase was scored with the commands in `docs/HANDOFF.md` (Bryan's task 1), on `main`'s scorer (`eval/run_eval.py --score-only`, with `eval/score.py` unchanged since `53d100d`). Phase F used HANDOFF's four commands as written. Every other phase used the same form, with the run IDs from `scores[].run_id` in its `reeval-*.json` and that file's gold swapped for its `_reviewed` version. The scorer reads `logs/` only, so nothing ran live. Each re-scored report sits next to its original, with `-reviewed` added to the name.

**Checks.**
- With the original gold, the same scorer reproduces every score in all 12 existing reports exactly, so only the gold differs.
- A separate agent recomputed every figure here from the raw dossiers and traces with its own code, under both golds, and found no differences.
- The reports' header line still says the gold is "not yet reviewed by a person". That line is hard-coded in `eval/score.py`, so it's out of date for the reviewed files.

## What the review changed

- **gold v2**, clear rows 71 to 68
  - metformin METABOLIC ACIDOSIS, on_label to possible_new_signal
  - montelukast NASAL CONGESTION, likely_indication_or_disease to on_label
  - montelukast DYSPNOEA and WHEEZING, and sertraline INTENTIONAL SELF-INJURY, clear to ambiguous
- **gold_newdrugs_v1**, clear rows 157 to 159, and 65 to 67 for the three drugs run
  - empagliflozin NECROTISING FASCIITIS and zuranolone PERINATAL DEPRESSION, ambiguous to clear
  - Five other reviewed rows stay ambiguous, and no other row changed category or ambiguity.
- No run answered NASAL CONGESTION, NECROTISING FASCIITIS or PERINATAL DEPRESSION, so those three changes move no score.

## Before and after, by phase

These are clear items only, with Wilson 95% intervals.

| Phase | Version | Round 1 before | Round 1 after | Final before | Final after | Answered before, after |
|---|---|---|---|---|---|---|
| A | R0 | 55 of 58 (85.9 to 98.2%) | 53 of 55 (87.7 to 99.0%) | 49 of 51 (86.8 to 98.9%) | 48 of 49 (89.3 to 99.6%) | 51 of 71, 49 of 68 |
| A, B | R2 | 57 of 58 (90.9 to 99.7%) | 55 of 55 (93.5 to 100%) | 59 of 60 (91.1 to 99.7%) | 57 of 57 (93.7 to 100%) | 60 of 71, 57 of 68 |
| B | R3 | 56 of 57 (90.7 to 99.7%) | 54 of 54 (93.4 to 100%) | 56 of 57 (90.7 to 99.7%) | 54 of 54 (93.4 to 100%) | 57 of 71, 54 of 68 |
| C (2 drugs) | R3 | 23 of 23 (85.7 to 100%) | 20 of 20 (83.9 to 100%) | 23 of 23 (85.7 to 100%) | 20 of 20 (83.9 to 100%) | 23 of 27, 20 of 24 |
| C (2 drugs) | R5 | 22 of 23 (79.0 to 99.2%) | 19 of 20 (76.4 to 99.1%) | 24 of 24 (86.2 to 100%) | 21 of 21 (84.5 to 100%) | 24 of 27, 21 of 24 |
| D | R2 | 36 of 42 (72.2 to 93.3%) | 36 of 42 (72.2 to 93.3%) | 39 of 43 (78.4 to 96.3%) | 39 of 43 (78.4 to 96.3%) | 43 of 65, 43 of 67 |
| D | R3 | 39 of 42 (81.0 to 97.5%) | 39 of 42 (81.0 to 97.5%) | 40 of 42 (84.2 to 98.7%) | 40 of 42 (84.2 to 98.7%) | 42 of 65, 42 of 67 |
| E | R5 (atorvastatin) | 9 of 9 (70.1 to 100%) | 9 of 9 (70.1 to 100%) | 9 of 9 (70.1 to 100%) | 9 of 9 (70.1 to 100%) | 9 of 13, 9 of 13 |
| E | R6 (2 drugs) | 19 of 19 (83.2 to 100%) | 17 of 17 (81.6 to 100%) | 20 of 20 (83.9 to 100%) | 18 of 18 (82.4 to 100%) | 20 of 26, 18 of 24 |
| F gold v2 | R2' | 37 of 38 (86.5 to 99.5%) | 36 of 37 (86.2 to 99.5%) | 34 of 35 (85.5 to 99.5%) | 33 of 34 (85.1 to 99.5%) | 35 of 45, 34 of 44 |
| F gold v2 | RF | 38 of 39 (86.8 to 99.5%) | 38 of 38 (90.8 to 100%) | 36 of 36 (90.4 to 100%) | 35 of 35 (90.1 to 100%) | 36 of 45, 35 of 44 |
| F newer | R2' | 37 of 41 (77.5 to 96.1%) | 37 of 41 (77.5 to 96.1%) | 40 of 42 (84.2 to 98.7%) | 40 of 42 (84.2 to 98.7%) | 42 of 65, 42 of 67 |
| F newer | RF | 39 of 42 (81.0 to 97.5%) | 39 of 42 (81.0 to 97.5%) | 42 of 44 (84.9 to 98.7%) | 42 of 44 (84.9 to 98.7%) | 44 of 65, 44 of 67 |
| F, six drugs | R2' | 74 of 79 (86.0 to 97.3%) | 73 of 78 (85.9 to 97.2%) | 74 of 77 (89.2 to 98.7%) | 73 of 76 (89.0 to 98.6%) | 77 of 110, 76 of 111 |
| F, six drugs | RF | 77 of 81 (88.0 to 98.1%) | 77 of 80 (89.5 to 98.7%) | 78 of 80 (91.3 to 99.3%) | 77 of 79 (91.2 to 99.3%) | 80 of 110, 79 of 111 |

Each cell is how many of a version's answers on clear items agreed with the reference, out of the clear items it answered. Where before and after match, the review changed no item that run answered. That covers every newer-drug figure, because the two newer-drug rows it changed are outside the screen and no version classified them.

## Paired comparisons

These use an exact two-sided McNemar test on the clear items both runs answered.

| Comparison | Stage | Original gold | Reviewed gold |
|---|---|---|---|
| A, R0 against R2 | round 1 | 57 shared, R2 alone right on 2 (montelukast OBSTRUCTIVE AIRWAYS DISORDER, sertraline ANXIETY), R0 alone on 0, p = 0.5 | 54 shared, the same 2 against 0, p = 0.5 |
| A | final | 49 shared, R2 alone right on 1 (sertraline ANXIETY), p = 1.0 | 47 shared, the same 1 against 0, p = 1.0 |
| B, R2 against R3 | round 1 and final | 57 shared, no discordant items (both wrong on METABOLIC ACIDOSIS) | 54 shared, no discordant items (both right on METABOLIC ACIDOSIS) |
| C, R3 against R5 | round 1 | 23 shared, R3 alone right on 1 (montelukast CHEST DISCOMFORT), p = 1.0 | 20 shared, the same, p = 1.0 |
| C | final | 23 shared, no discordant items | 20 shared, no discordant items |
| D, R2 against R3 | round 1 | 42 shared, R3 alone right on 3 (zuranolone MANIA and PANIC ATTACK, empagliflozin LACTIC ACIDOSIS), p = 0.25 | 42 shared, the same 3 against 0, p = 0.25 |
| D | final | 41 shared, R3 alone right on 2 (MANIA, PANIC ATTACK), R2 alone on 1 (GAIT INABILITY), p = 1.0 | 41 shared, the same 2 against 1, p = 1.0 |
| E, R5 against R6 (atorvastatin) | round 1 and final | 9 shared, no discordant items | 9 shared, no discordant items |
| F gold v2, R2' against RF | round 1 | 38 shared, no discordant items (both wrong on METABOLIC ACIDOSIS) | 37 shared, RF alone right on 1 (metformin METABOLIC ACIDOSIS, where RF said possible_new_signal and R2' said likely_indication_or_disease), p = 1.0 |
| F gold v2 | final | 32 shared, no discordant items | 31 shared, no discordant items (RF's final on METABOLIC ACIDOSIS was not reviewed, so it isn't scored) |
| F newer | round 1 | 41 shared, RF alone right on 2 (MANIA, PANIC ATTACK), p = 0.5 | 41 shared, the same 2 against 0, p = 0.5 |
| F newer | final | 41 shared, RF alone right on 2, R2' alone on 1 (empagliflozin IMPAIRED GASTRIC EMPTYING), p = 1.0 | 41 shared, the same 2 against 1, p = 1.0 |
| F, six drugs | round 1 | 79 shared, RF alone right on 2, R2' alone on 0, p = 0.5 | 78 shared, RF alone right on 3, R2' alone on 0, p = 0.25 |
| F, six drugs | final | 73 shared, RF alone right on 2, R2' alone on 1, p = 1.0 | 72 shared, RF alone right on 2, R2' alone on 1, p = 1.0 |

**Review next.** The only change is metformin METABOLIC ACIDOSIS, which moves from on_label to possible_new_signal, clear both times, in the runs that sent it to review next. Those are R0 and R2 in Phase A, and R2 and R3 in Phase B. In each of those versions, clear on_label entries in review next go from 1 to 0 and clear possible_new_signal entries from 1 to 2. So `main`'s (R2's) 22 review-next entries in Phase A are now 20 that the reference calls ambiguous or doesn't include, and 2 clear possible new signals. No other phase's review next changed.

**Measures that don't use the gold's labels.** The hidden serious terms are picked by the gold's `origin` field and counted from the dossier's own text, so the count is unchanged. R2 and R2' surfaced 0 of 15, and R3 and RF 14 of 15. The thin-row caution counts use dossier report counts and text only, and are also unchanged. In Phase D, R3 used words of caution on 4 of 8 thin items and R2 on 4 of 11. In Phase F, RF did on 8 of 11 and R2' on 2 of 9. Task 3's scorer gives the same counts under both golds.

## Every changed outcome (38)

- **DYSPNOEA and WHEEZING (montelukast)**, answered likely_indication_or_disease and now ambiguous, so right to excluded. Round 1 and final in A-R0, A-R2, B-R3, C-R5 and E-R6 (20 outcomes).
- **INTENTIONAL SELF-INJURY (sertraline)**, answered on_label and now ambiguous, so right to excluded. Round 1 and final in A-R2, B-R3, C-R5, F-RF and F-R2' (10 outcomes), and round 1 only in A-R0, whose final was unresolved (1 outcome).
- **METABOLIC ACIDOSIS (metformin)**, answered possible_new_signal, with the gold moving from on_label to possible_new_signal, so wrong to right. Round 1 and final in A-R0, A-R2 and B-R3 (6 outcomes), and round 1 only in F-RF, whose final was not reviewed (1 outcome). F-R2' answered likely_indication_or_disease, which is wrong under both golds, so it doesn't change.
- No newer-drug outcome changed.

Each phase and version has one run per drug, so these name single runs. Their run IDs are in the summary's Run IDs table.

## Reports

| Re-scored report | Gold | Runs |
|---|---|---|
| [reeval-25oct-A-R0-083b669-reviewed.md](reeval-25oct-A-R0-083b669-reviewed.md) | gold_v2_reviewed | 5 |
| [reeval-25oct-A-R2-53d100d-reviewed.md](reeval-25oct-A-R2-53d100d-reviewed.md) | gold_v2_reviewed | 5 |
| [reeval-25oct-B-R3-13421ee-reviewed.md](reeval-25oct-B-R3-13421ee-reviewed.md) | gold_v2_reviewed | 5 |
| [reeval-25oct-C-R5-484beba-reviewed.md](reeval-25oct-C-R5-484beba-reviewed.md) | gold_v2_reviewed | 2 |
| [reeval-25oct-D-R2-53d100d-newdrugs-reviewed.md](reeval-25oct-D-R2-53d100d-newdrugs-reviewed.md) | gold_newdrugs_v1_reviewed | 3 |
| [reeval-25oct-D-R3-13421ee-newdrugs-reviewed.md](reeval-25oct-D-R3-13421ee-newdrugs-reviewed.md) | gold_newdrugs_v1_reviewed | 3 |
| [reeval-26oct-E-R5-484beba-control-reviewed.md](reeval-26oct-E-R5-484beba-control-reviewed.md) | gold_v2_reviewed | 1 |
| [reeval-26oct-E-R6-b7868b8-reviewed.md](reeval-26oct-E-R6-b7868b8-reviewed.md) | gold_v2_reviewed | 2 |
| [reeval-26oct-F-RF-8ae141c-reviewed.md](reeval-26oct-F-RF-8ae141c-reviewed.md) | gold_v2_reviewed | 3 |
| [reeval-26oct-F-R2control-53d100d-reviewed.md](reeval-26oct-F-R2control-53d100d-reviewed.md) | gold_v2_reviewed | 3 |
| [reeval-26oct-F-RF-8ae141c-newdrugs-reviewed.md](reeval-26oct-F-RF-8ae141c-newdrugs-reviewed.md) | gold_newdrugs_v1_reviewed | 3 |
| [reeval-26oct-F-R2control-53d100d-newdrugs-reviewed.md](reeval-26oct-F-R2control-53d100d-newdrugs-reviewed.md) | gold_newdrugs_v1_reviewed | 3 |

Phase C's R3 figures come from Phase B's report, and Phase B's R2 from Phase A's.
