# Handoff: Black Box, state as of Fri 23 Oct 2026, afternoon Sydney (early 23 Oct UTC)

Start here if you are picking up the work, whether you are a teammate, Cursor's agent or a new Claude session. The design and its reasoning are in [ideas/BLACK_BOX.md](ideas/BLACK_BOX.md). Event rules are in [HACKATHON_KNOWLEDGE.md](HACKATHON_KNOWLEDGE.md).

## What it is

Black Box helps a drug-safety analyst decide which reported drug-reaction patterns deserve a closer look, and shows the evidence and objections behind that shortlist. Track 02, "The Agent That Can Explain Why".

Input is a drug name. The app:
1. Registers that drug's public openFDA adverse-event counts and its current label in **Zetaris** at runtime.
2. Computes disproportionality (PRR, chi-squared) in SQL.
3. Lets two Nemotron agents, run through **Meterless Nightshift**, assess the strongest signals. The Hunter proposes; the Judge checks in code, then objects, accepts or leaves the item unresolved.
4. Writes a ranked review queue (the dossier) and a full JSONL trace.

## Status

| Area | State |
|---|---|
| Zetaris data layer (Clerk) | Built and working. Any drug name is registered at runtime; PRR matches an independent Python check |
| Hunter and Judge loop | Built. Last full run: montelukast in 9 minutes on Nemotron Ultra |
| Decision contract v2 | **Code done and tested offline (37 tests), not yet run against Nightshift.** It separates label coverage, context and review priority; adds objection and next check per finding; closes disputes as `unresolved`; marks unreached items `pending` or `failed` |
| Evaluation harness | Built: 100-row gold set over 5 drugs, scorer, runner. **Baseline (contract v1) scored 22 Oct:** `eval/reports/eval-20261022T063731Z.md`. 5 runs, one per drug: 93% round-1 and 95% final accuracy on clear gold items, but only 27 of 80 clear items were classified in round 1. The Judge fixed 1 item and kept 1 wrong. The two montelukast repeat runs were stopped, so there is no repeat-run agreement yet |
| Meterless Engine (required) | **Not started.** Plan: minimal World Model with a behaviour test |
| Skeptic agent | Not started. Plan: one operation, reporter-type composition for top candidates |
| `SAMPLE_MODE`, Dockerfile, `POST /run`, UI | Not started. `SAMPLE_MODE` needs an organiser answer first (see open questions) |
| README | **Done** (22 Oct): user story, problem, inputs and outputs, why agents, Track 02 mapping, sponsors, results, limitations. Sourced statistics: 23% (Doernberg et al., JAMA Intern Med 2026, checked), about 27,000 alerts and 99.9% closed (GSK, Drug Safety 2026, checked), and FDA's "more than 2 million" reports a year. The exact 2,048,059 from the 2025 OSE report is **not verified**, so it isn't used |
| Team briefing deck | **Done** (23 Oct), internal only: `C:\Users\Ricky\projects\black-box-deck\` on Ricky's laptop, **outside the repo** because it contains licensed BioRender assets and sponsor logos. Contents: `black_box_team_briefing.pptx` and `.pdf`, `speaker_notes.md` (plain-language notes, the source), `build_deck.ps1` (rebuild with the research-deck skill). 13 slides: track, why it matters, user, proposal, why agents, workflow diagram, sponsor tools, progress checklist, submission, video plan, summary |
| Submission deck, video, `metadata.json` | Not started. Build the submission deck from the team briefing; the required contents are in `HACKATHON_KNOWLEDGE.md` |

Git: branch `main`. Key commits: `bf4f2c1` (first working loop, 22 Oct 15:50 Sydney) and `d3d9394` (contract v2, evaluation harness, docs). Last pushed commit: `90ac97b` (outdated review pack removed). **Uncommitted local edits (23 Oct):** `CLAUDE.md`, `README.md`, `docs/HANDOFF.md`, `docs/HACKATHON_KNOWLEDGE.md`, `docs/CURSOR_LOG.md`, all marking Cursor as optional. Ricky asked to leave them uncommitted for now; commit them (no Co-Authored-By trailer) and push when he says so. Private GitHub repo for the team since 22 Oct: https://github.com/realRickyNguyen/genai_hackathon (`origin`). Teammate setup is in [TEAM_SETUP.md](TEAM_SETUP.md). Run traces and dossiers in `logs/` are gitignored; choose which to publish as evidence before the repo goes public.

Tools: Cursor became optional on 23 Oct and no credits are coming; we develop mainly with Claude Code and Codex, and Cursor's free plan may be used for small tasks. `CLAUDE.md`, `AGENTS.md` and `.cursor/rules/` carry the same rules.

## How to run

**Start the services** (the "lets begin" routine in [../CLAUDE.md](../CLAUDE.md)):
- Docker Desktop
- `docker compose up -d` in `~/zetaris-platform` (WSL Ubuntu)
- Nightshift

**Check Nightshift after every restart.** A restart re-seats lanes from its saved `lanes.toml`. The working setup is:
- NIGHT › LANES: the first lane runs `nvidia/nemotron-3-ultra-550b-a55b` (its card still shows the old ID `nemotron-3-super-120b-a1`). The **Lightning lane is stopped**.
- Setup › PREFERENCES: **race width 1**.
- Why: racing two lanes made pinned model IDs meaningless, and an empty reply from one lane failed the whole request. The Super model itself returns NVIDIA 404 for this key.
- The other preference changes we discussed (reasoning scaffold, fusion, judging, cache and so on set to off) have **not** been applied.

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
| `app/adapters/meterless.py` | Nightshift client: required headers, retries, `served_by` logging, JSON extraction (handles Ultra's inline `</think>`) |
| `app/data/faers.py` | The Clerk: registers openFDA tables per drug, signal SQL, label fetch |
| `app/data/label.py` | Label helpers: per-reaction sentence retrieval, literal term lookup |
| `app/agents/rules.py` | Code routing for easy cases: administrative terms, treated condition, literal label match |
| `app/agents/hunter.py` | Hunter: pick (1 call), then classify in batches of 3 with fallbacks |
| `app/agents/judge.py` | Judge: code checks first, then model review in batches; objection and next check per finding |
| `app/orchestration/pipeline.py` | The loop, dispute settling (`settle`), review queue and counts, dossier |
| `app/schemas.py` | `Finding` (contract v2), `Verdict`, `Signal`, status constants |
| `app/tracing.py` | Append-only JSONL trace, thread-safe |
| `scripts/zetaris/` | Baseline SQL and a runner that sends `.sql` files through the REST API |
| `eval/` | Gold set, labelling rules, scorer, runner, backtest feasibility notes |
| `tests/` | Offline tests: app logic and scorer |
## Rules to keep (from the hackathon and from what broke)

- **Secrets only in `.env`.** Never print them. The NVIDIA key lives inside Nightshift only.
- **Never edit `logs/`.** Traces and dossiers are evidence. Never load `output_examples/` at runtime, and never match known inputs to stored answers.
- **Every number an agent cites must come from a Zetaris query ID in the trace.** The Judge's code checks enforce this; do not weaken them to make a run pass.
- **Keep model calls small.** Large prompts on Nightshift time out or come back empty. Batches of 3 and per-reaction label excerpts are deliberate.
- **Do not overclaim.** FAERS shows reporting patterns, not causation. Say "review next", not "new side effect". Gold accuracy is a development check labelled by an AI, not clinical validation.
- **Cursor.** Optional since 23 Oct; no credits. Development is mainly Claude Code and Codex, with Cursor's free plan for small tasks if useful. Log real Cursor work in [CURSOR_LOG.md](CURSOR_LOG.md) on the day it happens. Never backdate it.

## Known issues

- **The metformin label is a combination product** (ZITUVIMET, sitagliptin + metformin). The Clerk's label search should prefer single-ingredient labels, for example by searching `openfda.generic_name.exact:"METFORMIN HYDROCHLORIDE"`.
- **The drug search counts every report that mentions the drug, not only those where it was the suspect.** This broadens the report set; it is not the same as inflating the PRR.
- **The baseline covers only the 999 most-reported reactions** (openFDA's no-key limit, which we tested). Rarer reactions are not screened.
- **Per-drug Zetaris REST tables cannot be deleted through SQL.** They pile up in `openfda_rest`. Remove them in Data Explorer if needed.
- **The total uses the sum of the serious-flag counts,** which is about 0.05% below openFDA's report total.
- **Montelukast is not a clean "caught it early" backtest:** its warnings were in the precautions by 2012. openFDA also returns only the latest version of each case, so date filters do not reconstruct the past. The backtest is off the critical path; see `eval/BACKTEST_FEASIBILITY.md`.
- **A run takes about 9 minutes,** mostly Nightshift latency. Roughly a third of model calls fail and are retried or fall back.

## Context from 22 to 23 Oct

- **Outside review.** An outside LLM panel scored the design 50/100. Its main points, which the next steps follow:
  - Pitch it as a review shortlist, not as discovering side effects.
  - Separate label coverage, priority and workflow status (done in contract v2).
  - Build one minimal World Model with a behaviour test.
  - Add one evidence-seeking Skeptic step.
  - Drop the montelukast "caught it early" backtest.

  The review file is on Ricky's laptop (`Downloads\BLACK_BOX_PANEL_REVIEW.md`), not in the repo.
- **Ricky's laptop disk** filled up on 22 Oct. Cleanup so far:
  - Cursor's install was cancelled. Cursor was to be uninstalled; a teammate uses Cursor instead.
  - Nightshift's local Llama models went to the Recycle Bin.
  - Five unused Docker images and the build cache were removed.

  Space returns only after `scripts/compact-wsl-disks.ps1` runs as administrator with Docker quit, and after the Recycle Bin is emptied. Check C: free space before large runs.
- **Services** were stopped at the end of 22 Oct. Use the "lets begin" routine in `CLAUDE.md`, then check that the Nightshift lanes are still Ultra-only.

## Next steps, in order

1. **You, today (needs your HackOS login):**
   - Read the Track 02 challenge statement.
   - Post the organiser questions below.
2. **Run the evaluation on contract v2** (`python -I eval/run_eval.py`, about 1.5 hours) **and compare with the baseline report.** Watch:
   - round-1 against final accuracy
   - unresolved disputes
   - whether the gold set supports the "review next" items
   - coverage: the baseline classified only a third of the clear gold items

   The repeat runs give the first stability figure.
3. **Minimal World Model engine** with a behaviour test: changing a supporting label version reopens a dependent "not covered" verdict.
4. **Tune the Hunter's selection** using the evaluation results (transparent criteria, a mix of candidates, no drug-specific hacks).
5. **Skeptic with one operation:** reporter-type composition for the top review-next items. It provides context, never proof.
6. **One investigation page:** ranked queue, coverage counts, evidence expansion.
7. **Submission package:** README, Dockerfile, `POST /run`, samples, video, deck, `metadata.json`, and a fresh-machine test.

## Open questions for the organisers

1. How should judges run an app whose agents need a model, given the "SAMPLE_MODE without keys" rule? Options: a local Nightshift lane, labelled replay of recorded model replies, or judges using their own Nightshift.
2. (Settled 23 Oct: Cursor is optional.) Does the sponsor explanation still need a Cursor paragraph, or a `metadata.json`?
3. Is a Python implementation of a Meterless Engine, with our own tests, accepted for the build rule?
4. What should `metadata.json` contain?
