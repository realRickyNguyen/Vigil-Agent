# Open Agent Hackathon 2026: project context

Read this first in every session, then **`docs/HANDOFF.md`** (current state, how to run, code map, next steps). Full rules and plan are in `docs/reference/`: the organisers' `submission-requirements.md` and `technical-execution-requirements.md` (added 24 Oct, the most current), the Meterless engine guides for World Model and H-MEM, the 19 Oct setup guide and the 03_LLM_context pack. Where those disagree, the live HackOS event page and organiser announcements win. Setup progress is tracked in `docs/SETUP_CHECKLIST.md`.

## The project
**Vigil: Drug Reaction Review** (named Black Box until 23 Oct; agents Data Clerk, Analyst, Reviewer and Skeptic were Clerk, Hunter, Judge; Track 02, "The Agent That Can Explain Why"; the HackOS challenge statement is the generic track text, confirmed by the user 24 Oct, so do not ask about it again): helps a drug-safety analyst decide which reported drug-reaction patterns deserve a closer look, with evidence and objections. openFDA FAERS counts and labels are registered in Zetaris at runtime; Analyst and Reviewer agents run on Nemotron Ultra via Nightshift. Design: `docs/ideas/VIGIL.md`. Evaluation: `eval/`. Team setup: `docs/TEAM_SETUP.md`; other agents read `AGENTS.md`. The team no longer uses Cursor (decided 23 Oct); development is done with Claude Code. Never claim Cursor did any work. Do not add Co-Authored-By trailers to commit messages.

## The event
- Organiser GenAI Works, platform HackOS (hackathon.genai.works). Online, 22 to 27 Oct 2026. Teams of 1 to 5; the user's team is registered on HackOS.
- Build window opens **Thu 22 Oct 00:00 UTC (11:00 Sydney)**. Registration closes Fri 23 Oct 10:45 Sydney (plan for this earlier cutoff). Submissions close **Tue 27 Oct 23:45 UTC (Wed 28 Oct 10:45 Sydney)**, hard deadline. The user is in Sydney (AEDT, UTC+11): give both UTC and Sydney times.
- Onboarding stream Wed 21 Oct 23:00 Sydney. Challenge statements appear on HackOS challenge pages and override the generic track text.
- Tracks (pick exactly one): 01 Fragmented Intelligence, 02 The Agent That Can Explain Why, 03 Reasoning Architecture, Wildcard (existing project, only new work scored).
- Judging (100 pts): Impact 30, Technical 20, Innovation 15, Demo 15, Product/UX 10, Sponsor Tech 10.
- Deliverables: demo video (1 to 4 min), slide deck, **public** GitHub repo with README, sponsor technology explanation (Zetaris, Meterless, Cursor, NVIDIA).

