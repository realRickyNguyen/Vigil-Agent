# Handoff: Vigil: Drug Reaction Review, state as of Sun 25 Oct 2026, evening Sydney

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
| Analyst and Reviewer loop | Built. Timed runs on 24 Oct (`fix/eval-logic`, buffered calls): 8 to 13 minutes per drug at `MODEL_PARALLEL=4`, bounded by NVIDIA's trial rate. Bryan's branch on 24 Oct (streamed calls, before our run-time changes): 8 to 11 minutes per run, 78 of 82 model call attempts succeeded. Both are merged on `fix/eval-logic` since 25 Oct. One live run of the merged code (before PR #11's follow-ups), through Docker on 25 Oct: 587 s, see the to-do item 2. **At the code defaults in the 25 Oct re-evaluation**, with no `.env` settings, `main`'s runs took {{A_R2_time}} and task 2's {{B_R3_time}} (`03_Project_context/Vigil_Reevaluation_RickyDefaults_25Oct.md`). {{C_handoff_note}} |
| Evaluation harness | Built: gold sets v1 (22 Oct) and **v2 (23 Oct, current search and label choice; default)**, scorer (`--gold`), runner. **The current numbers are the 25 Oct re-evaluation at Ricky's code defaults** (`03_Project_context/Vigil_Reevaluation_RickyDefaults_25Oct.md`, gold v2, one run per drug, one scorer). Final answers agreed on {{A_R2_final}} clear items on `main` and {{B_R3_final}} with task 2, against {{A_R0_final}} on Ricky's code before our pushes (`083b669`). Everything after this in the row was measured with H-MEM on or with Bryan's `.env` (2 parallel calls, 2 revision rounds), and is superseded. **Every evaluation on Ricky's laptop before 25 Oct ran with Nightshift's H-MEM injecting earlier answers into every model call** (checked 25 Oct: every call in the 8 latest traces), so those numbers partly measure replayed answers: 22 Oct baseline (v1) 93% round-1 and 95% final, 27 of 80 clear items assessed; 23 Oct (`eval-20261023T125018Z-gold_v2.md`) 91% and 92%; 24 Oct timed runs on three drugs (`eval-20261024T072538Z-gold_v2.md`) 86% and 84%. **Bryan's 24 Oct evaluation, memory off and streaming** (`eval/reports/eval-20261024T022640Z.md`, his branch before the merge): 93% round-1 (26 of 28) and 89% final (49 of 55) on clear items; rules 27 of 27, model 22 of 28; montelukast repeat agreement 0.95. Of its 6 final errors, 3 are gold rows whose evidence the newer labels no longer contain (metformin acute kidney injury and acute renal failure, sertraline panic attack), 2 are judgement calls (metformin metabolic acidosis, sertraline intentional self-injury) and 1 is a model error (metformin diabetic ketoacidosis via the contraindication, since fixed). **Bryan's consolidated build** (`fix/consolidated-24-oct` at `9e6d382`, memory off, streaming, gold v2, 2 parallel calls, `eval/reports/eval-20261024T125052Z-gold_v2.md`) agreed on 58 of 58 final clear items counting each drug once, and 77 of 77 over 7 runs. Those items are mostly label lookups, and 1 of its 27 review-next entries is a clear gold new signal. Quote none of these publicly before the gold review |
| Decision contract v2 | **Done; run live in the 23 Oct evaluation.** It separates label coverage, context and review priority; adds objection and next check per finding; closes disputes as `unresolved`; marks unreached items `pending` or `failed` |
| Meterless Engine (required) | **World Model: built, 13 offline tests, and one live run** (merged into `main` 23 Oct). Live montelukast run 22 Oct 07:54 UTC (`dossier-20261022T075444Z-c885cc`, Bryan's desktop): 15 settled verdicts recorded against the current label version; nothing reopened, as the label had not changed. **Live reopening, Ricky's laptop, 23 Oct:** when the label choice changed to the newest single-ingredient prescription label, each drug's recorded label version changed and the next run reopened the earlier verdicts: montelukast 20260305 to 20260804 (`dossier-20261023T060822Z-0a4c58` then `-111014Z-d9f025`, 16 reopened, 3 of them ended differently), metformin 20260812 to 20260909 (`-073610Z-f89f9f` then `-104749Z-8e7480`, 13 reopened, 5 different, for example BLOOD GLUCOSE DECREASED), atorvastatin 20250828 to 20261015 (`-064207Z-41c6f3` then `-092958Z-a5c8cc`, 13 reopened, 4 different, for example END STAGE RENAL DISEASE unclear to not_found). The version changed because our label choice picked a different label document (new set_id), not because FDA revised a label; say so when showing it. Differences also reflect the new drug search and model variation, not only the label. `app/engines/world_model.py` ports the Meterless reference (stable IDs, merge bands, provenance on every write, idempotent ingest, bitemporal edges, audit order); `tests/test_world_model.py` ports its 8 conformance checks. Our addition: decisions recorded with the facts they rest on. `pipeline.remember()` stores each run's label version and settled verdicts in `state/world-model.json` (gitignored); a later run on a changed label version reopens the earlier verdicts and lists them under `world_model.reopened` in the dossier |
| Skeptic | **On `main` since 24 Oct (merged from `product/fixes`).** Co-reported drug check: for the top 3 accepted review-next items and their top 3 co-drugs, the co-drug's own PRR, this drug's PRR adjusted for the co-drug (Mantel-Haenszel) and the Omega interaction measure (Norén et al., Stat Med 2008; formula checked against the paper's published form). Challenged items go back through the Reviewer and one Analyst revision. Offline tests in `tests/test_skeptic.py`. Reporter type would be a second check. **First live run (montelukast, 23 Oct, `dossier-20261023T045841Z-337e86`, 29 min, about 6.5 of them the Skeptic):** all 9 pair counts matched direct openFDA calls (one within 0.4%, the known serious-flag gap) and the statistics matched an independent recomputation. All 3 items were challenged, but only by the interaction flag, which fired on all 9 pairs: patients on several asthma drugs are sicker, and Omega cannot tell that from an interaction. The Reviewer kept all 3 as review_next. Meanwhile every co-drug's own PRR for wheezing and sputum discoloured was 10 to 52, which points to the disease; the gold set labels both as the treated condition. The interaction flag was then made context only, and a "shared with most co-drugs" challenge added. **Second round, combined drug search, 23 Oct 06:08 to 08:27 UTC** (montelukast `dossier-20261023T060822Z-0a4c58`, atorvastatin `-064207Z-41c6f3`, metformin `-073610Z-f89f9f`): 8 items checked, 1 failed (openFDA HTTP 500 on the co-drug list for atorvastatin end stage renal disease; not retried), 7 challenged. Every count matched direct openFDA calls (one within 0.4%) and every statistic matched an independent recomputation. **Only the adjusted-PRR rule changed outcomes:** atorvastatin chronic kidney disease (PRR 4.84; 70% of reports also name omeprazole; adjusted for omeprazole, pantoprazole or esomeprazole it is 1.5 to 1.8, and those PPIs have CKD PRRs of 34 to 72) went Reviewer reject, Analyst lowered to insufficient_evidence, Reviewer accept; atorvastatin fall (adjusted for aspirin or metoprolol 1.65 to 1.83) was lowered too, but the Reviewer's last call failed, so it shows not_reviewed. **The "shared" rule fired on all 7 challenged items** (all 3 montelukast items, both metformin items, both atorvastatin items) and changed nothing on its own: the Reviewer kept all 3 montelukast items, and both metformin re-reviews failed on Nightshift errors. Against gold, it fired on sputum discoloured (gold: treated condition) but also on full blood count abnormal and metformin hyperkalaemia (gold: possible new signal), so it does not discriminate; the top co-drugs are given to the same patients and share their conditions. **Known issue:** when the Skeptic round's Reviewer call fails, an item accepted in round 1 ends as not_reviewed. **Applied 23 Oct (offline tests only, no live run yet):** "shared" is now context only like the interaction flag, adjusted PRR below 2 is the only trigger, the co-drug list is retried once on an openFDA 5xx, and when the challenge review fails the round-1 verdict stands with a note (`challenge_not_reviewed` count). Next: one live run with Nightshift's memory and reasoning scaffold turned off. Branch rebased on `rename/vigil` 23 Oct; the pre-rename tip is kept as `experiment/skeptic-co-drugs-pre-rename` |
| Task 2 (clinical reliability) | **On `main` from the 25 Oct final PR.** The label search across every fetched section, report sources for review-next items, uncertainty and scope marks, the manual-review flag, the serious-term safety net in clinical order, and rule fixes. Details and the decisions left open are in `03_Project_context/Vigil_Task2_Clinical_Reliability.md` |
| `POST /run` and Dockerfile | **Built 25 Oct, on `main` since 25 Oct** (`app/server.py`, `Dockerfile`). `python -I run.py` with no arguments starts the API: `POST /run` (bare `{"drug"}` or the organisers' envelope; waits by default, `options.wait=false` returns 202), `GET /runs/<run_id>`, `GET /health`; one run at a time (`Busy`, 409); structured errors with type and `recoverable`. The image (207 MB, no secrets) rewrites `localhost`/`127.0.0.1` to `host.docker.internal`, and settings drop inline comments and quotes that `docker run --env-file` keeps. Checked live: every error path from the host and from the container. **Full run through Docker, 25 Oct 05:56 UTC** (the organisers' test: `curl -X POST /run -d @input_examples/example_1.json`, montelukast, `dossier-20261025T055628Z-3ae747`): HTTP 200 in 587 s; the container reached Zetaris and Nightshift via `host.docker.internal`; 23 assessed (7 by rule), 23 reviewed, 4 review next, 3 pending; the budget skipped only the Skeptic's challenge review (14 s left) |
| `SAMPLE_MODE`, UI | Not started. `POST /run` answers `SampleModeNotImplemented` (501) until `SAMPLE_MODE` exists |
| README | **Done** (22 Oct): user story, problem, inputs and outputs, why agents, Track 02 mapping, sponsors, results, limitations. Sourced statistics: 23% (Doernberg et al., JAMA Intern Med 2026, checked), about 27,000 alerts and 99.9% closed (GSK, Drug Safety 2026, checked), and FDA's "more than 2 million" reports a year. The exact 2,048,059 from the 2025 OSE report is **not verified**, so it isn't used |
| Team briefing deck | **Done** (23 Oct), internal only: `C:\Users\Ricky\projects\black-box-deck\` on Ricky's laptop, **outside the repo** because it contains licensed BioRender assets and sponsor logos. Contents: `black_box_team_briefing.pptx` and `.pdf`, `speaker_notes.md` (plain-language notes, the source), `build_deck.ps1` (rebuild with the research-deck skill). 13 slides: track, why it matters, user, proposal, why agents, workflow diagram, sponsor tools, progress checklist, submission, video plan, summary |
| Submission deck, video, `metadata.json` | Not started. Build the submission deck from the team briefing; the required contents are in `HACKATHON_KNOWLEDGE.md` |

Git: branch `main`. Key commits: `bf4f2c1` (first working loop, 22 Oct 15:50 Sydney) and `d3d9394` (contract v2, evaluation harness, docs). On 23 Oct Bryan's `feature/world-model` and `fix/nightshift-connection-reset` branches were merged into `main` and pushed. Later on 23 Oct, also pushed: the combined drug search from Bryan's issue (`fix/combined-drug-search`, merged), full prompts and replies in the trace (`feature/full-trace`, merged), Nightshift memory and scaffold recorded per call (`44c9bb4`), and the rename to Vigil (`e7ead70`; 55 offline tests pass). **After pulling:** `hunter.py` is now `analyst.py` and `judge.py` is `reviewer.py`; rebase any open branch, and expect conflicts in agent files. An older `.env` with `HUNTER_MODEL`, `JUDGE_MODEL` or `JUDGE_ROUNDS` still works. On 24 Oct (Sydney) `product/fixes` was merged into `main` locally: the Skeptic, splitting batches at Nightshift's deadline, label choice, combination share, the selection rule, gold set v2 and the 23 Oct evaluation (74 offline tests pass); `main` was pushed on the evening of 24 Oct. **25 Oct (Sydney): everything is on `main`** (`536c2fb`, pushed): 24 Oct's agent work (`fix/eval-logic`), Bryan's PR #10 and PR #11 follow-ups, and the API and Dockerfile (`feature/api-docker`); 157 offline tests pass. **Pull `main` and start every new branch from it**; `fix/eval-logic`, `feature/api-docker` and Bryan's 23 to 25 Oct branches are done and need no further work. Since 24 Oct the `.env` defaults are: `MAX_RETRIES=1`, `MODEL_PARALLEL=4`, `MODEL_TIMEOUT_SECONDS=90`, `REVIEWER_ROUNDS=1`, `RUN_BUDGET_SECONDS=600` (see `.env.example`). Private GitHub repo for the team since 22 Oct: https://github.com/realRickyNguyen/genai_hackathon (`origin`). Teammate setup is in [TEAM_SETUP.md](TEAM_SETUP.md). Run traces and dossiers in `logs/` are gitignored; final ones go into `output_examples/` for submission (next step 8).

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
- **H-MEM is kept out by the app since 24 Oct.** Nightshift walls its memory by the `meterless-scope` header (its `hmem.js` describes "hard per-`scope` isolation on write AND read"), and the app sent `user` on every call, so each call got up to 3 earlier answers. It now sends a fresh scope per call. A new `meterless-app` name does not isolate memory (tested). Nightshift's code also reads global settings (`hmemKnowledge`, `hmemTopK`), but those would change only one machine. Since 23 Oct every `llm_call` trace event has a `nightshift` field from the receipt Nightshift returns inline (memories injected and their IDs, scaffold state, phases, context sources), and each dossier counts it under `model_calls`, so a run shows that none were injected.

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
One investigation. Writes `logs/trace-<run>.jsonl` and `logs/dossier-<run>.json`. `python -I run.py` with no arguments starts the API on port 8000; `docker build -t vigil .` then `docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/logs:/app/logs" -v "$(pwd)/state:/app/state" vigil` runs it in Docker (README, Run it).

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
| `run.py` | Entry point: no arguments starts the API (`app/server.py`); `--drug` or `--input` runs one investigation and prints the review queue |
| `app/server.py` | HTTP API (standard library): `POST /run`, `GET /runs/<run_id>`, `GET /health`; one run at a time; maps exceptions to structured errors |
| `Dockerfile`, `.dockerignore` | Image for judges; secrets only at `docker run`; `logs/` and `state/` as mounts |
| `app/config.py` | Settings from `.env`. Defaults: Ultra for both agents, 4 parallel model calls, 1 revision round, 90 s per call, 1 retry, a 600 s budget |
| `app/adapters/zetaris.py` | Zetaris REST client: retries, short query IDs for evidence, every query traced |
| `app/adapters/meterless.py` | Nightshift client: required headers, retries (including dropped connections), `fail_fast` on the provider deadline for batches, `served_by` and Nightshift receipt logging (H-MEM, scaffold), JSON extraction (handles Ultra's inline `</think>`) |
| `app/data/faers.py` | The Data Clerk: registers openFDA tables per drug (two-field `drug_search`), signal SQL, label choice (`choose_label`), combination share, the Skeptic's co-drug and pair counts |
| `app/data/label.py` | Label helpers: per-reaction sentence retrieval, the code search of every fetched section (`search`) |
| `app/agents/rules.py` | Code routing for easy cases: administrative terms, treated condition, a name in the safety sections |
| `app/data/sources.py` | Report sources for review-next items (country and reporter flags, context only) |
| `app/data/uncertainty.py` | Expected count, PRR interval, IC025 and the thin-evidence mark for each screened row |
| `app/data/safety_net.py` | Serious-term safety net outside the screen and the queue, for a person to review |
| `app/orchestration/manual_review.py` | The "needs manual review" flag, by the rules in `eval/MANUAL_REVIEW_RULES.md` |
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
- **Keep model calls small.** Large prompts on Nightshift time out or come back empty. **Keep `MODEL_STREAM=true`**, because buffered calls are cut at 45 s. Batches of 3 and per-reaction label excerpts are deliberate.
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
- **Run time:** 9 minutes on 22 Oct; 30 to 55 minutes on 23 Oct (mostly buffered calls cut at 45 s, plus H-MEM and the scaffold); 8 to 13 minutes on 24 Oct after the run-time changes on `fix/eval-logic` (bounded by NVIDIA 429s). Since the 25 Oct merge calls are streamed (below), with `MODEL_TIMEOUT_SECONDS` (90) as the limit on a whole call. At the code defaults in the 25 Oct re-evaluation, `main`'s runs took {{A_R2_time}} (`03_Project_context/Vigil_Reevaluation_RickyDefaults_25Oct.md`).
- **Nightshift's H-MEM replayed earlier answers, which the model treated as vetted** (fixed 24 Oct). With memory on, all four montelukast runs on 23 and 24 Oct marked obstructive airways disorder and dyspnoea as signals to review, repeating an answer first made on 22 Oct. In one run, 10 of the 20 texts the model wrote repeated earlier runs word for word, and the Reviewer reasoned "The prior vetted answer also said clinical_event" before accepting. With a fresh scope per call, `main`'s own prompts got all three airway items right (6 of 7 in round 1, 7 of 8 final). The 23 Oct repeat-run agreement (0.93) also reflects the replay.
- **Most `provider_deadline` failures came from buffered calls** (fixed 24 Oct). Nightshift aborts its NVIDIA fetch when no response headers arrive within 45 s (`CLOUD_FETCH_DEADLINE_MS` in its `providers.js`; no setting or request field changes it). A buffered (`stream: false`) reply sends no headers until the whole answer is written, so any reply Ultra needs more than 45 s for failed. In Nightshift's receipts that was 376 of 390 failures to 24 Oct. The client now streams (`MODEL_STREAM=true`, the default), which gets headers at once. Nightshift still runs two steps buffered even for a streamed request, and both can still hit the 45 s cut. One is its own fallback after a failed first attempt. The other is the whole answer when its quality lane is on (difficulty 0.6 or more, about half of our calls). The client also sends `meterless-tier-split: off`, which stops the buffered planning phase and Nightshift's "plan only" or "diff only" system prompts (Nightshift ignores our model pin, so these applied to our calls). Setting `"qualityRace": "off"` and `"reasoningScaffold": "off"` in Nightshift's `state/setpoints.json` (then restart Nightshift) removes the quality lane; done on Bryan's PC on 24 Oct, and every teammate's Nightshift needs the same. At race width 1 the quality lane has only one answer to choose from. In a live A/B on 24 Oct, the same real Reviewer prompt ran 10 times each way. Buffered calls succeeded 0 of 10 times (all `provider_deadline` at 50 s), and streamed calls 10 of 10, with valid JSON and a median of 130 s per call. Ultra runs at about 15 to 34 tokens/s on NVIDIA and about 77% of each reply is reasoning, so calls are slow but no longer fail. A full montelukast run at `MODEL_PARALLEL=4` with all of this in place took 16 minutes with 0 retries and 13 of 13 calls succeeding (36 minutes and 25 retries with streaming alone, before the Nightshift settings change).
- **Nightshift's first-byte limit on streamed calls.** Nightshift learns a time-to-first-byte budget per model, 1.5 times the 95th percentile of recent first-token times and at most 45 s (`ttfbBudget` in its `engine/js/engine/health.js`). When NVIDIA slows down, a streamed call that waits longer is cut with `ttfb_timeout`, which the client retries, or splits like `provider_deadline` for a batch. In the 24 Oct evening evaluation that happened to 33 of 237 calls, and one item ended not reviewed. Separately, 8 of 529 successful streamed calls in Bryan's 24 and 25 Oct runs took longer than 90 s, so the merge's whole-call limit will cut and retry about 1.5% of calls.
- **Nightshift 1.2.1 ignores the app's model pin** (found 24 Oct). Its proxy passes a request's model only to an app without a policy, but its policy lookup returns one for every app, and the first request from a new app saves the global mode as that app's rule. So calls route by Nightshift's own mode. On a default install that means the quality lane (unstreamed, cut at 45 s) and possibly other models. The README's Run it section now tells judges how to set Nightshift up, and each run warns (console, trace and the dossier's `nightshift_warnings`) at the first call served by another model or with the reasoning scaffold.

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

**25 Oct, the re-evaluation at Ricky's code defaults.** Every version re-run with no `.env` settings beyond the connection keys, scored on gold v2 by one scorer. Results, method and what one run per drug can't show are in `03_Project_context/Vigil_Reevaluation_RickyDefaults_25Oct.md` and the README's Results section.

**25 Oct, Bryan's Task 2 (clinical reliability), branch `feature/label-search-evidence`** (in the 25 Oct final PR to `main`). It adds the label search across every fetched section, report sources for review-next items, uncertainty and scope for each row, the manual-review flag, the serious-term safety net and small rule fixes. What changed, the live checks and the decisions left open are in Bryan's note for Ricky, `03_Project_context/Vigil_Task2_Clinical_Reliability.md`, and in the commit messages.

**Agent-system to-do, as of 25 Oct (Ricky's order: finish the agent system, then demo and UX).** Everything below is on `main` since 25 Oct; new work branches from `main`.

**25 Oct: Bryan's PR #10 (`fix/verified-batch-24-oct`) was merged into `fix/eval-logic`, then everything into `main`.**
- Kept from Bryan: streamed calls (`MODEL_STREAM`, default on); a fresh `meterless-scope` per call, which keeps H-MEM out; `meterless-tier-split: off`; Nightshift error codes that are not retried; setup warnings when Nightshift serves another model or adds its scaffold (console, trace, dossier `nightshift_warnings`); excerpts cut around the reaction's words; four more not_meaningful terms (treatment failure, therapeutic response, a bare drug interaction, induced abortion); a disproven unresolved item no longer heads the queue as review_next; name matching that ignores case and spacing; a failed Zetaris re-check marks the findings not reviewed instead of crashing; a rejected Runtime token stops the run; "1,234"-style numbers no longer crash.
- Kept ours where both did the same thing: the label choice (`choose_label`, not Bryan's `label_source`), the indication and contraindication rules, missing-verdict and omitted-reaction handling, the one-query re-check, the shared 429 cool-down (now also for 429s inside a stream) and our defaults (90 s, 4 parallel, 1 revision round, 600 s budget).
- Added in the merge: a whole-call limit for streamed calls, because the socket timeout only bounds the gap between chunks.
- Not taken: PR #7's "objection before decision" Reviewer prompt. Our own treated-condition prompt changes address the same errors.
- 127 offline tests pass.
- Bryan's follow-up PR #11 (`fix/merge-followups-25-oct`, merged 25 Oct) adds the robustness fixes from Bryan's `fix/consolidated-24-oct` that the merge did not include (dropped Zetaris connections, null lists in replies, an empty re-check, case in enum answers, the cool-down race, `ttfb_timeout` splitting, excerpts centred on the strongest word), with his consolidated evaluation reports. 157 offline tests pass on `main` with the API tests.

Still open, in order:
1. **Done on Ricky's laptop (checked 25 Oct): `raceParallelism` 1, `qualityRace` off, `reasoningScaffold` off, only the Ultra lane running.** For other machines: in Nightshift's `state/setpoints.json` set `"raceParallelism": 1`, `"qualityRace": "off"` and `"reasoningScaffold": "off"`, restart Nightshift and check the lanes (Ultra only, race width 1). Without it, about half of the calls go to the quality lane, which Nightshift runs buffered and cuts at 45 s even for a streamed request. Ricky's 24 Oct traces show every call served by Ultra with no scaffold.
2. **One timed live run of the merged code: done 25 Oct** (montelukast through Docker, branch `feature/api-docker` = `fix/eval-logic` plus the API, before Bryan's PR #11 follow-up fixes; `dossier-20261025T055628Z-3ae747`). 587 s; 42 model calls, all served by Ultra, **0 with H-MEM memories** (the fresh scope works) and 0 with the scaffold; median call 27 s, longest 83 s; **0 NVIDIA rate limits** (16 to 28 per drug on 24 Oct, before streaming); 4 retries, all recovered (3 Nightshift `ttfb_timeout`, 1 stream cut by the new 90 s limit); no degraded steps or unclassified reactions. Not scored against gold. Next: the three-drug evaluation, the first numbers on Ricky's laptop without H-MEM; compare with Bryan's 24 Oct report.
3. **Decide how to live with NVIDIA's trial rate limit.** With 4 parallel calls the 24 Oct timed runs had 16 to 28 NVIDIA 429 waits per drug, so the 600 s budget skipped the second revision round and the Skeptic's challenge review. Options: (a) `MODEL_PARALLEL=2` and `RUN_BUDGET_SECONDS=900`, with judges using `SAMPLE_MODE` replays for speed; (b) item 4 first, in case Super's requests count separately from Ultra's. Streaming may change this: measure again in item 2 first.
4. **Nemotron role test** (also the NVIDIA award's "technical depth"): Nemotron 3 Super 120B A12B as the Analyst (`ANALYST_MODEL`), Ultra as the Reviewer, scored on gold against all-Ultra, with run time and failure counts. Needs a Super lane in Nightshift (race width 1, Lightning stopped); check its model ID with `GET /v1/models` and one test call first. Super is reported to be unreliable; drop it if it fails often. Nightshift 1.2.1 ignores the request's model pin, so the lanes decide which model answers: check `served_by` in the trace.
5. **Treated-condition errors:** in the 24 Oct runs, which had H-MEM on, metformin HYPERGLYCAEMIA and BLOOD GLUCOSE ABNORMAL and montelukast CHEST DISCOMFORT were marked clinical events sent for review (gold: the treated disease). Check them again in item 2 before changing anything. If they persist, test giving each single-reaction call the names of the other screened reactions (context, not classification), without putting evaluation cases into prompt examples (`tests/test_offline.py::test_prompt_examples_avoid_the_evaluation_drugs`).
6. **Timing test: the whole label for the Reviewer** instead of 3 retrieved sentences (Ultra has a 1M-token context; retrieval misses caused real errors). With streaming the limits are our 90 s per call and Nightshift's first-byte budget (at most 45 s, see Known issues), which a longer prompt also pushes up.
7. **World Model read by the agents:** earlier settled verdicts and reopened items go into the Analyst's and Reviewer's prompts, and the engine's audit entries go into the run's trace (the World Model guide in `docs/reference/` recommends both).
8. **Human review of the gold set** before any accuracy number is quoted publicly: four rows flagged in `eval/LABELLING_RULES.md` (sertraline ANXIETY, PANIC ATTACK and INTENTIONAL SELF-INJURY, metformin METABOLIC ACIDOSIS), plus the rows Bryan found the newer labels no longer support (metformin ACUTE KIDNEY INJURY and ACUTE RENAL FAILURE).
9. A final clean evaluation run on the finished system, on `main` (ask Ricky before pushing to `main`).

How to run the evaluation: `python -I eval/run_eval.py --drugs sertraline metformin montelukast --repeats 1 --repeat-extra 0` (one drug at a time; progress prints to stdout, report in `eval/reports/`). Offline tests: `python -I -m pytest -q tests` ({{TESTS_PASS}} pass).

**Progress, 24 Oct afternoon** (every run below had H-MEM on).
- **Re-run** (`eval/reports/eval-20261024T054159Z-gold_v2.md`): worse, 80% round-1 and 76% final on the three drugs, against 88% and 90% for the same drugs on 23 Oct.
  - Cause, from the Analyst's own reasoning: with serious and death shares in its table, it escalated treated-disease terms ("High reporting (PRR 7.03) with 93% serious and 7% death") to review_next, 16 such items for metformin.
  - Fixed in `4e5aad3`: the shares stay in the pick step and the dossier, but no longer reach the classification or review prompts.
  - Also found: on metformin's real label, retrieval tied "blood" and "hypoglyc" and showed lactate sentences. Synonym words now count double (checked on the real label).
  - Sertraline ANXIETY and PANIC ATTACK: the gold evidence is not in any section the app keeps; flagged in `eval/LABELLING_RULES.md`.
- **Run-time changes**, made in three passes (`2ac103f`, `71244a4`, `cfefbaf`):
  - one reaction per call, 4 parallel calls, a 90 s timeout and one retry, a 600 s run budget
  - the pick runs alongside classification, and the Data Clerk's queries run in parallel
  - the Reviewer's re-checks in one Zetaris query (they had taken 3.5 to 4 of the 6 review minutes)
  - one revision round, with the Skeptic's checks overlapping it
  - a shared cool-down on NVIDIA 429s
  - progress lines on stdout
  - also: context decided before coverage, a code check that coverage fits context, and prompt examples moved off the evaluation drugs
- **Timed runs, three drugs each** (reports `eval-20261024T061951Z`, `-064905Z`, `-072538Z`): 8 to 13 minutes per drug, against 22 to 33 before. Accuracy on the last run: 86% round-1, 84% final.
- **The limit was NVIDIA's trial rate, not our code:** 16 to 28 rate-limit waits per drug, so the budget skipped the second revision round and the Skeptic's challenge review every time. The Skeptic's evidence is still recorded.

After that: demo and UX (investigation page, `SAMPLE_MODE`, samples, deck, video). `POST /run` and the Dockerfile are built (on `main`, 25 Oct).

1. **Organiser questions** (below). The Track 02 challenge statement on HackOS is the generic track text (confirmed 24 Oct); nothing more to read.
2. **Evaluation:** see the status table. A person still needs to review gold v1 and v2 before any number is quoted publicly.
3. **World Model engine:** merged into `main` on 23 Oct, with offline tests; reopening shown live on 23 Oct (see the status table). This counts for the Build rule: the 19 Oct setup guide (section 3.2 and "Verify your Build setup") asks for the engine to be implemented in your own application, in any language, with "the engine's relevant conformance suite, evaluation, or a reproducible feature test" passing. For the submission: name the engine, say what it does here, and show the feature and the test result.
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
