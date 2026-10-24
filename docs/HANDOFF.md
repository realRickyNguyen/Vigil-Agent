# Handoff: Vigil: Drug Reaction Review, state as of Fri 23 Oct 2026, afternoon Sydney (early 23 Oct UTC)

Start here if you are picking up the work, whether you are a teammate or a new Claude session. The design and its reasoning are in [ideas/VIGIL.md](ideas/VIGIL.md). Event rules are in [HACKATHON_KNOWLEDGE.md](HACKATHON_KNOWLEDGE.md).

Named **Black Box** until 23 Oct 2026, with agents called Clerk, Hunter and Judge (now Data Clerk, Analyst and Reviewer). Traces and evaluation reports from before the rename keep the old names.

## What it is

Vigil helps a drug-safety analyst decide which reported drug-reaction patterns deserve a closer look, and shows the evidence and objections behind that shortlist. Track 02, "The Agent That Can Explain Why".

Input is a drug name. The app:
1. Registers that drug's public openFDA adverse-event counts and its current label in **Zetaris** at runtime.
2. Computes disproportionality (PRR, chi-squared) in SQL.
3. Lets two Nemotron agents, run through **Meterless Nightshift**, assess the strongest signals. The Analyst proposes; the Reviewer checks in code, then objects, accepts or leaves the item unresolved.
4. Writes a ranked review queue (the dossier) and a full JSONL trace.

## Status