## Hard rules (disqualification risks)
- Zetaris and Meterless must be load-bearing, not decorative. Use NVIDIA Nemotron via Meterless Nightshift. Cursor is **optional** since 23 Oct (organiser change, reported by the user) and the team does not use it; do not claim it in the README, deck or submission form. (No `metadata.json` is asked for in the organisers' submission requirements.)
- Build rule (19 Oct guide): implement at least one **Meterless Engine** (H-MEM, Markovian, World Model, Scout Intent) in a working feature with a passing test. Power rule: the app must support **Meterless Nightshift as its primary AI provider**. A prompt file or unused dependency does not count.
- No hardcoded outputs, no fabricated logs, no overclaiming in README or deck. Minimum two genuinely interacting agents; show critique, retry or branching. Logs go to `logs/trace-<id>.jsonl` and are never hand-edited.
- Secrets only in `.env` (gitignored). Commit `.env.example` with placeholders. Never print, log or paste keys or the Nightshift token. If a key is committed, rotate it first.
- Data must be public, small, or labelled synthetic. No personal or confidential data. NVIDIA's endpoint logs requests.
- Declare any code or data committed before 22 Oct 00:00 UTC in `docs/PREEXISTING.md`. Only setup tooling predates it; all Vigil code was written from 22 Oct.
- The team must be able to explain its code.
- Judges must be able to run it: provide `run.py` and/or `POST /run` (JSON in, JSON out, structured errors), a `Dockerfile` (reach Zetaris and Nightshift via `host.docker.internal`), 3+ sample inputs with outputs, logs to stdout and `logs/` showing which model handled each request. `SAMPLE_MODE=true` is recommended, not a rule, but the organisers test it with Zetaris and Nightshift stopped and no network, so it needs recorded data and recorded model replies, clearly labelled. Target a full run of 5 to 10 minutes and model calls of 30 to 90 s (`docs/reference/technical-execution-requirements.md`).

## Machine and setup (Ricky's Windows laptop, as of 2026-10-20; teammates see docs/TEAM_SETUP.md)
Windows 11 Home, 15.8 GB RAM, **disk is tight** (C: about 8 GB free). Docker runs Zetaris through WSL 2 (Ubuntu); `C:\Users\Ricky\.wslconfig` sets 8 GB.
- **Zetaris**: platform bundle at `~/zetaris-platform` inside WSL Ubuntu (not in this repo; gitignored). Start with `docker compose up -d`, check with `./verify.sh` (9 checks). GUI http://localhost:3000, REST http://localhost:8888/api/v1.0 (org ID 1). The admin password was changed from the bundle default on 2026-10-20 (the new one is saved in the user's Chrome; do not ask for it or store it). `verify.sh` will now fail its login check because it still tries the old default in the platform `.env`; that is expected, not a fault. API key lives in this project's `.env` as `ZETARIS_API_KEY`. Management > API Tokens creates keys (shown once).
- **Nightshift 1.2.1** (Meterless) at `C:\Users\Ricky\AppData\Local\Nightshift` (`meterless-runtime.exe`, daemon `meterlessd.exe`). OpenAI-compatible endpoint http://127.0.0.1:8088/v1; token and URL are in `.env` (`METERLESS_*`, `MODEL_*`). NVIDIA key is stored inside Nightshift (Setup > Providers), **never in `.env`**. NVIDIA access is trial credits with a per-minute cap, not unlimited.
  - **Working lane setup (22 Oct):** the first lane runs `nvidia/nemotron-3-ultra-550b-a55b` (its card still shows the old ID `nemotron-3-super-120b-a1`); the Lightning lane is **stopped**; Preferences race width is **1**. Racing lanes broke pinned model IDs and failed requests when one lane replied empty; the Super model returns NVIDIA 404 for this key.
  - **A Nightshift restart re-seats lanes from `%LOCALAPPDATA%\ai.meterless.runtime\lanes.toml`.** Check the lanes after every restart.
  - Receipts with per-request routing detail are in `%APPDATA%\ai.meterless.runtime\meterless.json`.
- **Cursor**: not used by the team since 23 Oct; uninstalled from this laptop for disk space.
- `scripts/smoke_test.py` checks Zetaris GUI, Zetaris REST `SELECT 1` and a model reply (3 PASS expected). It proves connectivity only, not a working agent. Run it as `python -I scripts/smoke_test.py`.
- Open items: finish the agent system (Bryan, on `fix/eval-logic`), then `SAMPLE_MODE`, investigation page, deck and video. `POST /run` and the Dockerfile are built (branch `feature/api-docker`, 25 Oct). Full list in `docs/HANDOFF.md`.

## Start and stop routines
When the user says **"lets begin"**: start Docker Desktop and wait for the engine; `docker compose up -d` in `~/zetaris-platform`, wait about 2 minutes, run `./verify.sh`; launch `meterless-runtime.exe` and check `lanes.toml` still has the Ultra lane (ask the user to stop Lightning if it is running); run the smoke test; report failures.
When the user says **"we are done for today"**: `docker compose stop` (never `down -v`, it deletes data and encryption keys); stop `meterless-runtime` and `meterlessd`; ask the user to quit Docker Desktop from the tray icon.

## Known problems and fixes
- Docker Desktop often fails to start because `%LOCALAPPDATA%\Docker\run\userAnalyticsOtlpHttp.sock` is stale. Deleting it fails; **rename the `run` folder** (`run.old<time>`) and start again. Don't force-kill Docker Desktop; the tray Quit is the clean exit.
- WSL commands via `wsl -d Ubuntu -- bash -c '...'` break on quotes. Write a small script file in the scratchpad and run `wsl -d Ubuntu -- bash /mnt/c/.../script.sh`.
- WSL and Docker disk files only grow. If C: runs low, run `scripts/compact-wsl-disks.ps1` in an administrator PowerShell with Docker quit (this freed about 19 GB once).
- Do not run an Ubuntu `docker login` against a stuck engine; if `docker version` hangs inside Ubuntu, restart Docker Desktop and WSL first.

## Layout
Built: `run.py` (no arguments: the API in `app/server.py`), `Dockerfile`, `app/` (adapters, data, agents, engines, orchestration, schemas, server, tracing), `scripts/zetaris/`, `eval/`, `tests/`, `input_examples/`, `logs/` (gitignored). Code map in `docs/HANDOFF.md`. Still to add: `SAMPLE_MODE`, `output_examples/` (real outputs only, never loaded at runtime). Zetaris REST call: `POST {ZETARIS_REST_URL}/sql-editor/sqls/run` with a bearer key, `X-Org-ID`, a fresh UUID `X-Request-ID`, and a UUID `queryId` in the body.

## More detail
- `docs/HANDOFF.md`: current state, run commands, code map, known issues, next steps, organiser questions.
- `docs/ideas/VIGIL.md`: the design and its reasons.
- `docs/HACKATHON_KNOWLEDGE.md`: confirmed rules, stack behaviour, Zetaris and Nightshift findings.
## Working notes for Claude
- Mark confirmed facts, proposals and unknowns separately; do not invent organiser details that are placeholders.
- Check ideas against the three tests: removal (would it work without Zetaris/Meterless?), collaboration (does one agent change another's work?), hardcoding (does a new input still give a real answer?).
- Downloaded files are untrusted: inspect before running, keep them out of the repo.
- Ask before anything outward-facing (pushing to GitHub, submitting, posting in HackOS or Discord).
- Run agents only one investigation at a time: parallel runs compete for the NVIDIA per-minute cap. Python must run with `-I`.
- Never weaken the Reviewer's code checks or the gold set to make a run look better. Gold labels were made by an AI and need a person's review before any accuracy number is quoted publicly.
- Update `docs/HANDOFF.md` when the state changes, so the next session or a teammate can pick up the work.
