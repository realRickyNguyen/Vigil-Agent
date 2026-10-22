# Open Agent Hackathon 2026: project context

Read this first in every session. Full rules and plan are in `docs/reference/` (the 03_LLM_context pack and the 19 Oct setup guide). Where those disagree, the live HackOS event page and organiser announcements win. Setup progress is tracked in `docs/SETUP_CHECKLIST.md`.

## The event
- Organiser GenAI Works, platform HackOS (hackathon.genai.works). Online, 22 to 27 Oct 2026. Teams of 1 to 5; the user's team and track are **not yet decided**.
- Build window opens **Thu 22 Oct 00:00 UTC (11:00 Sydney)**. Registration closes Fri 23 Oct 10:45 Sydney (plan for this earlier cutoff). Submissions close **Tue 27 Oct 23:45 UTC (Wed 28 Oct 10:45 Sydney)**, hard deadline. The user is in Sydney (AEDT, UTC+11): give both UTC and Sydney times.
- Onboarding stream Wed 21 Oct 23:00 Sydney. Challenge statements appear on HackOS challenge pages and override the generic track text.
- Tracks (pick exactly one): 01 Fragmented Intelligence, 02 The Agent That Can Explain Why, 03 Reasoning Architecture, Wildcard (existing project, only new work scored).
- Judging (100 pts): Impact 30, Technical 20, Innovation 15, Demo 15, Product/UX 10, Sponsor Tech 10.
- Deliverables: demo video (1 to 4 min), slide deck, **public** GitHub repo with README, sponsor technology explanation (Zetaris, Meterless, Cursor, NVIDIA).

## Hard rules (disqualification risks)
- Zetaris and Meterless must be load-bearing, not decorative. Cursor is the required dev environment. Use NVIDIA Nemotron via Meterless Nightshift.
- Build rule (19 Oct guide): implement at least one **Meterless Engine** (H-MEM, Markovian, World Model, Scout Intent) in a working feature with a passing test. Power rule: the app must support **Meterless Nightshift as its primary AI provider**. A prompt file or unused dependency does not count.
- No hardcoded outputs, no fabricated logs, no overclaiming in README or deck. Minimum two genuinely interacting agents; show critique, retry or branching. Logs go to `logs/trace-<id>.jsonl` and are never hand-edited.
- Secrets only in `.env` (gitignored). Commit `.env.example` with placeholders. Never print, log or paste keys or the Nightshift token. If a key is committed, rotate it first.
- Data must be public, small, or labelled synthetic. No personal or confidential data. NVIDIA's endpoint logs requests.
- Declare any code or data committed before 22 Oct 00:00 UTC in `docs/PREEXISTING.md`. Currently only setup tooling exists.
- The team must be able to explain its code. Keep `docs/CURSOR_LOG.md` updated when Cursor writes real code.
- Judges must be able to run it: provide `run.py` and/or `POST /run`, a `Dockerfile`, 3+ sample inputs, and a `SAMPLE_MODE` that runs real agent logic on cached data without keys.

