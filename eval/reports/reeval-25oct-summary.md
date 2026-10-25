# Re-evaluation on the code defaults (25 and 26 Oct 2026)

Every live run from 22 to 25 Oct loaded a local `.env` that overrode the code defaults (at least `MODEL_PARALLEL=2` and `REVIEWER_ROUNDS=2`). So those numbers didn't describe the architecture this repo ships. This re-evaluation ran each version on its own code defaults. Those are Ultra for both agents, 4 parallel calls, 1 revision round, a 90 s call limit, 1 retry, a 600 s budget and streaming on (R0 predates streaming).

38 live runs, one at a time. 23 ran on 25 Oct (18:27 to 22:37 Sydney) and 15 overnight on 26 Oct (00:18 to 04:50). Scored with `main`'s `eval/score.py` (`53d100d`) against `eval/gold_v2.jsonl`, and for the newer drugs with task 3's scorer against `gold_newdrugs_v1.jsonl` (SHA-256 `3a7a6808...c1dc1c80`). Ambiguous gold rows are left out of accuracy. Intervals are Wilson 95%. Paired comparisons use an exact two-sided McNemar test on clear items both runs answered. A separate agent re-derived every headline number from the raw dossiers and traces with its own code. Per-version scorer reports are next to this file (`reeval-25oct-*` and `reeval-26oct-*`, `.md` and `.json`).

## Versions

| Label | Commit | What it is |
|---|---|---|
| R0 | `083b669` | Before PR #10 and PR #11. Buffered calls, shared H-MEM scope |
| R2 | `53d100d` | `main`. PR #10 and PR #11, plus the API and Docker (no agent-logic change in those) |
| R3 | `13421ee` | Task 2 (`feature/label-search-evidence`) on `main`. The final tip `65d7c50` differs only in the safety net's display, which feeds no prompt |
| R5 | `484beba` | The speed-ups (`perf/runtime-on-task2`) on task 2's final tip |
| R6 | `b7868b8` | The Skeptic's challenge review alongside the Reviewer's rounds (`feature/parallel-challenge-review`), on the release branch with the messy-input fix |
| RF | `8ae141c` | The final version (`release/clinical-reliability-25-oct`). The same code as R6, plus a README commit |
| R2' | `53d100d` | `main` run again overnight on 26 Oct, as the same-hour control for RF |

## Results

