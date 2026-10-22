# Instructions for coding agents (Codex, Cursor, Claude Code)

Black Box is our Open Agent Hackathon 2026 entry (Track 02). Read `docs/HANDOFF.md` first: it covers the current state, run commands, code map, known issues and next steps. The design and its reasons are in `docs/ideas/BLACK_BOX.md`. Event rules are in `docs/HACKATHON_KNOWLEDGE.md`. Teammate setup is in `docs/TEAM_SETUP.md`.

## Rules

- **Secrets.** Never read, print or copy `.env`. Settings come from environment variables via `app/config.py`. The NVIDIA key lives inside Meterless Nightshift only. Never put the Nightshift token or NVIDIA key into an editor's or agent's settings.
- **Python.** Run Python with `-I`, for example `python -I -m pytest tests -q`. The offline tests must pass before every commit or pull request; they need no services.
- **The sponsors are load-bearing.**
  - Every model call goes through Nightshift (`app/adapters/meterless.py`).
  - Every number comes from Zetaris SQL (`app/data/faers.py`).
  - Do not add a direct model API or a data path that bypasses Zetaris.
- **No hardcoding.** Never match known inputs to stored outputs, never read `output_examples/` at runtime, and never edit anything in `logs/`.
- **Do not weaken** the Judge's code checks (`app/agents/judge.py`) or the gold set (`eval/gold_v1.jsonl`) to make a run look better.
- **Keep model calls small.** Batches of 3 reactions and per-reaction label excerpts are deliberate: large prompts time out on Nightshift.
- **One investigation at a time per NVIDIA key.** Parallel runs share the per-minute cap.
- **Wording.** FAERS shows reporting patterns, not causation. Say "review next", not "new side effect". Do not overclaim in the README, deck or comments.
- **Keep the handoff current.** When the state changes, update `docs/HANDOFF.md`. When Cursor writes real code, add a dated row to `docs/CURSOR_LOG.md`, and never backdate one.
- **Match the surrounding code.** Plain Python 3.11 standard library plus `pytest`; short docstrings that say why, not what.
- **Ask a person** before pushing to `main`, opening the repo to the public, or posting anywhere.
