# Instructions for coding agents

Vigil is our Open Agent Hackathon 2026 entry (Track 02). Read `docs/HANDOFF.md` first: it covers the current state, run commands, code map, known issues and next steps. The design and its reasons are in `docs/ideas/VIGIL.md`. Event rules are in the organisers' documents on HackOS (Resource Center); they are not in this repo. Teammate setup is in `docs/TEAM_SETUP.md`.

## Rules

- **Secrets.** Never read, print or copy `.env`. Settings come from environment variables via `app/config.py`. The NVIDIA key lives inside Meterless Nightshift only. Never put the Nightshift token or NVIDIA key into an editor's or agent's settings.
- **Python.** Run Python with `-I`, for example `python -I -m pytest tests -q`. The offline tests must pass before every commit or pull request; they need no services.
- **The sponsors are load-bearing.**
  - Every model call goes through Nightshift (`app/adapters/meterless.py`).
  - Every number comes from Zetaris SQL (`app/data/faers.py`).
  - Do not add a direct model API or a data path that bypasses Zetaris.
- **No hardcoding.** Never match known inputs to stored outputs, never read `output_examples/` at runtime, and never edit anything in `logs/`.
- **Do not weaken** the Reviewer's code checks (`app/agents/reviewer.py`) or the gold sets (`eval/gold_*.jsonl`; the person-reviewed versions are `eval/*_reviewed.jsonl`, see `eval/GOLD_REVIEW.md`) to make a run look better.
- **Keep model calls small.** One reaction per call and per-reaction label excerpts are deliberate: large prompts run long on Nightshift and NVIDIA, and calls are bounded at 90 s.
- **Sample mode replays recordings.** `samples/<drug>.json.gz` are recorded live runs that `SAMPLE_MODE=true` replays (`app/sample_mode.py`), and `output_examples/` holds those runs' unedited outputs. After any change to what the agents do, re-record them with `python -I run.py --drug <drug> --record`, with Zetaris and Nightshift running.
- **One investigation at a time per NVIDIA key.** Parallel runs share the per-minute cap.
- **Wording.** FAERS shows reporting patterns, not causation. Say "review next", not "new side effect". Do not overclaim in the README, deck or comments.
- **Keep the handoff current.** When the state changes, update `docs/HANDOFF.md`.
- **Match the surrounding code.** Plain Python 3.11 standard library plus `pytest`; short docstrings that say why, not what.
- **Ask a person** before pushing to `main`, opening the repo to the public, or posting anywhere.
