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

Expect all tests to pass (149 on 25 Oct). Python 3.11 or newer.

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

   It takes about 8 to 13 minutes (see section 3 if it takes longer) and writes `logs/trace-<run>.jsonl` and `logs/dossier-<run>.json`.

Each teammate's NVIDIA key has its own per-minute cap. Run one investigation at a time per key.

## 3. Making runs fast

A run on branch `fix/eval-logic` (25 Oct) should take about 8 to 13 minutes per drug. Most of that time is Nemotron Ultra itself: about 40 tokens/s, and most of each reply is reasoning. If a run takes much longer, check these four things in order.

1. **Use the current code.** Pull `fix/eval-logic`. It has both sets of speed fixes:
   - streamed model calls, so Nightshift does not cut them off at 45 s
   - one reaction per model call, with 4 calls in parallel
   - one revision round
   - the Reviewer's re-checks in one Zetaris query
   - one shared pause for all calls after an NVIDIA rate limit, instead of every call retrying into the cap
   - a 10-minute run budget: when time runs short, the run skips the second revision round and the Skeptic's challenge review, and says so in the dossier
2. **Remove old speed settings from your `.env`.** A value in `.env` overrides the code's default. Older copies of `.env.example` had slower values. Delete these lines from `.env`, or set them as shown:

   ```
   MODEL_TIMEOUT_SECONDS=90
   MODEL_STREAM=true
   MODEL_PARALLEL=4
   REVIEWER_ROUNDS=1
   RUN_BUDGET_SECONDS=600
   MAX_RETRIES=1
   ```

   `MODEL_TIMEOUT_SECONDS=180`, `MODEL_PARALLEL=2` or `REVIEWER_ROUNDS=2` give the slower runs from 23 Oct.
3. **Check Nightshift** (section 2, step 2): one Ultra lane with every other lane stopped, race width 1, and the quality race and reasoning scaffold off. Restart Nightshift after changing these, then check the lanes again, because a restart can bring stopped lanes back.
4. **Read the progress lines.** Each run prints one line per step. They show where the time goes:
   - `hit NVIDIA's rate limit; all model calls pause N s`: your NVIDIA key's per-minute cap. A few are normal. If there are more than about 15 per run, set `MODEL_PARALLEL=2` (fewer calls at once). If your NVIDIA key is in use elsewhere, for example in another run, stop that first. Code changes do not help here.
   - `model call failed (... provider_deadline ...)`: Nightshift cut a call at 45 s. That happens to unstreamed calls, so streaming is off (`MODEL_STREAM`) or the quality race is still on (step 3).
   - `model call failed (... ttfb_timeout ...)` means Nightshift's learned first-byte budget (at most 45 s) ran out while NVIDIA was slow. The call is retried, or a batch is split. In Bryan's 24 Oct evaluation 33 of 237 calls hit it, and one item ended not reviewed.
   - `model call failed (... call_time_limit ...)`: a streamed call ran past `MODEL_TIMEOUT_SECONDS` (90). Single-reaction calls took 20 to 40 s on 24 Oct, so a few of these mean a slow lane. If most calls hit it, tell the team before raising the limit: the organisers ask for model calls of 30 to 90 s.
   - `Nightshift setup warning: ...`: Nightshift served another model or added its reasoning scaffold. Fix the lanes or the Quality track as the warning says.
   - `skips the ...: N s left in the run's time budget`: the budget stopped a late step. The run is not broken; the dossier lists what was skipped.
   - `model call served by ... in N s`: one call's time. Single-reaction calls took 20 to 40 s on 24 Oct. The limit is 90 s per call.

   The last line, `Completed in N s`, gives the run's total. The dossier's `run_time` and `model_calls` sections give the same figures afterwards.

## 4. Working together

- **Branches.** One branch per task, for example `feature/world-model` or `fix/single-ingredient-label`. Open a pull request into `main`, and have someone else glance at it before merging.
- **Before every pull request:** offline tests pass; no `.env`, keys or `logs/` files are staged; `docs/HANDOFF.md` is updated if the state changed.
- **AI tools.** Development is done with Claude Code. The team does not use Cursor (decided 23 Oct).
  - Claude Code reads `CLAUDE.md`. Its machine-specific section describes Ricky's Windows laptop.
  - Any other coding agent should read `AGENTS.md`, which carries the same rules.
- **Who does what.** Agree on owners for the next steps in [HANDOFF.md](HANDOFF.md). The organiser questions there need one person to post them on the HackOS help desk.