| Change | What it did | Verdict |
|---|---|---|
| **Final version (RF) against `main` (R2'), same hour, six drugs (Phase F)** | Final accuracy 78 of 80 against 74 of 77. On 73 shared clear items, RF alone was right on 2 (zuranolone MANIA and PANIC ATTACK) and `main` alone on 1 (empagliflozin IMPAIRED GASTRIC EMPTYING), p = 1.0. Hidden serious terms surfaced: 14 of 15 against 0 of 15. Median time outside model calls 41 s against 143 s, median run 554 s against 608 s. 2 of 6 runs past budget against 3 of 6. Degraded Reviewer batches 7 against 4 (NVIDIA cuts at the slower overnight speed) | **Better than `main`** on safety-net coverage and time, equal on accuracy |
| PR #10 and #11 (R0 to R2), 5 gold v2 drugs | Final accuracy 49 of 51 to 59 of 60 (p = 1.0). Clear items answered went from 51 to 60 of 71, and unresolved items from 10 to 2. `provider_deadline` cuts fell from 18 to 0 and injected H-MEM memories from 472 to 0. The revision round fitted in 4 of 5 runs, against 1 of 5. Mean run time was 619 s against 616 s | **Improved** |
| Task 2 (R2 to R3), 5 gold v2 drugs | Same answer on all 57 shared clear items. 3 fewer clear items were answered (60 to 57). The revision round fitted in 2 of 5 runs against 4 of 5. Longer prompts make each call about 2.5 s slower, which likely contributes, but one run per drug can't separate that from NVIDIA's variation | **Neutral on accuracy, slight coverage cost** |
| Task 2 (R2 to R3), 3 newer drugs | 14 of 15 hidden serious terms surfaced, against 0 (empagliflozin's Fournier's gangrene and ketoacidosis among them). Final accuracy was 40 of 42 against 39 of 43 (p = 1.0). Round 1 gained 3 items (p = 0.25). Thin-evidence wording was about level, and two 4-report rows moved to "insufficient evidence" | **Improved where intended** |
| Speed-ups (R3 to R5), montelukast and sertraline | Time outside model calls fell from 166 to 99 s and from 117 to 40 s, at the same NVIDIA speed. Run time was 590 s (R5) against 593 s (R3) on montelukast, and 350 s against 518 s on sertraline. Montelukast fitted the revision round and the Skeptic's challenge review, which R3 skipped. No final answer changed. But up to 9 Zetaris queries ran at once, and openFDA rejected two queries with HTTP 500 errors, at least one of them "Too Many Requests" (both handled, nothing lost). R5 also had no NVIDIA 429s, against R3's 13 and 10 | **Improved**, with an openFDA concurrency risk to fix (cap the background pool or use an openFDA key) |
| Challenge review alongside the Reviewer (R5 to R6), atorvastatin, same hour (Phase E) | 3 of 3 Skeptic challenges reviewed, against 0 of 3. Claims changed 2 (1 priority, 1 label-coverage call). Calls in flight stayed within 4. No accuracy change. Both R6 runs ended at 655 s, 55 s past the budget | **Improved** on challenge review, with a budget overrun to fix (a late-start cut-off) |

No accuracy difference in this re-evaluation is statistically significant, and with one run per version per drug none could be. The clear-cut changes are the structural ones, such as cut-off calls, memory injection, items left unreviewed and serious terms surfaced.

### Phase A: R0 against R2 (gold v2)

| | R0 | R2 |
|---|---|---|
| Round 1 | 55 of 58, 94.8% (85.9 to 98.2%) | 57 of 58, 98.3% (90.9 to 99.7%) |
| Final | 49 of 51, 96.1% (86.8 to 98.9%) | 59 of 60, 98.3% (91.1 to 99.7%) |
| Clear items answered | 51 of 71 | 60 of 71 |
| Queue: reviewed, unresolved, not reviewed, failed, pending | 83, 10, 9, 1, 6 | 109, 2, 1, 0, 12 |
| Revision round ran | 1 of 5 | 4 of 5 |
| Mean run time, model-call time, time outside (s) | 619, 402, 216 | 616, 457, 159 |
| NVIDIA 429 waits (pause) | 90 (2,070 s) | 63 (1,200 s) |
| `provider_deadline`, `ttfb_timeout`, `call_time_limit` | 18, 0, 0 | 0, 6, 4 |
| Calls with H-MEM injected | 160 of 160 (472 memories) | 0 of 194 |

In round 1, R2 alone was right on 2 shared items (montelukast OBSTRUCTIVE AIRWAYS DISORDER, sertraline ANXIETY) and R0 alone on none, so p = 0.5. Final, 1 against 0 (p = 1.0). Both got metformin METABOLIC ACIDOSIS wrong. The Skeptic's challenge review was skipped for time in all 10 runs (21 of the 23 runs on 25 Oct; only the two R5 runs skipped nothing).

### Phase B: R2 against R3 (gold v2)

| | R2 | R3 |
|---|---|---|
| Round 1 | 57 of 58, 98.3% (90.9 to 99.7%) | 56 of 57, 98.2% (90.7 to 99.7%) |
| Final | 59 of 60, 98.3% (91.1 to 99.7%) | 56 of 57, 98.2% (90.7 to 99.7%) |
| Clear items answered | 60 of 71 | 57 of 71 |
| Revision round ran | 4 of 5 | 2 of 5 |
| Mean run time, model-call time, time outside (s) | 616, 457, 159 | 588, 437, 152 |
| Mean prompt (characters), Analyst classify and Reviewer | 6,037 and 7,808 | 7,720 and 10,697 |

There are no discordant pairs among the 57 shared items. R3 missed 3 clear items that R2 answered. Metformin VOMITING was left pending when the revision round was skipped. Atorvastatin CHEST PAIN was never named by R3's Reviewer. Isotretinoin BLOOD TRIGLYCERIDES INCREASED was lost to a first-byte cut. Every R3 dossier has the new fields (`safety_net`, `manual_review`, `thin_evidence`, report-source counts, per-item `uncertainty` and `label_search`). The safety net's 8 Zetaris queries per run ran in the background, done by 92 s at the latest, and cost no budget.

### Phase D: R2 against R3 (newer drugs, gold_newdrugs_v1)

| | R2 | R3 |
|---|---|---|
| Round 1 | 36 of 42, 85.7% (72.2 to 93.3%) | 39 of 42, 92.9% (81.0 to 97.5%) |
| Final | 39 of 43, 90.7% (78.4 to 96.3%) | 40 of 42, 95.2% (84.2 to 98.7%) |
| Clear items answered | 43 of 65 | 42 of 65 |
| Hidden serious terms surfaced | 0 of 15 | 14 of 15 |
| Mean run time (s) | 592 | 611 |

In round 1, R3 alone was right on zuranolone MANIA and PANIC ATTACK and on empagliflozin LACTIC ACIDOSIS (p = 0.25). In the final answers, R3 alone was right on MANIA and PANIC ATTACK, and R2 alone on GAIT INABILITY (p = 1.0). On sotagliflozin's thin rows (under 10 reports), caution wording was about level. It was 4 of 8 classified thin items for R3 against 4 of 11 for R2 by task 3's corrected measure, which excludes "not thin" matches (POLLAKIURIA counts, through its Reviewer objection "with only 5 cases the signal is modest"). In the Analyst's own reasoning it was 3 against 0. R3 moved two 4-report rows from "review next" to "insufficient evidence". There's also a definition clash. Task 2's `thin_evidence` flag uses the confidence interval, not the report count, so R3 calls rows with 5 to 9 reports "not thin evidence". The safety-net lists are long (86, 105 and 285 terms), and nothing classifies them, so a person still has to read them.

### Phase C: R3 against R5 (gold v2, two drugs)

| | Montelukast R3 | Montelukast R5 | Sertraline R3 | Sertraline R5 |
|---|---|---|---|---|
| Run time (s) | 593 | 590 | 518 | 350 |
| Time outside model calls (s) | 166 | 99 | 117 | 40 |
| NVIDIA speed (completion tokens/s) | 55.3 | 52.7 | 55.5 | 55.8 |
| NVIDIA 429 waits | 13 | 0 | 10 | 0 |
| Final | 10 of 10 | 10 of 10 | 13 of 13 | 14 of 14 |
| Revision round | skipped | ran | ran | ran |
| Skeptic challenge review | skipped | ran, plus revision | skipped | not needed (no challenge) |
| Peak Zetaris queries in flight | 5 | 9 | 4 | 4 |
| openFDA REST reads in the busiest 60 s | 12 | 20 | 11 | 11 |

23 clear items were shared, with no final disagreement. On montelukast, R5's concurrency set off two openFDA HTTP 500 errors. The first error's body says "Too Many Requests", and the second's was cut off in the trace.
- The early Reviewer re-check failed at 167 s. The Reviewer re-ran it itself, successfully, by 197 s.
- One of the Skeptic's early co-drug counts failed at 226 s. It was for an early guessed target (CHEST DISCOMFORT) that ended at lower priority and never needed the check.

No step was degraded and no item was left unreviewed. Later queries succeeded, so it was a per-minute burst, not the daily cap. Part of sertraline's saving is R3's 10 rate-limit pauses, which R5 didn't get, and that may be the hour rather than the code.

### Phase E: R6 against R5 (the Skeptic's challenge review, 26 Oct)

R6 reviews each Skeptic challenge as soon as its target is settled, alongside the Reviewer's rounds. It uses low-priority slots within the same pool of 4 calls. R6 also carries the messy-input fix (brand names resolved to generics). The control is R5, the combined build, run in the same hour, not `main`.

| | Atorvastatin R5 | Atorvastatin R6 | Montelukast R6 |
|---|---|---|---|
| Started, NVIDIA tokens/s | 00:18, 38.4 | 01:37, 38.9 | 01:49, 38.7 |
| Run time, model-call time, outside (s) | 531, 492, 39 | 655, 631, 24 | 655, 493, 162 |
| Final | 9 of 9 | 10 of 10 | 10 of 10 |
| Skeptic challenges raised, reviewed | 3, 0 | 3, 3 | 1, 1 |
| Revision round | skipped (71 s left) | ran | ran |
| Peak calls in flight after round 1 | 4 | 4 | 4 |

On atorvastatin, the first challenge review started at 396 s, before the Reviewer's round-1 verdicts at 474 s. For all three targets, the Reviewer rejected reasoning that called the signal strong. None of it said that co-reported drugs (proton pump inhibitors, aspirin) bring the adjusted PRR below 2. CHRONIC KIDNEY DISEASE moved from "review next" to "insufficient evidence".

The dossier's `skeptic_priority_changed` says 2 because it counts claims changed (1 priority, 1 label-coverage call). It compares label coverage, context and priority, the same formula as before. So the count is right, but the name overstates it.

Both R6 runs ended 55 s past the budget. On atorvastatin, a challenge review started with 121 s left. On montelukast, the revision round ran long. Three Reviewer batches in R6 degraded to code checks after NVIDIA cuts. R5 montelukast (Phase C) ran 3.5 hours earlier at 52.7 tokens/s, so it isn't a fair time control for R6 montelukast.

### Phase F: the final version (RF) against `main` (R2'), same hour (26 Oct)

NVIDIA served about 30% slower overnight (a median of 38 tokens/s, 33 to 48, against 54 on 25 Oct, when `main`'s evening runs were at 46 to 64). So `main` was run again alongside RF. The first three pairs ran RF first, then `main` 34 to 36 minutes later. The last three ran in random order (seed 20261027), 10 to 14 minutes apart. No pair's speed differed by more than 15%.

| Drug | NVIDIA tokens/s (R2', RF) | R2' run, outside (s) | RF run, outside (s) | R2' final | RF final | Clear | Revision round (R2', RF) |
|---|---|---|---|---|---|---|---|
| metformin | 38.1, 35.0 | 731, 241 | 623, 24 | 11 of 12 | 9 of 9 | 15 | no, no |
| zuranolone | 36.7, 37.8 | 593, 67 | 715, 125 | 16 of 18 | 19 of 19 | 27 | yes, yes |
| sertraline | 32.9, 37.8 | 622, 217 | 525, 41 | 9 of 9 | 12 of 12 | 14 | no, yes |
| sotagliflozin | 33.7, 38.1 | 757, 255 | 582, 41 | 10 of 10 | 11 of 12 | 12 | no, yes |
| isotretinoin | 38.6, 41.9 | 540, 68 | 482, 41 | 14 of 14 | 15 of 15 | 16 | yes, yes |
| empagliflozin | 41.9, 47.6 | 584, 59 | 502, 56 | 14 of 14 | 12 of 13 | 26 | yes, no |

| | R2' (`main`) | RF (final version) |
|---|---|---|
| Gold v2 (3 drugs), round 1 | 37 of 38, 97.4% (86.5 to 99.5%) | 38 of 39, 97.4% (86.8 to 99.5%) |
| Gold v2 (3 drugs), final | 34 of 35, 97.1% (85.5 to 99.5%) | 36 of 36, 100% (90.4 to 100%) |
| Newer drugs (3), round 1 | 37 of 41, 90.2% (77.5 to 96.1%) | 39 of 42, 92.9% (81.0 to 97.5%) |
| Newer drugs (3), final | 40 of 42, 95.2% (84.2 to 98.7%) | 42 of 44, 95.5% (84.9 to 98.7%) |
| All six, final | 74 of 77, 96.1% (89.2 to 98.7%) | 78 of 80, 97.5% (91.3 to 99.3%) |
| Clear items answered | 77 of 110 | 80 of 110 |
| Hidden serious terms surfaced | 0 of 15 | 14 of 15 |
| Thin rows with caution wording, Phase F (sotagliflozin, task 3's corrected measure; Phase D's figure was 4 of 8 against 4 of 11) | 2 of 9 | 8 of 11 |
| Revision round ran | 3 of 6 | 4 of 6 |
| Skeptic challenges reviewed, raised | 0, 1 | 1, 1 |
| Run time median (range), s | 608 (540 to 757) | 554 (482 to 715) |
| Model-call time median, time outside median (s) | 496, 143 | 513, 41 |
| Runs past 600 s | 3 | 2 |
| `ttfb_timeout`, `call_time_limit`, degraded Reviewer batches | 26, 13, 4 | 28, 12, 7 |

On gold v2 there were no discordant items. On the newer drugs, RF alone was right on zuranolone MANIA and PANIC ATTACK, and `main` alone on empagliflozin IMPAIRED GASTRIC EMPTYING (final p = 1.0).

In the slow hour, each version lost three items on one drug to degraded reviews: RF on metformin, `main` on sertraline.

All 12 runs kept calls in flight within 4 after round 1. All calls were Ultra, with no scaffold, no H-MEM, no NVIDIA 429s and no Zetaris or openFDA errors.

## What this design can't show

- **No separate effect for PR #10 or PR #11.** R1 (after PR #10 only) was dropped to finish in one evening, so R0 against R2 measures both PRs together.
- **No measured run-to-run noise.** There's one run per version per drug and no repeat, and Nemotron's answers vary between runs. A one- or two-item difference on a drug may be noise.
- **Speed-ups on two drugs only,** once each. NVIDIA's speed varies by the hour (42 to 69 tokens/s per run on 25 Oct, 33 to 48 overnight). So time outside model calls is the fairer measure, and two runs can't show a general speed-up.
- **Phase F ran in a slow hour.** At half NVIDIA speed, both versions lost items to first-byte cuts and call time limits. The comparison is fair within pairs, but absolute coverage and run times are worse than in a normal hour.
- **Three newer drugs checked offline only.** Semaglutide, tirzepatide and fezolinetant had no live run.
- **AI-labelled gold.** Both gold sets were drafted by an AI assistant and haven't been reviewed by a person.
- **The budget runs over.** The Skeptic step's budget check comes after the deadline, so 8 of the 15 runs in Phases A and B ended 13 to 74 s past the 600 s budget. That's existing behaviour on `main`. In Phase F, 3 of 6 `main` runs and 2 of 6 RF runs went past 600 s, by up to 157 s. That happened when a revision round started near the 120 s threshold at the slow speed.

## Earlier numbers that need relabelling

These working reports (outside the repo) and the earlier `eval/reports/` files from 22 to 25 Oct were measured with the overriding `.env`, not the code defaults. They should be read as "2 parallel calls, 2 revision rounds and other overrides".
- the 24 Oct evaluation (`eval-20261024T022640Z`, which also says 4 parallel and needs checking)
- the consolidated findings and PR #10 draft (`eval-20261024T112546Z`, `eval-20261024T125052Z`)
- the PR #11 live check (`20261025T053746Z-44cfc9`)
- the PR follow-ups
- the low-data and newer-drug baselines
- task 2's live checks
- the run-time bottleneck pairs
- the task 1 overlap feedback
- the clinical reliability review (it relays the figures above)
- the 23 Oct improvement plan (likely the same `.env`, not confirmed)

The Nightshift buffered-against-streamed comparison ran one call at a time, so it stands.

## Run IDs

| Phase | Version | Drug | Run ID | Start (Sydney) |
|---|---|---|---|---|
| A | R0 | montelukast | `20261025T072719Z-dcfa6b` | 18:27 |
| A | R2 | montelukast | `20261025T073949Z-689367` | 18:39 |
| A | R2 | atorvastatin | `20261025T074922Z-d516b4` | 18:49 |
| A | R0 | atorvastatin | `20261025T080114Z-0cdb6f` | 19:01 |
| A | R0 | metformin | `20261025T081259Z-d4c33c` | 19:12 |
| A | R2 | metformin | `20261025T082354Z-93ed65` | 19:23 |
| A | R2 | sertraline | `20261025T083541Z-0c29aa` | 19:35 |
| A | R0 | sertraline | `20261025T084640Z-188701` | 19:46 |
| A | R2 | isotretinoin | `20261025T085657Z-1df654` | 19:56 |
| A | R0 | isotretinoin | `20261025T090814Z-16518f` | 20:08 |
| B | R3 | montelukast | `20261025T091934Z-8d4142` | 20:19 |
| B | R3 | atorvastatin | `20261025T093028Z-dd472b` | 20:30 |
| B | R3 | metformin | `20261025T094242Z-36dbff` | 20:42 |
| B | R3 | sertraline | `20261025T095355Z-b5d91a` | 20:53 |
| B | R3 | isotretinoin | `20261025T100333Z-999438` | 21:03 |
| D | R3 | zuranolone | `20261025T101337Z-5152c8` | 21:13 |
| D | R2 | zuranolone | `20261025T102409Z-ddb35c` | 21:24 |
| D | R3 | sotagliflozin | `20261025T103419Z-a9c122` | 21:34 |
| D | R2 | sotagliflozin | `20261025T104447Z-934dbb` | 21:44 |
| D | R3 | empagliflozin | `20261025T105532Z-47bd9e` | 21:55 |
| D | R2 | empagliflozin | `20261025T110806Z-5915de` | 22:08 |
| C | R5 | montelukast | `20261025T111951Z-ff5945` | 22:19 |
| C | R5 | sertraline | `20261025T113131Z-d278f5` | 22:31 |
| E | R5 | atorvastatin | `20261025T131806Z-96b97f` | 00:18 (26 Oct) |
| E | R6 | atorvastatin | `20261025T143718Z-7da6db` | 01:37 (26 Oct) |
| E | R6 | montelukast | `20261025T144913Z-7daaa6` | 01:49 (26 Oct) |
| F | RF | metformin | `20261025T153908Z-eee925` | 02:39 (26 Oct) |
| F | RF | zuranolone | `20261025T155031Z-10a84a` | 02:50 (26 Oct) |
| F | RF | sertraline | `20261025T160326Z-ee1771` | 03:03 (26 Oct) |
| F | R2' | metformin | `20261025T161311Z-fe8e30` | 03:13 (26 Oct) |
| F | R2' | zuranolone | `20261025T162622Z-a375af` | 03:26 (26 Oct) |
| F | R2' | sertraline | `20261025T163715Z-2903a9` | 03:37 (26 Oct) |
| F | R2' | sotagliflozin | `20261025T164743Z-1a7b50` | 03:47 (26 Oct) |
| F | RF | sotagliflozin | `20261025T170120Z-bf10e5` | 04:01 (26 Oct) |
| F | R2' | isotretinoin | `20261025T171203Z-6183bf` | 04:12 (26 Oct) |
| F | RF | isotretinoin | `20261025T172203Z-2e5486` | 04:22 (26 Oct) |
| F | R2' | empagliflozin | `20261025T173105Z-51dc64` | 04:31 (26 Oct) |
| F | RF | empagliflozin | `20261025T174149Z-313ee3` | 04:41 (26 Oct) |

Order within each drug was random (seeds 20261025 for Phase A, 20261026 for Phase D and 20261027 for Phase F's last three pairs). Logs and traces stay on the machine that ran them, since `logs/` is never committed.