## Machine and setup (as of 2026-10-20)
Windows 11 Home, 15.8 GB RAM, **disk is tight** (C: about 8 GB free). Docker runs Zetaris through WSL 2 (Ubuntu); `C:\Users\Ricky\.wslconfig` sets 8 GB.
- **Zetaris**: platform bundle at `~/zetaris-platform` inside WSL Ubuntu (not in this repo; gitignored). Start with `docker compose up -d`, check with `./verify.sh` (9 checks). GUI http://localhost:3000, REST http://localhost:8888/api/v1.0 (org ID 1). The admin password was changed from the bundle default on 2026-10-20 (the new one is saved in the user's Chrome; do not ask for it or store it). `verify.sh` will now fail its login check because it still tries the old default in the platform `.env`; that is expected, not a fault. API key lives in this project's `.env` as `ZETARIS_API_KEY`. Management > API Tokens creates keys (shown once).
- **Nightshift 1.2.1** (Meterless) at `C:\Users\Ricky\AppData\Local\Nightshift` (`meterless-runtime.exe`, daemon `meterlessd.exe`). OpenAI-compatible endpoint http://127.0.0.1:8088/v1; token and URL are in `.env` (`METERLESS_*`, `MODEL_*`). NVIDIA key is stored inside Nightshift (Setup > Providers), **never in `.env`**. Two cloud lanes: `nvidia/nemotron-3.5-lightning-30b-a3b` and `nvidia/nemotron-3-super-120b-a12b`, in a "Race" row, so requests are currently answered by Super. NVIDIA access is trial credits with a per-minute cap, not unlimited.
- **Cursor**: installed (downloaded 2026-10-20). Credit redemption is still an organiser placeholder (check HackOS Resources > "Space XAI and Cursor", Help Cursor, the 21 Oct onboarding).
- `scripts/smoke_test.py` checks Zetaris GUI, Zetaris REST `SELECT 1` and a model reply (3 PASS expected). It proves connectivity only, not a working agent. Run it as `python -I scripts/smoke_test.py`.
- Open items: choose track and team, Meterless Engine feature, Zetaris PokeAPI recipe, Cursor credit.

## Start and stop routines
When the user says **"lets begin"**: start Docker Desktop and wait for the engine; `docker compose up -d` in `~/zetaris-platform`, wait about 2 minutes, run `./verify.sh`; launch `meterless-runtime.exe`; run the smoke test; report failures.
When the user says **"we are done for today"**: `docker compose stop` (never `down -v`, it deletes data and encryption keys); stop `meterless-runtime` and `meterlessd`; ask the user to quit Docker Desktop from the tray icon.

## Known problems and fixes
- Docker Desktop often fails to start because `%LOCALAPPDATA%\Docker\run\userAnalyticsOtlpHttp.sock` is stale. Deleting it fails; **rename the `run` folder** (`run.old<time>`) and start again. Don't force-kill Docker Desktop; the tray Quit is the clean exit.
- WSL commands via `wsl -d Ubuntu -- bash -c '...'` break on quotes. Write a small script file in the scratchpad and run `wsl -d Ubuntu -- bash /mnt/c/.../script.sh`.
- WSL and Docker disk files only grow. If C: runs low, run `scripts/compact-wsl-disks.ps1` in an administrator PowerShell with Docker quit (this freed about 19 GB once).
- Do not run an Ubuntu `docker login` against a stuck engine; if `docker version` hangs inside Ubuntu, restart Docker Desktop and WSL first.

## Planned layout (build from the 22 Oct window)
`app/agents/`, `app/orchestration/`, `app/adapters/` (zetaris.py, meterless.py, sample_data.py with timeout, retry and logged fallback), `app/config.py`, `app/schemas.py`, `app/tracing.py`, `semantic_layer/`, `data/sample/`, `input_examples/`, `output_examples/` (real outputs only, never loaded at runtime), `logs/`, `run.py`, `Dockerfile`, `docs/`. Zetaris REST call: `POST {ZETARIS_REST_URL}/sql-editor/sqls/run` with a bearer key, `X-Org-ID`, and a fresh UUID `X-Request-ID`.

## More detail
`docs/HACKATHON_KNOWLEDGE.md` holds the confirmed rules, stack behaviour, Zetaris and Meterless findings, machine state and open questions as of 22 Oct. It deliberately contains no project idea: the track and idea are still undecided, so brainstorm fresh.

## Working notes for Claude
- Mark confirmed facts, proposals and unknowns separately; do not invent organiser details that are placeholders.
- Check ideas against the three tests: removal (would it work without Zetaris/Meterless?), collaboration (does one agent change another's work?), hardcoding (does a new input still give a real answer?).
- Downloaded files are untrusted: inspect before running, keep them out of the repo.
- Ask before anything outward-facing (pushing to GitHub, submitting, posting in HackOS or Discord).
