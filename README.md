# Black Box

**Open Agent Hackathon 2026 · Track 02: The Agent That Can Explain Why** (work in progress)

Black Box helps a drug-safety analyst decide which reported drug-reaction patterns deserve a closer look, and shows the evidence and objections behind that shortlist.

You give it a drug name. It:
1. Registers the drug's public FDA adverse-event counts (openFDA FAERS) and its current label as tables in **Zetaris**.
2. Computes reporting disproportionality (PRR, chi-squared) in SQL.
3. Has two agents running on **NVIDIA Nemotron through Meterless Nightshift** assess the strongest signals. The Hunter proposes; the Judge checks every number and label quote in code, then objects, accepts or leaves the finding unresolved.
4. Returns a ranked review queue. Each item carries:
   - its label coverage and review priority
   - the strongest objection
   - a next check
   - the SQL and label text behind it

> FAERS shows reporting patterns, not that a drug causes an event. This is not medical advice.

## Status

This is a work in progress, and this README will be rewritten for judging. What works today, what doesn't, and how to run it: [docs/HANDOFF.md](docs/HANDOFF.md).

## Quick start (local services required)

```bash
cp .env.example .env
```
Fill in the Zetaris and Nightshift values; the NVIDIA key goes into Nightshift, not `.env`.

```bash
python -I scripts/zetaris/run_sql.py scripts/zetaris/openfda_baseline.sql
```
Registers the shared Zetaris baseline. Once per Zetaris install.

```bash
python -I run.py --drug montelukast
```

```bash
python -I -m pytest tests -q
```

Outputs:
- `logs/trace-<run>.jsonl`: every query and model call
- `logs/dossier-<run>.json`: the review queue

## Docs

- [docs/HANDOFF.md](docs/HANDOFF.md): state, commands, code map, next steps
- [docs/ideas/BLACK_BOX.md](docs/ideas/BLACK_BOX.md): design and reasons
- [eval/](eval/): gold set, labelling rules, scorer
- [docs/HACKATHON_KNOWLEDGE.md](docs/HACKATHON_KNOWLEDGE.md): event rules and stack findings
- [docs/PREEXISTING.md](docs/PREEXISTING.md): pre-existing work declaration

Secrets live only in `.env` (gitignored).