| Area | State |
|---|---|
| Zetaris data layer (Data Clerk) | Built and working. Any drug name is registered at runtime; PRR matches an independent Python check |
| Analyst and Reviewer loop | Built. Last full run: montelukast in 9 minutes on Nemotron Ultra |
| Decision contract v2 | **Done; run live in the 23 Oct evaluation.** It separates label coverage, context and review priority; adds objection and next check per finding; closes disputes as `unresolved`; marks unreached items `pending` or `failed` |
| Evaluation harness | Built: gold sets v1 (22 Oct) and **v2 (23 Oct, current search and label choice; default)**, scorer (`--gold`), runner. Baseline 22 Oct (v1): 93% round-1 and 95% final on clear items, but only 27 of 80 clear items assessed in round 1. **23 Oct evaluation (product fixes, now on `main`)** (`eval/reports/eval-20261023T124957Z.md` against v1, `eval-20261023T125018Z-gold_v2.md` against v2; 6 runs, 22 to 40 min each): against v2, **91% round-1 and 92% final** on clear items (59/65, 60/65); **coverage 56 of 71 clear items in round 1 (79%)** in the five first runs, up from 34%; montelukast repeat-run agreement 0.95. Lost coverage is mostly model failures after every fallback (1 to 3 items per run). The Reviewer kept all 5 wrong answers and fixed none. Wrong items point to two rule bugs and one prompt gap (see next step 4). H-MEM injected memories into 151 of 153 model calls; the scaffold ran in none |
| Meterless Engine (required) | **World Model: built, 13 offline tests, and one live run** (merged into `main` 23 Oct). Live montelukast run 22 Oct 07:54 UTC (`dossier-20261022T075444Z-c885cc`, Bryan's desktop): 15 settled verdicts recorded against the current label version; nothing reopened, as the label had not changed. **Live reopening, Ricky's laptop, 23 Oct:** when the label choice changed to the newest single-ingredient prescription label, each drug's recorded label version changed and the next run reopened the earlier verdicts: montelukast 20260305 to 20260804 (`dossier-20261023T060822Z-0a4c58` then `-111014Z-d9f025`, 16 reopened, 3 of them ended differently), metformin 20260812 to 20260909 (`-073610Z-f89f9f` then `-104749Z-8e7480`, 13 reopened, 5 different, for example BLOOD GLUCOSE DECREASED), atorvastatin 20250828 to 20261015 (`-064207Z-41c6f3` then `-092958Z-a5c8cc`, 13 reopened, 4 different, for example END STAGE RENAL DISEASE unclear to not_found). The version changed because our label choice picked a different label document (new set_id), not because FDA revised a label; say so when showing it. Differences also reflect the new drug search and model variation, not only the label. `app/engines/world_model.py` ports the Meterless reference (stable IDs, merge bands, provenance on every write, idempotent ingest, bitemporal edges, audit order); `tests/test_world_model.py` ports its 8 conformance checks. Our addition: decisions recorded with the facts they rest on. `pipeline.remember()` stores each run's label version and settled verdicts in `state/world-model.json` (gitignored); a later run on a changed label version reopens the earlier verdicts and lists them under `world_model.reopened` in the dossier |
| Skeptic | **On `main` since 24 Oct (merged from `product/fixes`).** Co-reported drug check: for the top 3 accepted review-next items and their top 3 co-drugs, the co-drug's own PRR, this drug's PRR adjusted for the co-drug (Mantel-Haenszel) and the Omega interaction measure (Norén et al., Stat Med 2008; formula checked against the paper's published form). Challenged items go back through the Reviewer and one Analyst revision. Offline tests in `tests/test_skeptic.py`. Reporter type would be a second check. **First live run (montelukast, 23 Oct, `dossier-20261023T045841Z-337e86`, 29 min, about 6.5 of them the Skeptic):** all 9 pair counts matched direct openFDA calls (one within 0.4%, the known serious-flag gap) and the statistics matched an independent recomputation. All 3 items were challenged, but only by the interaction flag, which fired on all 9 pairs: patients on several asthma drugs are sicker, and Omega cannot tell that from an interaction. The Reviewer kept all 3 as review_next. Meanwhile every co-drug's own PRR for wheezing and sputum discoloured was 10 to 52, which points to the disease; the gold set labels both as the treated condition. The interaction flag was then made context only, and a "shared with most co-drugs" challenge added. **Second round, combined drug search, 23 Oct 06:08 to 08:27 UTC** (montelukast `dossier-20261023T060822Z-0a4c58`, atorvastatin `-064207Z-41c6f3`, metformin `-073610Z-f89f9f`): 8 items checked, 1 failed (openFDA HTTP 500 on the co-drug list for atorvastatin end stage renal disease; not retried), 7 challenged. Every count matched direct openFDA calls (one within 0.4%) and every statistic matched an independent recomputation. **Only the adjusted-PRR rule changed outcomes:** atorvastatin chronic kidney disease (PRR 4.84; 70% of reports also name omeprazole; adjusted for omeprazole, pantoprazole or esomeprazole it is 1.5 to 1.8, and those PPIs have CKD PRRs of 34 to 72) went Reviewer reject, Analyst lowered to insufficient_evidence, Reviewer accept; atorvastatin fall (adjusted for aspirin or metoprolol 1.65 to 1.83) was lowered too, but the Reviewer's last call failed, so it shows not_reviewed. **The "shared" rule fired on all 7 challenged items** (all 3 montelukast items, both metformin items, both atorvastatin items) and changed nothing on its own: the Reviewer kept all 3 montelukast items, and both metformin re-reviews failed on Nightshift errors. Against gold, it fired on sputum discoloured (gold: treated condition) but also on full blood count abnormal and metformin hyperkalaemia (gold: possible new signal), so it does not discriminate; the top co-drugs are given to the same patients and share their conditions. **Known issue:** when the Skeptic round's Reviewer call fails, an item accepted in round 1 ends as not_reviewed. **Applied 23 Oct (offline tests only, no live run yet):** "shared" is now context only like the interaction flag, adjusted PRR below 2 is the only trigger, the co-drug list is retried once on an openFDA 5xx, and when the challenge review fails the round-1 verdict stands with a note (`challenge_not_reviewed` count). Next: one live run with Nightshift's memory and reasoning scaffold turned off. Branch rebased on `rename/vigil` 23 Oct; the pre-rename tip is kept as `experiment/skeptic-co-drugs-pre-rename` |
| `SAMPLE_MODE`, Dockerfile, `POST /run`, UI | Not started. `SAMPLE_MODE` needs an organiser answer first (see open questions) |
| README | **Done** (22 Oct): user story, problem, inputs and outputs, why agents, Track 02 mapping, sponsors, results, limitations. Sourced statistics: 23% (Doernberg et al., JAMA Intern Med 2026, checked), about 27,000 alerts and 99.9% closed (GSK, Drug Safety 2026, checked), and FDA's "more than 2 million" reports a year. The exact 2,048,059 from the 2025 OSE report is **not verified**, so it isn't used |
| Team briefing deck | **Done** (23 Oct), internal only: `C:\Users\Ricky\projects\black-box-deck\` on Ricky's laptop, **outside the repo** because it contains licensed BioRender assets and sponsor logos. Contents: `black_box_team_briefing.pptx` and `.pdf`, `speaker_notes.md` (plain-language notes, the source), `build_deck.ps1` (rebuild with the research-deck skill). 13 slides: track, why it matters, user, proposal, why agents, workflow diagram, sponsor tools, progress checklist, submission, video plan, summary |
| Submission deck, video, `metadata.json` | Not started. Build the submission deck from the team briefing; the required contents are in `HACKATHON_KNOWLEDGE.md` |

Git: branch `main`. Key commits: `bf4f2c1` (first working loop, 22 Oct 15:50 Sydney) and `d3d9394` (contract v2, evaluation harness, docs). On 23 Oct Bryan's `feature/world-model` and `fix/nightshift-connection-reset` branches were merged into `main` and pushed. Later on 23 Oct, also pushed: the combined drug search from Bryan's issue (`fix/combined-drug-search`, merged), full prompts and replies in the trace (`feature/full-trace`, merged), Nightshift memory and scaffold recorded per call (`44c9bb4`), and the rename to Vigil (`e7ead70`; 55 offline tests pass). **After pulling:** `hunter.py` is now `analyst.py` and `judge.py` is `reviewer.py`; rebase any open branch, and expect conflicts in agent files. An older `.env` with `HUNTER_MODEL`, `JUDGE_MODEL` or `JUDGE_ROUNDS` still works. On 24 Oct (Sydney) `product/fixes` was merged into `main` locally: the Skeptic, splitting batches at Nightshift's deadline, label choice, combination share, the selection rule, gold set v2 and the 23 Oct evaluation (74 offline tests pass). **Not yet pushed.** Private GitHub repo for the team since 22 Oct: https://github.com/realRickyNguyen/genai_hackathon (`origin`). Teammate setup is in [TEAM_SETUP.md](TEAM_SETUP.md). Run traces and dossiers in `logs/` are gitignored; final ones go into `output_examples/` for submission (next step 8).

Tools: the team does not use Cursor (decided 23 Oct, after the organisers made it optional). Development is done with Claude Code, which reads `CLAUDE.md`; `AGENTS.md` carries the same rules for any other coding agent.

## How to run

**Start the services** (the "lets begin" routine in [../CLAUDE.md](../CLAUDE.md)):
- Docker Desktop
- `docker compose up -d` in `~/zetaris-platform` (WSL Ubuntu)
- Nightshift

**Check Nightshift after every restart.** A restart re-seats lanes from its saved `lanes.toml`. The working setup is:
- NIGHT › LANES: the first lane runs `nvidia/nemotron-3-ultra-550b-a55b` (its card still shows the old ID `nemotron-3-super-120b-a1`). The **Lightning lane is stopped**.
- Setup › PREFERENCES: **race width 1**.
- Why: racing two lanes made pinned model IDs meaningless, and an empty reply from one lane failed the whole request. The Super model itself returns NVIDIA 404 for this key.
- Setup › PREFERENCES › Quality track: **Reasoning scaffold off** (set 23 Oct; saved in `%LOCALAPPDATA%i.meterless.runtime\state\setpoints.json` with race width 1). Answer fusion, Answer judging and Best-of-N are still `auto`; set them off too, because if a restart returns race width to 6 they would merge or judge several lanes' answers.
- **Why restarts bring Lightning back:** the active fleet is "Imported" (`fleet-state.json` → `imported-v2` in `fleets.toml`), a 22 Oct snapshot with the old Super ID (404 for our key) and Lightning, both autostart and racing. Fix: set the lanes as wanted and save them as a custom fleet, then activate it.
- **H-MEM memory cannot be switched off as far as we know** (no setting found in the app, its files or the organiser guide). It injected 2 to 3 earlier answers into 32 of 34 calls on 23 Oct, after our app sends the prompt, so the injected text is not in our trace. Since 23 Oct every `llm_call` trace event has a `nightshift` field from the receipt Nightshift returns inline (memories injected and their IDs, scaffold state, phases, context sources), and each dossier counts it under `model_calls`. Ask the organisers whether H-MEM can be disabled per app.

Then, from the repo root:

```bash
python -I scripts/smoke_test.py
```
Expect 3 PASS.

```bash
python -I -m pytest tests -q
```
Offline tests, no services needed.

```bash
python -I run.py --drug montelukast
```
One investigation. Writes `logs/trace-<run>.jsonl` and `logs/dossier-<run>.json`.

```bash
python -I eval/run_eval.py
```
All 5 gold drugs, plus 2 extra montelukast runs: about 60 to 75 minutes.

```bash
python -I eval/run_eval.py --score-only <run_id> <run_id>
```
Re-scores existing runs with no model calls.

The shared Zetaris baseline must exist once per Zetaris install:

```bash
python -I scripts/zetaris/run_sql.py scripts/zetaris/openfda_baseline.sql
```

## Code map

| Path | What it does |
|---|---|
| `run.py` | CLI entry point; prints the review queue |
| `app/config.py` | Settings from `.env`. Defaults: Ultra for both agents, 2 parallel model calls, 2 revision rounds |
| `app/adapters/zetaris.py` | Zetaris REST client: retries, short query IDs for evidence, every query traced |
| `app/adapters/meterless.py` | Nightshift client: required headers, retries (including dropped connections), `fail_fast` on the provider deadline for batches, `served_by` and Nightshift receipt logging (H-MEM, scaffold), JSON extraction (handles Ultra's inline `</think>`) |
| `app/data/faers.py` | The Data Clerk: registers openFDA tables per drug (two-field `drug_search`), signal SQL, label choice (`choose_label`), combination share, the Skeptic's co-drug and pair counts |
| `app/data/label.py` | Label helpers: per-reaction sentence retrieval, literal term lookup |
| `app/agents/rules.py` | Code routing for easy cases: administrative terms, treated condition, literal label match |
| `app/agents/analyst.py` | Analyst: the top 15 rows by chi2 plus up to 5 of its own picks, then classify in batches of 3 with fallbacks |
| `app/agents/reviewer.py` | Reviewer: code checks first, then model review in batches; objection and next check per finding |
| `app/orchestration/pipeline.py` | The loop, dispute settling (`settle`), Skeptic round (`skeptic_round`), review queue and counts, World Model record (`remember`), dossier |
| `app/agents/skeptic.py` | Skeptic: co-drug ranking (salts merged), adjusted PRR, co-drug PRR, Omega, outcome rule |
| `app/engines/world_model.py` | Meterless World Model engine (Python port of the reference) plus decisions that reopen when a fact they rest on changes |
| `app/schemas.py` | `Finding` (contract v2), `Verdict`, `Signal`, status constants |
| `app/tracing.py` | Append-only JSONL trace, thread-safe |
| `scripts/zetaris/` | Baseline SQL and a runner that sends `.sql` files through the REST API |
| `eval/` | Gold set, labelling rules, scorer, runner, backtest feasibility notes |
| `tests/` | Offline tests: app logic, scorer and World Model conformance |
## Rules to keep (from the hackathon and from what broke)

- **Secrets only in `.env`.** Never print them. The NVIDIA key lives inside Nightshift only.
- **Never edit `logs/`.** Traces and dossiers are evidence. Never load `output_examples/` at runtime, and never match known inputs to stored answers.
- **Every number an agent cites must come from a Zetaris query ID in the trace.** The Reviewer's code checks enforce this; do not weaken them to make a run pass.
- **Keep model calls small.** Large prompts on Nightshift time out or come back empty. Batches of 3 and per-reaction label excerpts are deliberate.
- **Do not overclaim.** FAERS shows reporting patterns, not causation. Say "review next", not "new side effect". Gold accuracy is a development check labelled by an AI, not clinical validation.
- **No Cursor claims.** The team does not use Cursor. Do not say it did any work in the README, deck or `metadata.json`.

## Known issues

- **Fixed 23 Oct: label choice.** The Data Clerk fetches the 10 newest labels (`label_d2_<slug>_raw`, sorted by `effective_time`) and `choose_label()` takes the newest single-ingredient prescription label. Metformin used to get ZITUVIMET (sitagliptin + metformin). The 22 Oct gold labels for metformin were made against that combination label, so metformin scores need care until a person re-checks them.
- **Combination products** are recorded per run (`combination_products` in the dossier): about 1% of atorvastatin's reports, 7% of metformin's (a lower bound) and 47% of acetaminophen's. Above 5% both agents are told a reaction may belong to the partner drug, and the Skeptic marks co-drugs sold in one product with the drug.
- **Fixed 23 Oct: the drug search used openFDA's `generic_name` alone,** which openFDA fills only when it can match the product record. Bryan showed against FDA's raw quarterly files that it found 39% of atorvastatin's reports (46% levothyroxine, 87% metformin, 99%+ montelukast). `drug_search()` now uses `generic_name` OR `activesubstance.activesubstancename` (atorvastatin through Zetaris: 249,468 to 519,224 reports), with new table names (`faers_d2_<slug>_…`) because old REST tables cannot be dropped. The 22 Oct evaluation used the old search; re-run it before quoting numbers. Combination products are included by both fields (46% of acetaminophen's reports, 12% of metformin's).
- **The drug search counts every report that mentions the drug, not only those where it was the suspect.** This broadens the report set; it is not the same as inflating the PRR.
- **The baseline covers only the 999 most-reported reactions** (openFDA's no-key limit, which we tested). Rarer reactions are not screened.
- **Per-drug Zetaris REST tables cannot be deleted through SQL.** They pile up in `openfda_rest`. Remove them in Data Explorer if needed.
- **The total uses the sum of the serious-flag counts,** which is about 0.05% below openFDA's report total.
- **Montelukast is not a clean "caught it early" backtest:** its warnings were in the precautions by 2012. openFDA also returns only the latest version of each case, so date filters do not reconstruct the past. The backtest is off the critical path; see `eval/BACKTEST_FEASIBILITY.md`.
- **Run time:** 9 minutes on 22 Oct, 30 to 55 minutes on 23 Oct, mostly Nightshift provider_deadline failures (43 in one run) plus H-MEM and the scaffold. Since 23 Oct a multi-item batch that hits the deadline is split at once instead of retried (`fail_fast`), and the scaffold is off in Nightshift.

## Context from 22 to 23 Oct

- **Outside review.** An outside LLM panel scored the design 50/100. Its main points, which the next steps follow:
  - Pitch it as a review shortlist, not as discovering side effects.
  - Separate label coverage, priority and workflow status (done in contract v2).
  - Build one minimal World Model with a behaviour test.
  - Add one evidence-seeking Skeptic step.
  - Drop the montelukast "caught it early" backtest.

  The review file is on Ricky's laptop (`Downloads\BLACK_BOX_PANEL_REVIEW.md`), not in the repo.
- **Ricky's laptop disk** filled up on 22 Oct. Cleanup so far:
  - Cursor's install was cancelled. Cursor was later dropped by the whole team (23 Oct).
  - Nightshift's local Llama models went to the Recycle Bin.
  - Five unused Docker images and the build cache were removed.

  Space returns only after `scripts/compact-wsl-disks.ps1` runs as administrator with Docker quit, and after the Recycle Bin is emptied. Check C: free space before large runs.
- **Services** were stopped at the end of 22 Oct. Use the "lets begin" routine in `CLAUDE.md`, then check that the Nightshift lanes are still Ultra-only.

## Next steps, in order

**Agent-system queue, 24 Oct (Ricky's order: finish the agent system, then demo and UX).** Work through these in order after the three-drug re-run on `fix/eval-logic` finishes:
1. Report the re-run scores against gold v2 (sertraline, metformin, montelukast; all fixes from 24 Oct).
2. **Run time to 5 to 10 minutes** (organisers' target): one reaction per model call for the Analyst and Reviewer (3-reaction batches pass Nightshift's ~50 s `provider_deadline`; 125 of 132 failed attempts on 23 Oct were that deadline, 7 were NVIDIA 429s); 4 parallel calls instead of 2 (calls overlap without slowing); model timeout 90 s and one retry (`.env` has `MAX_RETRIES=2`, change to 1); a whole-run time budget that skips the revision round and Skeptic when it runs low and marks their items `pending`; the extra-pick call alongside classifying the top 15; the Skeptic's items and the Data Clerk's label, combination and seriousness queries in parallel.
3. **Readable progress lines on stdout** for every step and every model call (agent, model that served it, seconds), next to the JSONL trace.
4. Tests, docs, commit; then a **timed live run with Ultra** to confirm 5 to 10 minutes.
5. **Nemotron role test** (also the NVIDIA award's "technical depth"): Nemotron 3 Super 120B A12B as the Analyst, Ultra as the Reviewer, scored on gold against all-Ultra. Needs Ricky to add a Super lane (race width 1, Lightning stopped). Super is reported to be unreliable, so test it, and drop it if it fails often.
6. **Timing test: the whole label for the Reviewer** instead of 3 retrieved sentences (Ultra has a 1M-token context; retrieval misses caused real errors). Keep only if calls stay under the deadline.
7. **World Model read by the agents:** earlier settled verdicts and reopened items go into the Analyst's and Reviewer's prompts, and the engine's audit entries go into the run's trace.
8. A final clean evaluation run on the finished system, then merge `fix/eval-logic` into `main` (ask before pushing).

**Progress, 24 Oct afternoon.** (1) Re-run done (`eval/reports/eval-20261024T054159Z-gold_v2.md`): **worse**, 80% round-1 and 76% final on the three drugs, against 88% and 90% for the same drugs on 23 Oct. Cause, from the Analyst's own reasoning: with serious and death shares in its table it escalated treated-disease terms ("High reporting (PRR 7.03) with 93% serious and 7% death") to review_next, 16 such items for metformin. Fixed in `4e5aad3`: the shares stay in the pick step and the dossier but no longer reach the classification or review prompts. Also found: retrieval tied "blood" and "hypoglyc" on metformin's real label and showed lactate sentences; synonym words now count double (checked on the real label). Sertraline ANXIETY and PANIC ATTACK: the gold evidence is not in any section the app keeps; flagged in `eval/LABELLING_RULES.md`. (2 to 4) Run-time changes made, offline tests pass (94); timed run pending.

After that: demo and UX (investigation page, `POST /run`, Dockerfile, `SAMPLE_MODE`, samples, deck, video).

1. **Organiser questions** (below). The Track 02 challenge statement on HackOS is the generic track text (confirmed 24 Oct); nothing more to read.
2. **Evaluation:** done 23 Oct with the product fixes now on `main` (see the status table). A person still needs to review gold v1 and v2 before any number is quoted publicly.
3. **World Model engine:** merged into `main` on 23 Oct, with offline tests, and reopening shown live on 23 Oct (see the status table). Counts for the Build rule: the 19 Oct setup guide (section 3.2 and "Verify your Build setup") asks for the engine implemented in your own application, in any language, with "the engine's relevant conformance suite, evaluation, or a reproducible feature test" passing. For the submission: name the engine, say what it does here, show the feature and the test result.
4. **Fixes the 23 Oct evaluation points to** (made 24 Oct on `fix/eval-logic`, commit `b383be8`: social-circumstance terms go aside by rule; a reaction named in both the indications and a safety section, or only in the contraindications, goes to the model; the Analyst and Reviewer prompts check coverage for treated conditions and do not count a contraindication as coverage. Live re-run of sertraline, metformin and montelukast pending; two attempts on 24 Oct failed on openFDA HTTP 500/502 before any agent ran). **Also 24 Oct, from the outside review in `docs/reviews/astra-high-review-2026-10-24.md` (each claim checked against the code first):** the Reviewer's `not_found` check ignores the contraindications (it had contradicted the fix above); a finding missing from the Reviewer's reply, or with an unknown decision, is `not_reviewed` instead of accepted; a reaction missing from the Analyst's reply is retried alone, then marked failed, instead of vanishing; label quotes are cut around the term, so they always contain it (metformin DIARRHOEA's did not); retrieval adds label words for common lab terms (BLOOD GLUCOSE DECREASED finds hypoglycemia); both prompts forbid comparing FAERS counts with incidence; exposure during pregnancy or breastfeeding gets a pregnancy-outcome next check instead of "none needed"; the Skeptic's "holds" is now `no_challenge`, and co-drugs that cut the PRR by 30% or more without going below 2 are listed as `attenuated_by` (context). **Seriousness per reaction:** one Zetaris query joins two openFDA counts (the drug's reactions among serious reports and among death reports) to the screen; the agents see serious and death shares in their tables and the dossier shows them per item. Ranking is unchanged. Checked live for montelukast (999 reactions): the serious share is 68 to 99% for nearly every row, so it separates little; the death share varies more (1.3 to 5%). The flags describe the whole report. 89 offline tests pass. Two gold rows the review disputed are flagged for the human review in `eval/LABELLING_RULES.md`; the gold files are unchanged: (a) the indication rule routed sertraline ANXIETY as the treated condition because the indications name social anxiety disorder, although adverse reactions list anxiety; (b) the literal-match rule called metformin DIABETIC KETOACIDOSIS on-label because the contraindications name it, which is not a drug effect; (c) the Analyst prompt tells it to mark a treated condition `not_assessed`, so it never checks whether the label says the drug can cause or worsen it (metformin BLOOD GLUCOSE DECREASED, the hypoglycaemia warning); (d) montelukast LOSS OF PERSONAL INDEPENDENCE IN DAILY ACTIVITIES, a MedDRA social-circumstance term, was sent as review next in both runs. Selection is done: the 15 strongest rows by chi2 plus up to 5 Analyst picks.
5. **Skeptic:** on `main` since 24 Oct. In the 23 Oct evaluation it checked 14 items and challenged only atorvastatin's three kidney and fall items (adjusted PRR below 2 for PPIs, aspirin, metoprolol): chronic kidney disease and fall were lowered to insufficient evidence, end stage renal disease ended unresolved. It challenged nothing for the other drugs. Reporter type could follow as a second check. It provides context, never proof.
6. **One investigation page:** ranked queue, coverage counts, evidence expansion.
7. **Submission package** (checklists in `docs/reference/submission-requirements.md` section 8 and `technical-execution-requirements.md` section 13): README, Dockerfile, `POST /run`, samples, video, deck (eight required points), sponsor technology explanation, and a fresh-clone test.
8. **Evidence for judges:** `logs/` is gitignored, so judges see no traces unless we publish them. Once the system is final, run each sample drug on it, then copy the chosen `trace-<run>.jsonl` and `dossier-<run>.json` **unedited** into `output_examples/` and point to them from the README. The app never reads `output_examples/`. Since 23 Oct every `llm_call` event holds the full prompt messages and the raw reply (including Ultra's inline reasoning), so a reader can see exactly what each agent was shown and answered. Traces made before that hold only sizes and a prompt hash, so publish only traces from the final system.

## Open questions for the organisers

All answered by the organisers' documents (copied into `docs/reference/` on 24 Oct):
1. **Sample mode:** recommended, not a rule, but the organisers' readiness test runs `SAMPLE_MODE=true` with Zetaris and Nightshift stopped and no network (`technical-execution-requirements.md` sections 5 and 11). So it needs recorded openFDA results and recorded model replies, clearly labelled as a replay.
2. **Cursor:** optional; the sponsor explanation mentions it only "if you built with Cursor". We did not.
3. **Python engine:** accepted. The 19 Oct setup guide (section 3.2) asks for the engine in your own application, verified by its conformance suite or a reproducible feature test.
4. **`metadata.json`:** not asked for. The submission form takes the project name, description, team, track and declared pre-existing components.

New targets from `technical-execution-requirements.md`: a full run in 5 to 10 minutes (ours take 20 to 40), model calls bounded at 30 to 90 s (ours: 180 s timeout plus retries), readable progress lines on stdout as well as the JSONL trace, `POST /run` returning JSON with `status`, `trace_id`, `log_file`, `execution_time_seconds` and a structured error on failure, and Docker reaching Zetaris and Nightshift through `host.docker.internal`.
