# Re-evaluation on the code defaults (25 Oct 2026)

Every live run from 22 to 25 Oct loaded a local `.env` that overrode the code defaults (at least `MODEL_PARALLEL=2` and `REVIEWER_ROUNDS=2`). So those numbers didn't describe the architecture this repo ships. This re-evaluation ran each version on its own code defaults. Those are Ultra for both agents, 4 parallel calls, 1 revision round, a 90 s call limit, 1 retry, a 600 s budget and streaming on (R0 predates streaming).

23 live runs, 18:27 to 22:37 Sydney, one at a time. Scored with `main`'s `eval/score.py` (`53d100d`) against `eval/gold_v2.jsonl`, and for the newer drugs with task 3's scorer against `gold_newdrugs_v1.jsonl` (SHA-256 `3a7a6808...c1dc1c80`). Ambiguous gold rows are left out of accuracy. Intervals are Wilson 95%. Paired comparisons use an exact two-sided McNemar test on clear items both runs answered. A separate agent re-derived every headline number from the raw dossiers and traces with its own code. Per-version scorer reports are next to this file (`reeval-25oct-*.md` and `.json`).

## Versions

| Label | Commit | What it is |
|---|---|---|
| R0 | `083b669` | Before PR #10 and PR #11. Buffered calls, shared H-MEM scope |
| R2 | `53d100d` | `main`. PR #10 and PR #11, plus the API and Docker (no agent-logic change in those) |
| R3 | `13421ee` | Task 2 (`feature/label-search-evidence`) on `main`. The final tip `65d7c50` differs only in the safety net's display, which feeds no prompt |
| R5 | `484beba` | The speed-ups (`perf/runtime-on-task2`) on task 2's final tip |

## Results

| Change | What it did | Verdict |
|---|---|---|
| PR #10 and #11 (R0 to R2), 5 gold v2 drugs | Final accuracy 49 of 51 to 59 of 60 (p = 1.0). Clear items answered went from 51 to 60 of 71, and unresolved items from 10 to 2. `provider_deadline` cuts fell from 18 to 0 and injected H-MEM memories from 472 to 0. The revision round fitted in 4 of 5 runs, against 1 of 5. Mean run time was 619 s against 616 s | **Improved** |
| Task 2 (R2 to R3), 5 gold v2 drugs | Same answer on all 57 shared clear items. 3 fewer clear items were answered (60 to 57). The revision round fitted in 2 of 5 runs against 4 of 5. Longer prompts make each call about 2.5 s slower, which likely contributes, but one run per drug can't separate that from NVIDIA's variation | **Neutral on accuracy, slight coverage cost** |
| Task 2 (R2 to R3), 3 newer drugs | 14 of 15 hidden serious terms surfaced, against 0 (empagliflozin's Fournier's gangrene and ketoacidosis among them). Final accuracy was 40 of 42 against 39 of 43 (p = 1.0). Round 1 gained 3 items (p = 0.25). Thin-evidence wording was more cautious | **Improved where intended** |
| Speed-ups (R3 to R5), montelukast and sertraline | Time outside model calls fell from 166 to 99 s and from 117 to 40 s, at the same NVIDIA speed. Run time was 590 s (R5) against 593 s (R3) on montelukast, and 350 s against 518 s on sertraline. Montelukast fitted the revision round and the Skeptic's challenge review, which R3 skipped. No final answer changed. But up to 9 Zetaris queries ran at once, and openFDA rejected two queries with HTTP 500 errors, at least one of them "Too Many Requests" (both handled, nothing lost). R5 also had no NVIDIA 429s, against R3's 13 and 10 | **Improved**, with an openFDA concurrency risk to fix (cap the background pool or use an openFDA key) |

No accuracy difference tonight is statistically significant, and with one run per version per drug none could be. The clear-cut changes are the structural ones, such as cut-off calls, memory injection, items left unreviewed and serious terms surfaced.

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

In round 1, R2 alone was right on 2 shared items (montelukast OBSTRUCTIVE AIRWAYS DISORDER, sertraline ANXIETY) and R0 alone on none, so p = 0.5. Final, 1 against 0 (p = 1.0). Both got metformin METABOLIC ACIDOSIS wrong. The Skeptic's challenge review was skipped for time in all 10 runs.

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

In round 1, R3 alone was right on zuranolone MANIA and PANIC ATTACK and on empagliflozin LACTIC ACIDOSIS (p = 0.25). In the final answers, R3 alone was right on MANIA and PANIC ATTACK, and R2 alone on GAIT INABILITY (p = 1.0). On sotagliflozin's thin rows, R3 used more caution wording on every count. By task 3's scorer it was 6 of 8 classified thin items against 4 of 11. In the model's own reasoning text it was 4 against 0. It moved two 4-report rows from "review next" to "insufficient evidence". The safety-net lists are long (86, 105 and 285 terms), and nothing classifies them, so a person still has to read them.

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

## What this design can't show

- **No separate effect for PR #10 or PR #11.** R1 (after PR #10 only) was dropped to finish in one evening, so R0 against R2 measures both PRs together.
- **No measured run-to-run noise.** There's one run per version per drug and no repeat, and Nemotron's answers vary between runs. A one- or two-item difference on a drug may be noise.
- **Speed-ups on two drugs only,** once each. NVIDIA's speed varies by the hour, so time outside model calls is the fairer measure, and two runs can't show a general speed-up.
- **Three newer drugs checked offline only.** Semaglutide, tirzepatide and fezolinetant had no live run tonight.
- **AI-labelled gold.** Both gold sets were drafted by an AI assistant and haven't been reviewed by a person.
- **The budget runs over.** The Skeptic step's budget check comes after the deadline, so 8 of the 15 runs in Phases A and B ended 13 to 74 s past the 600 s budget. That's existing behaviour on `main`.

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

Order within each drug was random (seeds 20261025 for Phase A and 20261026 for Phase D). Logs and traces stay on the machine that ran them, since `logs/` is never committed.
