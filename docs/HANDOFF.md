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
| Analyst and Reviewer loop | Built. On 24 Oct, with streaming and `MODEL_PARALLEL=4`, each evaluation run took 8 to 11 minutes on Nemotron Ultra, and 78 of 82 model call attempts succeeded |
| Decision contract v2 | **Built and evaluated on 24 Oct** (see Evaluation harness). It separates label coverage, context and review priority; adds objection and next check per finding; closes disputes as `unresolved`; marks unreached items `pending` or `failed` |
| Evaluation harness | Built: 100-row gold set over 5 drugs, scorer, runner. **Baseline (contract v1) scored 22 Oct:** `eval/reports/eval-20261022T063731Z.md`. 5 runs, one per drug: 93% round-1 and 95% final accuracy on clear gold items, but only 27 of 80 clear items were classified in round 1. The Reviewer fixed 1 item and kept 1 wrong. The two montelukast repeat runs were stopped, so there is no repeat-run agreement yet. A 23 Oct evaluation of `main` on Bryan's desktop (71% final, report not in the repo) ran with Nightshift's H-MEM feeding earlier answers into every call, and mostly measured that (see Known issues). The 22 Oct baseline may be affected too. **Evaluated 24 Oct on this code** (`eval/reports/eval-20261024T022640Z.md`, memory off, streaming), with each drug once and montelukast twice more. 93% round-1 (26 of 28) and 89% final (49 of 55) accuracy on clear gold items, with rules right 27 of 27 times and the model 22 of 28. Of the 6 final errors, 3 are gold rows whose evidence the newer labels no longer contain (metformin acute kidney injury and acute renal failure, sertraline panic attack), 2 are broader-or-narrower judgement calls (metformin metabolic acidosis, sertraline intentional self-injury) and 1 is a model error (metformin diabetic ketoacidosis, a contraindication counted as coverage). Round 1 assessed 24 of 80 clear items, and 43 had a final answer. Montelukast repeat agreement was 0.95. Quote these numbers, not the earlier ones |
| Meterless Engine (required) | **World Model: built, 13 offline tests, and one live run** (merged into `main` 23 Oct). Live montelukast run 22 Oct 07:54 UTC (`dossier-20261022T075444Z-c885cc`, Bryan's desktop): 15 settled verdicts recorded against the current label version; nothing reopened, as the label had not changed. Reopening itself is shown only in the offline tests so far. `app/engines/world_model.py` ports the Meterless reference (stable IDs, merge bands, provenance on every write, idempotent ingest, bitemporal edges, audit order); `tests/test_world_model.py` ports its 8 conformance checks. Our addition: decisions recorded with the facts they rest on. `pipeline.remember()` stores each run's label version and settled verdicts in `state/world-model.json` (gitignored); a later run on a changed label version reopens the earlier verdicts and lists them under `world_model.reopened` in the dossier |
| Skeptic agent | Not started. Plan: one operation, reporter-type composition for top candidates |
| `SAMPLE_MODE`, Dockerfile, `POST /run`, UI | Not started. `SAMPLE_MODE` needs an organiser answer first (see open questions) |
| README | **Done** (22 Oct): user story, problem, inputs and outputs, why agents, Track 02 mapping, sponsors, results, limitations. Sourced statistics: 23% (Doernberg et al., JAMA Intern Med 2026, checked), about 27,000 alerts and 99.9% closed (GSK, Drug Safety 2026, checked), and FDA's "more than 2 million" reports a year. The exact 2,048,059 from the 2025 OSE report is **not verified**, so it isn't used |
| Team briefing deck | **Done** (23 Oct), internal only: `C:\Users\Ricky\projects\black-box-deck\` on Ricky's laptop, **outside the repo** because it contains licensed BioRender assets and sponsor logos. Contents: `black_box_team_briefing.pptx` and `.pdf`, `speaker_notes.md` (plain-language notes, the source), `build_deck.ps1` (rebuild with the research-deck skill). 13 slides: track, why it matters, user, proposal, why agents, workflow diagram, sponsor tools, progress checklist, submission, video plan, summary |
| Submission deck, video, `metadata.json` | Not started. Build the submission deck from the team briefing; the required contents are in `HACKATHON_KNOWLEDGE.md` |

Git: branch `main`. Key commits: `bf4f2c1` (first working loop, 22 Oct 15:50 Sydney) and `d3d9394` (contract v2, evaluation harness, docs). On 23 Oct Bryan's `feature/world-model` and `fix/nightshift-connection-reset` branches were merged into `main` and pushed. Later on 23 Oct, also pushed: the combined drug search from Bryan's issue (`fix/combined-drug-search`, merged), full prompts and replies in the trace (`feature/full-trace`, merged), Nightshift memory and scaffold recorded per call (`44c9bb4`), and the rename to Vigil (`e7ead70`; 55 offline tests pass). **After pulling:** `hunter.py` is now `analyst.py` and `judge.py` is `reviewer.py`; rebase any open branch, and expect conflicts in agent files. An older `.env` with `HUNTER_MODEL`, `JUDGE_MODEL` or `JUDGE_ROUNDS` still works. Not pushed: `experiment/skeptic-co-drugs` (the Skeptic, awaiting a live run of its latest fixes), on Ricky's laptop only. Private GitHub repo for the team since 22 Oct: https://github.com/realRickyNguyen/genai_hackathon (`origin`). Teammate setup is in [TEAM_SETUP.md](TEAM_SETUP.md). Run traces and dossiers in `logs/` are gitignored; final ones go into `output_examples/` for submission (next step 8).

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
| `app/adapters/meterless.py` | Nightshift client: required headers, retries (including dropped connections), `served_by` logging, JSON extraction (handles Ultra's inline `</think>`) |
| `app/data/faers.py` | The Data Clerk: registers openFDA tables per drug, signal SQL, label fetch |
| `app/data/label.py` | Label helpers: per-reaction sentence retrieval, literal term lookup |
| `app/agents/rules.py` | Code routing for easy cases: administrative terms, treated condition, literal label match |
| `app/agents/analyst.py` | Analyst: pick (1 call), then classify in batches of 3 with fallbacks |
| `app/agents/reviewer.py` | Reviewer: code checks first, then model review in batches; objection and next check per finding |
| `app/orchestration/pipeline.py` | The loop, dispute settling (`settle`), review queue and counts, World Model record (`remember`), dossier |
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

- **Fixed 23 Oct: the metformin label was a combination product** (ZITUVIMET, sitagliptin + metformin), because the label was whichever one openFDA returned first for the generic name (sertraline's was from 2019). The Data Clerk now registers the generic names on the drug's labels (`label_names_<slug>_raw`), picks the most common single-ingredient name (METFORMIN HYDROCHLORIDE, not SITAGLIPTIN AND METFORMIN HYDROCHLORIDE), and registers the latest prescription label filed under it (`label_s_<slug>_<hash>_raw`, sorted by `effective_time`). It falls back to the old first match if no name qualifies. Checked live through Zetaris for all five gold drugs: each gets a single-ingredient prescription label from 2026. The new labels have new set IDs, so the World Model reopens earlier verdicts on the next run of each drug.
- **Fixed 23 Oct: the drug search used openFDA's `generic_name` alone,** which openFDA fills only when it can match the product record. Bryan showed against FDA's raw quarterly files that it found 39% of atorvastatin's reports (46% levothyroxine, 87% metformin, 99%+ montelukast). `drug_search()` now uses `generic_name` OR `activesubstance.activesubstancename` (atorvastatin through Zetaris: 249,468 to 519,224 reports), with new table names (`faers_d2_<slug>_…`) because old REST tables cannot be dropped. The 22 Oct evaluation used the old search; re-run it before quoting numbers. Combination products are included by both fields (46% of acetaminophen's reports, 12% of metformin's).
- **The drug search counts every report that mentions the drug, not only those where it was the suspect.** This broadens the report set; it is not the same as inflating the PRR.
- **The baseline covers only the 999 most-reported reactions** (openFDA's no-key limit, which we tested). Rarer reactions are not screened.
- **Per-drug Zetaris REST tables cannot be deleted through SQL.** They pile up in `openfda_rest`. Remove them in Data Explorer if needed.
- **The total uses the sum of the serious-flag counts,** which is about 0.05% below openFDA's report total.
- **Montelukast is not a clean "caught it early" backtest:** its warnings were in the precautions by 2012. openFDA also returns only the latest version of each case, so date filters do not reconstruct the past. The backtest is off the critical path; see `eval/BACKTEST_FEASIBILITY.md`.
- **A run takes 8 to 11 minutes,** mostly Ultra's reasoning at 15 to 34 tokens/s (24 Oct, with streaming and `MODEL_PARALLEL=4`). Before streaming, about two thirds of model call attempts failed and runs took 17 to 35 minutes.
- **Nightshift's H-MEM replayed earlier answers, which the model treated as vetted** (fixed 24 Oct). With memory on, all four montelukast runs on 23 and 24 Oct marked obstructive airways disorder and dyspnoea as signals to review, repeating an answer first made on 22 Oct. In one run, 10 of the 20 texts the model wrote repeated earlier runs word for word, and the Reviewer reasoned "The prior vetted answer also said clinical_event" before accepting. With a fresh scope per call, `main`'s own prompts got all three airway items right (6 of 7 in round 1, 7 of 8 final). The 23 Oct repeat-run agreement (0.93) also reflects the replay.
- **Most `provider_deadline` failures came from buffered calls** (fixed 24 Oct). Nightshift aborts its NVIDIA fetch when no response headers arrive within 45 s (`CLOUD_FETCH_DEADLINE_MS` in its `providers.js`; no setting or request field changes it). A buffered (`stream: false`) reply sends no headers until the whole answer is written, so any reply Ultra needs more than 45 s for failed. In Nightshift's receipts that was 376 of 390 failures to 24 Oct. The client now streams (`MODEL_STREAM=true`, the default), which gets headers at once. Nightshift still runs two steps buffered even for a streamed request, and both can still hit the 45 s cut. One is its own fallback after a failed first attempt. The other is the whole answer when its quality lane is on (difficulty 0.6 or more, about half of our calls). The client also sends `meterless-tier-split: off`, which stops the buffered planning phase and Nightshift's "plan only" or "diff only" system prompts (Nightshift ignores our model pin, so these applied to our calls). Setting `"qualityRace": "off"` and `"reasoningScaffold": "off"` in Nightshift's `state/setpoints.json` (then restart Nightshift) removes the quality lane; done on Bryan's PC on 24 Oct, and every teammate's Nightshift needs the same. At race width 1 the quality lane has only one answer to choose from. In a live A/B on 24 Oct, the same real Reviewer prompt ran 10 times each way. Buffered calls succeeded 0 of 10 times (all `provider_deadline` at 50 s), and streamed calls 10 of 10, with valid JSON and a median of 130 s per call. Ultra runs at about 15 to 34 tokens/s on NVIDIA and about 77% of each reply is reasoning, so calls are slow but no longer fail. A full montelukast run at `MODEL_PARALLEL=4` with all of this in place took 16 minutes with 0 retries and 13 of 13 calls succeeding (36 minutes and 25 retries with streaming alone, before the Nightshift settings change).

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

1. **You, today (needs your HackOS login):**
   - Read the Track 02 challenge statement.
   - Post the organiser questions below.
2. **The evaluation on contract v2 ran on 24 Oct** (see Status; about 70 minutes with `MODEL_PARALLEL=4`). Next, a person re-checks the gold rows the newer labels moved (metformin acute kidney injury and acute renal failure, sertraline panic attack) and decides the two judgement calls (metformin metabolic acidosis, sertraline intentional self-injury). In later runs, watch the points below.
   - round-1 against final accuracy
   - unresolved disputes
   - whether the gold set supports the "review next" items
   - coverage: the baseline classified only a third of the clear gold items

   Repeat agreement on montelukast was 0.95 on 24 Oct, with memory off.
3. **World Model engine:** merged into `main` on 23 Oct, with offline tests and one live run. Still to do: the organiser answer on whether a Python port counts for the build rule (open question 3).
4. **Tune the Analyst's selection** using the evaluation results (transparent criteria, a mix of candidates, no drug-specific hacks).
5. **Skeptic with one operation:** reporter-type composition for the top review-next items. It provides context, never proof.
6. **One investigation page:** ranked queue, coverage counts, evidence expansion.
7. **Submission package:** README, Dockerfile, `POST /run`, samples, video, deck, `metadata.json`, and a fresh-machine test.
8. **Evidence for judges:** `logs/` is gitignored, so judges see no traces unless we publish them. Once the system is final, run each sample drug on it, then copy the chosen `trace-<run>.jsonl` and `dossier-<run>.json` **unedited** into `output_examples/` and point to them from the README. The app never reads `output_examples/`. Since 23 Oct every `llm_call` event holds the full prompt messages and the raw reply (including Ultra's inline reasoning), so a reader can see exactly what each agent was shown and answered. Traces made before that hold only sizes and a prompt hash, so publish only traces from the final system.

## Open questions for the organisers

1. How should judges run an app whose agents need a model, given the "SAMPLE_MODE without keys" rule? Options: a local Nightshift lane, labelled replay of recorded model replies, or judges using their own Nightshift.
2. (Settled 23 Oct: Cursor is optional, and we do not use it.) Does the sponsor explanation need to mention Cursor at all?
3. Is a Python implementation of a Meterless Engine, with our own tests, accepted for the build rule?
4. What should `metadata.json` contain?
