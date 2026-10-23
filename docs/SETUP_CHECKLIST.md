# Setup checklist (updated Thu 22 Oct 2026 against the 21 Oct setup guide PDF)

Build window opens Thu 22 Oct 11:00 Sydney. Onboarding is Wed 21 Oct 23:00 Sydney. Registration closes Fri 23 Oct 10:45 Sydney (plan for the earlier time).

## Machine status (checked 20 Oct)
- [x] Git 2.40, Python 3.11, Node installed
- [x] Docker Desktop 27.3.1 installed and running (WSL memory set to 8 GB in `C:\Users\Ricky\.wslconfig`)
- [x] WSL 2 Ubuntu working; Zetaris runs from `~/zetaris-platform` inside it
- [x] Cursor installed (20 Oct), later uninstalled; the team dropped Cursor on 23 Oct
- RAM 15.8 GB (tight for Zetaris's 8 GB; close other apps), C: drive 22.6 GB free (needs 15 GB+)

## Data: Zetaris (slow, start first)
- [x] Register at https://cloud.enterprise.zetaris.com/register
- [x] Download the platform bundle and the registry sign-in command from "Run locally"
- [x] Docker Desktop: Settings > Resources, set 4 CPUs and 8 GB; enable WSL integration for Ubuntu
- [x] In WSL: unzip the bundle to `~/zetaris-platform`, run the registry login, `./preflight.sh`
- [x] (not needed: bundle .env works as shipped) Edit the platform `.env` (admin email, password, org; keep the guide's laptop settings) BEFORE first start
- [x] `docker compose config --quiet`, `docker compose pull`, `docker compose up -d` (30 to 45 min)
- [x] `./verify.sh` shows 9 passing checks
- [x] GUI at http://localhost:3000: SQL Editor works (22 Oct)
- [x] PokéAPI recipe done 22 Oct: pikachu_abilities_table returns 2 rows (static, lightning-rod)
- [x] Create a user API key in the GUI, save it in this project's `.env` as ZETARIS_API_KEY (set; admin password changed 20 Oct)

## Build: Cursor
Dropped 23 Oct: Cursor became optional, no credits came, and the team develops with Claude Code.

## Build: Meterless
Updated 19 Oct guide: Meterless is REQUIRED in two ways. Using the prompt library alone does not count.
- [x] (World Model, merged 23 Oct) Build rule: implement at least one Meterless Engine (H-MEM, Markovian, World Model or Scout Intent) in a working feature, with a passing test. Prompts: meterless.ai/engines.html
- [ ] Power rule: the app must support Meterless Nightshift as its primary AI provider (use the POWER "Add Meterless as a provider" prompt)

## Power: Nightshift + Nemotron
- [x] Install the Windows edition of Nightshift from meterless.ai (email verification needed); keep it running
- [x] Get a free NVIDIA key at build.nvidia.com/models and paste it into Nightshift > Setup > Providers > NVIDIA (not into `.env`)
- [x] NIGHT tab > LANES: add a Nemotron model (guide examples: nvidia/nemotron-3.5-lightning-30b-a3b and nvidia/nemotron-3-super-120b-a12b; copy exact IDs from your catalog)
- [x] Console (top right): copy the Runtime URL and API key into `.env` as METERLESS_BASE_URL / METERLESS_RUNTIME_TOKEN
- [x] Test with the guide's curl command; check which model actually answered (meterless/auto may pick a non-NVIDIA model)

## Final check
- [x] `.env` filled in (20 Oct). Re-run `python -I scripts/smoke_test.py` each day: 3 PASS expected
- [ ] Keep the output as evidence (no secrets)

## Questions to put to organisers (#help desk on HackOS)
1. ~~How do we redeem the Cursor credit?~~ No longer needed: Cursor dropped 23 Oct.
2. When and where is the vibe coding workshop? (also a placeholder)
3. How do judges reach a local Zetaris instance? (guide says everyone runs it locally)
Answered by the 19 Oct guide: Meterless is required as provider and as an Engine; Nemotron runs through Nightshift.


## Changes in the 21 Oct guide (PDF, 30 pages)
- Eligibility: Zetaris and Meterless must be running on your own machine.
- Lane 2 example ID is `nvidia/nemotron-3.5-super-vl-120b-a12b`; ours is `nvidia/nemotron-3-super-120b-a12b`. Copy IDs from your own catalog.
- `meterless/auto` may pick a non-NVIDIA model. Pin a Nemotron lane (or show an explicit Nemotron task) for the NVIDIA award evidence.
- Vibe coding workshop was 20 Oct 9 PM PST (YouTube link in the guide). Already past.
- Cursor credit redemption is still not explained: check HackOS Resources.

## Still open (updated 22 Oct, 17:00 Sydney)
- [x] Team registered on HackOS (22 Oct). Project Black Box, Track 02 provisionally
- [ ] Read the Track 02 challenge statement on HackOS
- [x] Cursor: dropped 23 Oct, nothing to redeem
- [x] Zetaris GUI and PokeAPI recipe done (22 Oct)
- [x] Meterless Engine feature with a passing test (Build rule): World Model merged 23 Oct; whether a Python port counts is an open organiser question
- [x] App uses Nightshift as primary provider (Power rule): every agent call goes through Nightshift, pinned to Nemotron Ultra
- [x] `run.py` entry point (22 Oct)
- [ ] Judge-facing: public repo, Dockerfile, `POST /run`, `SAMPLE_MODE`, 3+ sample inputs (1 so far)
- [ ] Nightshift lanes: Ultra lane running, Lightning stopped, race width 1 (done 22 Oct; re-check after every restart)

## Daily status (22 Oct, after "lets begin")
- Docker engine 27.3.1 needed the `run` folder rename again. Zetaris and Nightshift up. Smoke test 3 PASS.
- `verify.sh` shows 6/9: bootstrap and the two login checks fail because they still use the default admin password. Expected since the password was changed on 20 Oct; not a fault.
