# Team setup

How a teammate gets from a fresh clone to running Vigil. Read [HANDOFF.md](HANDOFF.md) for what the project does and what is next.

## 1. Code only: no services needed (5 minutes)

You can work on most of the code and run every test without Zetaris or Nightshift.

The repo is private: https://github.com/realRickyNguyen/genai_hackathon. Ask Ricky to add you as a collaborator first.

```bash
git clone https://github.com/realRickyNguyen/genai_hackathon.git
```

```bash
cd genai_hackathon
```

```bash
python -m pip install -r requirements.txt
```

```bash
python -I -m pytest tests -q
```

Expect all tests to pass (37 on 22 Oct). Python 3.11 or newer.

## 2. Running real investigations: your own local stack

The hackathon requires Zetaris and Meterless to run on your own machine, so each teammate who runs agents needs:

1. **Zetaris.** Follow section 1 of the organisers' setup guide (`docs/reference/Participant_Setup_Guide_updated_19Oct.md`):
   - Docker Desktop, plus WSL 2 on Windows
   - the platform bundle and registry login from your own Zetaris registration
   - `docker compose up -d`
   - then create an API key in the Zetaris GUI (Management › API Tokens)
2. **Meterless Nightshift.** Install it from meterless.ai and get a free NVIDIA key from build.nvidia.com. Put the key **into Nightshift** (Setup › Providers), never into `.env`. Then set up the lanes as described in [HANDOFF.md](HANDOFF.md):
   - one lane running `nvidia/nemotron-3-ultra-550b-a55b`
   - every other lane stopped
   - Preferences › race width 1
   - Preferences › Quality track, with the quality race and the reasoning scaffold both off. They are saved in `%LOCALAPPDATA%\ai.meterless.runtime\state\setpoints.json` as `"raceParallelism": 1`, `"qualityRace": "off"` and `"reasoningScaffold": "off"`, and take effect after a Nightshift restart. With the quality race on, Nightshift answers about half our calls without streaming and cuts them off at 45 s.

   Racing lanes breaks model pinning. Check the lanes and the Quality track again after every Nightshift restart.
3. **`.env`.** Copy `.env.example` to `.env` and fill in the Zetaris URL, key and org ID, and the Nightshift URL and Runtime token (shown in the Nightshift Console). Never commit `.env`.
4. **The shared Zetaris baseline**, once per Zetaris install:

   ```bash
   python -I scripts/zetaris/run_sql.py scripts/zetaris/openfda_baseline.sql
   ```
5. **Check, then run:**

   ```bash
   python -I scripts/smoke_test.py
   ```

   Expect 3 PASS. Then:

   ```bash
   python -I run.py --drug montelukast
   ```

   It takes 5 to 20 minutes and writes `logs/trace-<run>.jsonl` and `logs/dossier-<run>.json`.

Each teammate's NVIDIA key has its own per-minute cap. Run one investigation at a time per key.

## 3. Working together

- **Branches.** One branch per task, for example `feature/world-model` or `fix/single-ingredient-label`. Open a pull request into `main`, and have someone else glance at it before merging.
- **Before every pull request:** offline tests pass; no `.env`, keys or `logs/` files are staged; `docs/HANDOFF.md` is updated if the state changed.
- **AI tools.** Development is done with Claude Code. The team does not use Cursor (decided 23 Oct).
  - Claude Code reads `CLAUDE.md`. Its machine-specific section describes Ricky's Windows laptop.
  - Any other coding agent should read `AGENTS.md`, which carries the same rules.
- **Who does what.** Agree on owners for the next steps in [HANDOFF.md](HANDOFF.md). The organiser questions there need one person to post them on the HackOS help desk.
