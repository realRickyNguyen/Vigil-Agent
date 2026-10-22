# Handoff: Black Box, state as of Thu 22 Oct 2026, about 17:00 Sydney (06:00 UTC)

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
| Evaluation harness | Built: 100-row gold set over 5 drugs, scorer, runner. **The baseline evaluation (old contract) is running now**; results land in `eval/reports/` |
| Meterless Engine (required) | **Not started.** Plan: minimal World Model with a behaviour test |
| Skeptic agent | Not started. Plan: one operation, reporter-type composition for top candidates |
| `SAMPLE_MODE`, Dockerfile, `POST /run`, UI | Not started. `SAMPLE_MODE` needs an organiser answer first (see open questions) |
| README, deck, video, `metadata.json` | Not started |

Git: local commits on `master`: `b5b16db` (first working loop, 22 Oct 15:50 Sydney) and `564d3ea` (contract v2, evaluation harness, these docs). There is no remote yet. Evaluation reports in `eval/reports/` are not committed yet.

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
| `docs/review/` | Review pack for outside reviewers |

## Rules to keep (from the hackathon and from what broke)

- **Secrets only in `.env`.** Never print them. The NVIDIA key lives inside Nightshift only.
- **Never edit `logs/`.** Traces and dossiers are evidence. Never load `output_examples/` at runtime, and never match known inputs to stored answers.
- **Every number an agent cites must come from a Zetaris query ID in the trace.** The Judge's code checks enforce this; do not weaken them to make a run pass.
- **Keep model calls small.** Large prompts on Nightshift time out or come back empty. Batches of 3 and per-reaction label excerpts are deliberate.
- **Do not overclaim.** FAERS shows reporting patterns, not causation. Say "review next", not "new side effect". Gold accuracy is a development check labelled by an AI, not clinical validation.
- **Cursor.** Development so far used Claude Code, because Cursor credits had not arrived. Log real Cursor work in [CURSOR_LOG.md](CURSOR_LOG.md) with dates from the day it starts. Do not backdate it.

## Known issues

- **The metformin label is a combination product** (ZITUVIMET, sitagliptin + metformin). The Clerk's label search should prefer single-ingredient labels, for example by searching `openfda.generic_name.exact:"METFORMIN HYDROCHLORIDE"`.
- **The drug search counts every report that mentions the drug, not only those where it was the suspect.** This broadens the report set; it is not the same as inflating the PRR.
- **The baseline covers only the 999 most-reported reactions** (openFDA's no-key limit, which we tested). Rarer reactions are not screened.
- **Per-drug Zetaris REST tables cannot be deleted through SQL.** They pile up in `openfda_rest`. Remove them in Data Explorer if needed.
- **The total uses the sum of the serious-flag counts,** which is about 0.05% below openFDA's report total.
- **Montelukast is not a clean "caught it early" backtest:** its warnings were in the precautions by 2012. openFDA also returns only the latest version of each case, so date filters do not reconstruct the past. The backtest is off the critical path; see `eval/BACKTEST_FEASIBILITY.md`.
- **A run takes about 9 minutes,** mostly Nightshift latency. Roughly a third of model calls fail and are retried or fall back.

## Next steps, in order

1. **You, today (needs your HackOS login):**
   - Read the Track 02 challenge statement.
   - Post the organiser questions below.
2. **Score the baseline evaluation, then run it on contract v2 and compare.** Watch round-1 against final accuracy, unresolved disputes, and whether the gold set supports the "review next" items.
3. **Minimal World Model engine** with a behaviour test: changing a supporting label version reopens a dependent "not covered" verdict.
4. **Tune the Hunter's selection** using the evaluation results (transparent criteria, a mix of candidates, no drug-specific hacks).
5. **Skeptic with one operation:** reporter-type composition for the top review-next items. It provides context, never proof.
6. **One investigation page:** ranked queue, coverage counts, evidence expansion.
7. **Submission package:** README, Dockerfile, `POST /run`, samples, video, deck, `metadata.json`, and a fresh-machine test.

## Open questions for the organisers

1. How should judges run an app whose agents need a model, given the "SAMPLE_MODE without keys" rule? Options: a local Nightshift lane, labelled replay of recorded model replies, or judges using their own Nightshift.
2. We developed with Claude Code before the Cursor credits arrived. Is that acceptable if Cursor is used from now on and disclosed?
3. Is a Python implementation of a Meterless Engine, with our own tests, accepted for the build rule?
4. What should `metadata.json` contain?
