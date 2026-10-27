# Handoff: investigation page UI fixes (26 Oct 2026)

Continue the UI work on `app/static/index.html`, the investigation page served at `GET /`. Read `CLAUDE.md`, then this file.

## Current state (26 Oct, evening): read this first

Everything from "The three fixes" down to "Then" step 3 below is **done**: the JS was written, a polish pass ran, and the second critique scored **26/40** (`.impeccable/critique/2026-10-26T08-20-54Z__…md`). Drafts kept per item came after that critique. A later session then fixed the second critique's P1s and P2s and made the three changes listed after them; all of this is committed together with this file:

- **Contradictory signals.** The objection caption now says what the Reviewer decided, e.g. "The Reviewer's strongest objection, though it accepted the finding" (`objectionBy()`). The Skeptic block title explains "no challenge" (the PRR stays above 2) beside a 30% drop (`skepticOutcome()`), and that reason ends "though not below 2" (`reasonText()`). Rows for items the agents did not reach say "Status", not "Against".
- **Queue above the fold.** The figures are more compact and "Since the last run" moved below the queue at every width. At 1440×900 the first row starts at y=652 (was 922); on a 375px phone it starts at y=1174 (was 1618). The sticky decision panel is 199px at rest (was about 275): the note starts one line tall, and the name field and Save sit in one row.
- **Accessibility.** The reaction name is the row's button (`.rowbtn`, `aria-expanded`, `aria-controls`). Rows are no longer focusable `tr`s, and an open row has class `open`. The decision options are a radiogroup with arrow keys and roving tabindex (`choose()`, `radioKeys()`, `radios()`), also on the landing page. `--muted` is now #636974, at least 4.65:1 on every ground. The name placeholder is covered. The Skeptic and safety-net tables scroll inside `.table-wrap`, so nothing widens the page at 375px.
- **Leaked terms and repetition.** Query links read "Its SQL" or "Its N SQL queries", not hashes; one link opens all of its queries. The cluster block no longer repeats the country shares. IC and its lower 95% bound are separate rows.
- **Checked:** 313 tests pass with `.venv\Scripts\python.exe -I -m pytest tests`. Plain `python` on this machine resolves to Inkscape's Python, which has no pytest. The impeccable detector is clean. The tasteskill inspector reports 0 FAIL (`node <skill>/scripts/inspect.mjs <url> --app`; Node 24 is now installed). Browser checks were done at 1440×900 and 375×812. One test decision (Escalated, SPUTUM DISCOLOURED) was saved on replay run `20261026T082903Z-753f59`.
- **Investigations drawer.** "Investigations" in the top bar used to open the sidebar in the page flow, with the landing page carried on beneath it. It is now a 400px drawer from the left, over a dimmed page (`body.drawer`, `#scrim`, `setSide()`), with a header and Close button. Escape, Close or a click on the dimmed page closes it and returns focus to the button. The form sits in a tinted block; the list ("Past investigations") fills the rest and scrolls on its own. On phones and short screens the whole drawer scrolls. It is used on the landing page at every width and on an investigation below 1100px. An alternative, a centred drop-down from the top bar that unrolls like a blind, is kept in this branch's history: it is commit `c343721`, undone by `62e936c`. To bring it back, run `git revert 62e936c`.
- **Investigations panel, current (replaces the drawer).**
  - **Layout:** "Investigations" opens a panel that floats in the middle of the screen, apart from the top bar. It is centred horizontally and vertically, up to 880px wide with at least 24px all round, and on phones 12px all round in one column.
  - **Behind it:** the whole page, top bar included, is dimmed (`.scrim`, z-index 25, above the bar's 20).
  - **Inside:** the form is on the left and past investigations on the right.
  - **Animation:** it unrolls like a blind (`blind-down`) and rolls up on close (`blind-up`). A 320ms timer also closes it if no frames are drawn.
  - **Semantics:** while floating it is `role="dialog"` with `aria-modal`.
  - **Code:** `body.floating` and `setSide()`.
- **Landing page before any run.** `logs/` and `state/` are not in the repo or the Docker image, so judges start with no runs. Until a machine has finished one, the landing page's item block on the right comes from `GET /example`.
  - **What it is:** a replay of the recorded montelukast run, made once per server start in a temporary folder (`Runner.example()` in `app/server.py`), outside `GET /runs` and the World Model.
  - **Caption:** "An example result. Your own results appear here once you run an investigation."
  - **What stays hidden:** the sections below the hero still show only the machine's own runs.
  - **Test:** `test_the_example_is_a_replay_made_once_outside_the_run_list`.
- **Wide screens.** From 1500px, the Analyst's summary and "How the agents got here" share a row (`.pair`).
- **Browser Back.** Going Back from a run to `/` now shows the landing page (`goHome()` from `hashchange`), instead of leaving the run on screen.
- **Not done:** the third critique (compare with 26/40); a glossary for PRR, IC and reporting cluster; decision shortcuts and batch close. Field names inside model text (for example "report_sources flag" in an objection) are left verbatim, since that text is the model's own.

Branch: `feature/investigation-page`. Nothing from this session is committed. The working tree already held uncommitted work from before this session: `README.md`, `app/config.py`, `app/server.py`, `app/static/index.html`, `docs/HANDOFF.md`, `tests/test_server.py` and `app/static/fonts/`. Do not discard any of it. Commit only when the user asks, and with no Co-Authored-By trailer (CLAUDE.md).

## What happened this session

- **Design canvas**: the current UI (montelukast run plus landing view) is drawn at https://claude.ai/artifact/JrwJ2eBDSAEDCuMejxFMeH. It is private.
- **Figma**: the file "Vigil UI" is at https://www.figma.com/design/CDXFTkqNsfBfsgDMYMFXWe.
  - It is in the drafts of the team "SKDB", on the Starter plan.
  - It has one page, with frames `1:2` (investigation) and `2:2` (landing). Both are plain layers, with no styles or components.
- **Skills**: `impeccable` (4.7.1) and `design-taste-frontend` (taste-skill) are installed in `C:\Users\Sally\.claude\skills\`, outside the repo.
  - Impeccable's auto-run hooks were deliberately not installed.
  - Its engine is cached at `C:\Users\Sally\.impeccable\bin\impeccable.exe`; the user approved that download.
  - Node.js is not installed, so taste-skill's scripts don't run. Its written references do work.
- **Impeccable critique** of `app/static/index.html`: **25/40 (Acceptable)**, 3 P1 and 2 P2. It is saved at `.impeccable/critique/2026-10-26T07-37-06Z__app-static-index-html.md` (untracked; read it first).
- **The user's choices**:
  - fix the top 3 P1 issues, in order;
  - then run `/impeccable polish` and re-run `/impeccable critique`;
  - keep the decision wording ("Agree with Vigil" / "Close, no action" / "Escalate for assessment");
  - nothing is off-limits (the API may change if needed).

## The three fixes

1. **Decide-and-advance loop.** The decision panel currently comes before the evidence. Move it to the end of the open item and make it sticky at the bottom of the screen. Put "Why it needs you" at the top. Allow one open item at a time. After a save, open the next undecided item ("Save and open next").
2. **"Needs you" clarity.** Today its 7 items mix 2 review-next items, 2 items Vigil set aside but flagged, and 3 pending items, all shown as "To decide".
   - Show each row's reason.
   - Explain what the decision means for each kind of item.
   - Hide "Agree with Vigil" on items Vigil made no call on (pending, not reviewed or failed), since there is nothing to agree with.
3. **Phone layout.** Below 900px, collapse the sidebar behind an "Investigations" toggle. Below 760px, show queue rows as stacked blocks, with the open item spanning the screen width.

## Current state of `app/static/index.html`: CSS is done, JS is not

The page is **temporarily inconsistent** until the JS below is written.

The following CSS changes are already in:
- `.src` is now 12px (was 11px).
- `.side-toggle` styles exist. Below 900px the sidebar is `display: none` unless `.layout.side-open` is set.
  - **On phones the sidebar is unreachable until the toggle button is added.**
- The `.search` placeholder now uses `--muted` with `opacity: 1` (fixes the 4.3:1 contrast finding).
- The active run's 2px navy left bar is gone (Impeccable bans coloured side borders). The active run now shows a grey background and an accent-coloured drug name.
- The `.kicker` CSS was **removed**, and `h1.title` is now 32px (was 40px).
  - **The JS still emits `class="kicker"` in `render()`, `follow()`, `showError()` and `intro()`.**
- Phone stacked-queue CSS exists, using grid areas `tw rank rx` / `call` / `prr` / `yours`.
  - **It expects classes `callc` and `prrc` on the "Vigil's call" and PRR `<td>`s in `queueRow()`, which are not added yet.**
- `.why .need` and `.why .need .more` row styles exist.
- `.decide` is now sticky (`bottom: 12px`, small shadow, `margin-top: 8px`). New `.decide .what`, `.decide .req` and `.needs` block styles exist.
- **`.doc h4` was renamed to `.doc h3.bh`**, which fixes the h2→h4 heading skip. **`blk()` still emits `<h4>`, so detail headings are unstyled until it emits `<h3 class="bh">`.**
- The Skeptic table gets left padding on the text cell after a right-aligned number (fixes "5.11possible").

## JS still to write

All of this is in the `<script>` of `app/static/index.html`:

- **Header and sidebar toggle.**
  - Add `<button class="side-toggle" id="side-toggle" type="button" aria-expanded="false" aria-controls="sidebar">Investigations</button>` in `.topbar`, and `id="sidebar"` on `<aside>`.
  - The button toggles `.side-open` on `.layout`.
  - Close the panel when a run is opened (`openRun`, form submit).
  - Open it by default on the landing view (`intro()`), so a phone user can start a run.
- **Kickers.** Remove every `<p class="kicker">`.
  - In `render()`, move the date into `.facts`, e.g. "Investigated <b>Monday 26 October 2026, 12:41</b>".
  - In `follow()`, show "In progress" plus the run ID in `.facts` or next to the elapsed time.
  - In `showError()`, keep the type in the notice.
  - In `intro()`, fold "openFDA FAERS and drug labels" into the lead.
- **Replay wording.** In replay (`d.sample_mode`), the facts should say "Replayed in N s" instead of "Run took N s of 600 s".
- **One open item.** In `toggle()` and `onOpenItem()`, clear `openRows` before adding, and remove any other open `tr.detail`.
- **`detail()` order.**
  - `head` = status line, the objection blockquote, then a `.needs` block: `<h3>Why it needs you</h3>` plus a list. Take the list from `manual_review.reasons`, mapped by `needReasons()` below; a review-next item without manual review gets "Vigil ranks it review next".
  - Remove the old "Why it needs you" side `blk`.
  - After that come the doc columns, then Evidence, then `decidePanel(x, i)` **last**.
- **`needReasons(x)`.** Map `x.manual_review.reasons`, capitalising each. Replace the internal "workflow status is pending" with "Not reached by the agents in this run".
  - Real reason strings in the montelukast run: "label coverage is unclear"; "adjusting for albuterol, omalizumab, fluticasone lowers its PRR by 30% or more"; "the Reviewer rejected a claim for it (round 1)"; "the Skeptic challenged it; adjusting for fluticasone lowers its PRR by 30% or more"; "workflow status is pending".
- **`queueRow()`.**
  - For `toDecide(x)` rows, add a `<div class="need"><span class="lbl">Needs you</span><span class="t">…first reason… <span class="more">+N more</span></span></div>` line. Skip any reason already shown in the Against line.
  - Add `class="callc"` and `class="r prrc"` to the call and PRR cells.
- **Tabs.** In `TABS`, rename "Needs you" to **"To decide"** and filter it with `toDecide`, so it matches the progress line ("N items that need a decision"). Keep the key `needs`, which the CSS uses.
- **`decidePanel(x, i)`.**
  - Add a `.what` line per kind of item:
    - review next: "Vigil ranks this for a closer look. Agree to confirm, close it, or escalate it for assessment.";
    - set aside but flagged: "Vigil set this aside (<asideReason>), but it was flagged for you. Agree keeps it set aside.";
    - no call (pending / not_reviewed / failed): "The agents did not reach this item in this run, so Vigil made no call to agree with."
  - Hide the `agree` button for the no-call kind.
  - Label the textarea "Why? (required)" with a `.req` hint.
  - Name the save button "Save and open next" when another undecided item exists in the current tab, else "Save decision".
- **`syncSave(panel)`.** Enable Save only when an option is chosen **and** the note is non-empty. Wire it with `$("#queue").oninput` on `.decide textarea`.
- **`saveDecision()`.**
  - On success, find the next item in the current tab's visible order that `toDecide` and has no decision yet, wrapping around.
  - Set `openRows = new Set([nextIndex])`, call `renderQueue()` and `drawProgress()`, scroll the next row into view, and focus its first option button.
  - If none is left, close the row and toast "All N decided. Export decisions (CSV) is at the top of the page."
- **Progress bar.** Add `aria-label="Your review progress"` on the progressbar in `drawProgress()`.
- **`blk()`.** Emit `<h3 class="bh">` instead of `<h4>`.

## Then

1. **Polish** (`/impeccable polish`). Read `C:\Users\Sally\.claude\skills\impeccable\reference\polish.md` and `craft-floor.md` before editing. Remaining small items from the critique:
   - the unexplained disabled Live button in replay;
   - the "Clinical event" context tag repeated on every row;
   - the implicit time zone in the run list.
2. **Verify.**
   - Start the app in replay mode, in the background:

     ```bash
     SAMPLE_MODE=true PORT=8765 python -I run.py
     ```
   - Create a run:

     ```bash
     curl -s -X POST http://127.0.0.1:8765/run -H "Content-Type: application/json" -d '{"input":{"drug":"montelukast"},"options":{"sample_mode":true}}'
     ```
   - Open `http://127.0.0.1:8765/#<run_id>` in the built-in browser at 1440×900 and at the mobile preset (375×812). Check that opening an item puts the evidence first and the sticky decision last.
     - Don't save decisions on runs that matter: saving writes to `state/`. A replay run is fine.
   - Run the detector:

     ```bash
     C:/Users/Sally/.claude/skills/impeccable/scripts/impeccable detect --json app/static/index.html
     ```
   - Run the tests:

     ```bash
     python -I -m pytest tests
     ```
   - Stop the server afterwards.
3. **Re-run the critique** (`/impeccable critique app/static/index.html`):
   - two isolated sub-agents (A: design review, B: detector plus browser overlay, with `live-server --background` and `stop --keep-inject`);
   - compare with 25/40;
   - save the snapshot with `critique-storage write`.
4. **Afterwards**, offered but not yet agreed:
   - update the Figma file and the design canvas to the new UI;
   - re-record the demo screens;
   - update `docs/HANDOFF.md`.

## Prompt for the next session

> Continue the investigation page UI fixes. Read `CLAUDE.md`, then `docs/UI_FIXES_HANDOFF.md`, then the saved critique in `.impeccable/critique/`. The CSS for the three fixes is already in `app/static/index.html`, but the JavaScript isn't, so the page is temporarily inconsistent. Write the JS listed under "JS still to write" (decide-and-advance loop, "To decide" clarity, phone sidebar toggle and stacked rows), keeping the current decision wording. Then run `/impeccable polish`, verify in the browser at desktop and phone width with the app in replay mode, run `python -I -m pytest tests`, and re-run `/impeccable critique app/static/index.html` with two sub-agents to compare against 25/40. Don't commit unless I ask.
