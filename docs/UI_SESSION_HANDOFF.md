# Handoff: investigation page UI session (27 Oct 2026)

Use this to continue the UI work in a new session. Read, in order:

1. `CLAUDE.md`;
2. this file;
3. **`docs/UI_GUIDE.md`**, which describes every feature of the page and where its code is. Keep it current: every UI change updates it in the same change, with a line in its change log.

`docs/HANDOFF.md` has the project as a whole. `docs/UI_FIXES_HANDOFF.md` is the older 26 Oct log.

Deadline: submissions close **Tue 27 Oct 23:45 UTC (Wed 28 Oct 10:45 Sydney)**.

## Where things stand

- **Branch:** `feature/investigation-page`. Nothing is pushed. Ask before pushing.
- **Commits from this session** (oldest first):
  - `5a9bf0c` Remove analyst decisions from the API, settings, tests and docs. This was another session's work, separated out.
  - `22408ae` Investigation page: agent mascots, run chip, paced replays, tabbed items and a UI guide. It also removes the page's decision controls; that removal was interleaved with the rest in `index.html`.
  - `905084b` SQL rows show they open, no header chip for replays, tab labels on one line.
  - The commit that adds this file: case reports as readable cards fetched live from openFDA, the "Since last run" tab removed, the logo dances, run warnings folded into one clickable bar, with the UI guide and `docs/HANDOFF.md` updated.
- **Working tree:** clean apart from the local folders below. Tests: 316 pass.
- **Never commit** `.claude/` (the local preview config), `.impeccable/` or `.taste-skill/` (local design tools). Stage files by path.
- **The user's last message had an empty item 6.** Ask what it was meant to be.

## How to work on it

- **The page:** `app/static/index.html`, one file of HTML, CSS and JS, no build step. The server is `app/server.py`.
- **Tests:** `.venv\Scripts\python.exe -I -m pytest -q tests`. Plain `python` here is Inkscape's Python, which has no pytest but does have Pillow, which `make_mascots.py` needs. `C:\Program Files\Python312\python.exe` is a plain Python.
- **Preview:** the `vigil-sample` entry in `.claude/launch.json` starts the server in sample mode on port **8000** with the `.venv` Python (moved from 8010 on 27 Oct; a live server started by hand also defaults to 8000, so only one can run at a time). A second entry, `vigil-live`, starts the same server live (`SAMPLE_MODE=false`) on 8000; it needs Zetaris and Nightshift up. Sample mode has three recordings: montelukast, isotretinoin and metformin. There are also two live runs in `logs/` that carry warnings: `20261027T043153Z-b59273` (metformin) and `20261027T052457Z-3b77ad`.
- **Inspecting the running view:** a replay ends in about 5 s on the server; the page then plays it over 15 to 20 s. To hold the view, replace `window.api` in the console so `/runs/<id>` answers `{status: "running"}`, then restore it.
- **Starting a run without leaving the current view:** `fetch("/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({drug: "metformin", options: {wait: false, sample_mode: true}})})`, then `loadHealth()`.
- **Checks to repeat after a change:**
  - look at about 1300 to 1800 px and at 375 px;
  - `document.documentElement.scrollWidth` should equal the window width (no sideways scroll);
  - every API value goes through `esc()`;
  - the tests pass.
- **Big edits:** `index.html` is large. Small Python edit scripts in the scratchpad, with an exact-match assert per replacement, worked well. Inline heredocs with mixed quotes sometimes break bash.
- **Another session may edit the same folder.** That happened this session: the decisions removal arrived between turns. Re-read before editing, and check `git status` and `git diff` before committing.
- **Commits:** no Co-Authored-By trailer (`CLAUDE.md`). Clear subject, short bullet body.

## What the user has asked for, and seems to prefer

- **Visual:**
  - less white space on big screens, while the Analyst's summary and "How the agents got here" stay **one column**;
  - things evenly spaced and responsive;
  - professional, not "AI-looking": rules and plain text over pills and circles.
- **Mascots:** Vigil and the four agents, animated, used throughout. Cheerful faces only sparingly (drug-safety tone).
- **Honesty:**
  - no "done" for an agent that may work again;
  - replays clearly labelled; their header chip says only "Investigation replay" (no agent, no clock);
  - nothing claimed beyond what is known (key set, not "connected").
- **Design choices:** for bigger design questions, the user liked being shown several real screenshot options to pick from. They chose layout A (tabs) for an open item.
- **Workflow:** the user reviews before committing, and asks for commits explicitly. Times in Sydney and UTC.

## Open items and ideas

- The empty item 6 (ask).
- The header chip has not been seen on a **live** run in the browser: the preview server only replays, and replays get no chip. The red "Stopped" state is unseen.
- The page has not been checked end to end on a live run (it needs Zetaris and Nightshift up: "lets begin" in `CLAUDE.md`).
- From the 26 Oct critiques, still open: a glossary for PRR, IC and reporting cluster.
- The landing hero and the README could mention the readable case reports.
- `docs/HANDOFF.md`'s investigation-page row now also lists the later changes and points here.
