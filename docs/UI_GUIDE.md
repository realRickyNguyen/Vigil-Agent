# Vigil investigation page: UI guide

Last updated 27 Oct 2026 (Sydney). **Keep this file current:** whoever changes the page updates the matching section here in the same change, and adds a line to the change log at the end.

This is the reference for the web UI: what every part does, where its code is, and the rules it follows. It describes the page as it is now. For the history of the 26 Oct design work (critiques, the Figma file, alternatives tried), see `docs/UI_FIXES_HANDOFF.md`. For the project as a whole, read `CLAUDE.md` and `docs/HANDOFF.md` first.

## Contents

1. [Files and how to run it](#1-files-and-how-to-run-it)
2. [How the page is built](#2-how-the-page-is-built)
3. [Views and navigation](#3-views-and-navigation)
4. [Top bar](#4-top-bar)
5. [Investigations panel](#5-investigations-panel)
6. [Landing page](#6-landing-page)
7. [Run in progress](#7-run-in-progress)
8. [Results of a run](#8-results-of-a-run)
9. [Review queue](#9-review-queue)
10. [An open item](#10-an-open-item)
11. [Mascots](#11-mascots)
12. [Time, dates and time zones](#12-time-dates-and-time-zones)
13. [Responsive layout](#13-responsive-layout)
14. [Design system](#14-design-system)
15. [Honesty rules the UI follows](#15-honesty-rules-the-ui-follows)
16. [Accessibility](#16-accessibility)
17. [Checking a change](#17-checking-a-change)
18. [Known gaps and ideas](#18-known-gaps-and-ideas)
19. [Change log](#19-change-log)

## 1. Files and how to run it

| Path | What it is |
|---|---|
| `app/static/index.html` | The whole UI: one self-contained file of HTML, CSS and JavaScript (about 1,800 lines). No framework, no build step and no CDN, so it works offline and in sample mode with no network. The one exception is an item's Case reports tab, which fetches from openFDA when opened and says so when it can't. |
| `app/static/fonts/` | Newsreader, Public Sans and IBM Plex Mono (SIL Open Font License), served at `GET /fonts/<file>.woff2`. |
| `app/static/mascots/` | The pixel mascots, 20 × 18 px PNGs, served at `GET /mascots/<who>-<face>.png`. They are generated, so don't edit them by hand (see [Mascots](#11-mascots)). |
| `app/server.py` | Serves the page and its API (standard library `ThreadingHTTPServer`). |
| `docs/video/mascot/make_mascots.py` | Draws every mascot sprite, for the video and for the page. |
| `tests/test_server.py` | Server tests, including the page, fonts and mascot routes. |

**Run it.** `python -I run.py` with no arguments starts the API and the page on `PORT` (default 8000). Open http://localhost:8000/.

**Sample mode (no Zetaris, Nightshift or network).** Set `SAMPLE_MODE=true` to replay the recorded runs in `samples/` (montelukast, isotretinoin, metformin). Each replay takes about 5 s on the server. The Claude Code preview uses `.claude/launch.json` (untracked), which starts sample mode on port 8000 with the project's `.venv`.

**API the page uses** (all JSON; errors are `{status: "error", error: {type, message, recoverable}}`):

| Call | Used for |
|---|---|
| `GET /health` | Top bar: models, service addresses, whether keys are set, sample mode, `busy`, `current_run`, `current_drug`, `current_sample_mode`, `stopping` (a stop was asked for), the replayable `samples`. |
| `POST /runs/<id>/stop` | Stop the run in progress (202 `{"status": "stopping"}`; 409 `NotRunning` for any other run). It ends with the error type `Stopped` (HTTP 409 on `GET /runs/<id>`) and leaves no dossier. |
| `GET /runs` | Investigations list: the run in progress (with its drug), then every dossier in `logs/`, newest first. |
| `GET /runs/<id>` | A run's status (`running`, `success` with `output.dossier`, or `error`). |
| `GET /runs/<id>/events?after=<seq>` | A run's progress lines from its trace, after a sequence number. It also returns `running` and `last_seq`. |
| `POST /run` | Start a run: `{"drug": "...", "options": {"wait": false, "sample_mode": true|false}}`. |
| `GET /example` | A replay of the recorded montelukast run, made once per server start, for the landing page before this machine has a run of its own. |

## 2. How the page is built

- **One file, in sections.** The CSS and the script are split by comment headings (`/* ---------- queue ---------- */`, `// ---------- landing ----------`). Search for those to find a part.
- **Rendering.** Plain template strings set with `innerHTML`, through two helpers: `$` (`querySelector`) and `esc()`. Every value from the API goes through `esc()` before it reaches the page. Keep it that way.
- **Main state** (top of the script): `health` (last `/health`), `runs` (last `/runs`), `current` (the run ID on screen), `shown` (`{res, d}`, the finished run on screen), `filter` (queue tab), `qSearch`, `openRows` (the open item), `pollTimer`, `sampleMode` (the form's mode). The header chip has its own `bar` object (see [Header chip](#header-chip)).
- **Routing.** The URL hash is the run ID (`/#20261027T041627Z-27277b`). An empty hash shows the landing page. `hashchange` calls `openRun()` or `goHome()`, so Back and Forward work.
- **Startup** (end of the script): load `/health` and `/runs`, then open the run in the hash, or follow the run in progress, or show the landing page.
- **One animation clock.** Any `<img data-frames="<sprite>:<face>,<face>,…">` steps through its faces every 420 ms. It is used by the logo, the agent at work and the landing line-up. It is still when the visitor asks for reduced motion, and paused while the tab is hidden.

## 3. Views and navigation

| View | Function | When |
|---|---|---|
| Landing page | `intro()` | No run ID in the hash. |
| Run in progress | `follow(runId, drug)` | A run was just started, or a running run is opened. |
| Results | `render(res)` | A finished run is opened. |
| Error | `showError(out, drug, status)` | A run failed, or no such run. |

`openRun(id)` asks `GET /runs/<id>` and chooses between `follow`, `render` and `showError`. `goHome()` returns to the landing page.

## 4. Top bar

Sticky at the top of every view.

- **Logo:** the Vigil mascot (`.brand-mascot`) beside the wordmark. It dances: every 3.6 s it hops, sways left and right and lands (CSS `vigil-dance`, pivoting at its feet), while its face changes (blink, glance, bob, a brief happy face). Still with reduced motion. The sprite canvas has clear edges, so negative margins trim them and the body centres on the wordmark. Clicking the logo goes home.
- **"Drug reaction review"**, the subtitle. It is hidden below 720 px.
- **Investigations button:** opens the Investigations panel (see [5](#5-investigations-panel)) on the landing page and on narrower screens.
- **Status area** (`#status`, built by `loadHealth()`):
  - the **header chip** (below), when there is one;
  - one bordered **model and services group**: "Nemotron 3 Ultra | ■ Zetaris | ■ Nightshift".
    - The model name is the ID with its size tokens removed. The full ID is in the tooltip. It is hidden below 720 px.
    - A square only says whether the key or token is **set**, not whether the service answers. The tooltip says so, with the address.
    - A missing key turns that part light red with "no key" or "no token".
    - In replay mode (`SAMPLE_MODE=true`) both services are faded, with "not used" in the tooltip. The header has no separate "Replay mode" label: the form, the chip and the run page say it.

### Header chip

A small box for the run in progress or the one just finished (`runChip()`, `followBar()`, the `bar` object).

- **Replays** get a plainer chip (class `rc-replay`): a square, the drug and "Investigation replay", then "· finished" (green) or "· stopped" (red) with **×**. No agent and no clock: a replay's few seconds on the server mean nothing to the viewer, and the run page plays its progress itself. On phones its label stays visible.
- **While running:** the moving mascot of the agent at work, the drug, "<Agent> working" (or "Starting"), and the time since the run started, ticking each second. `followBar()` reads the run's progress lines every 3 s itself, so the chip is current on every view.
- **When it ends:** a green square and "Finished", or a red square and "Stopped" when the outcome is an error. The time freezes at the last progress line. "Stopped" is shown only when the server says `error`. The chip waits up to 5 s for the outcome while the server still says `running`.
- **Click:** opens that run. **×** (a small round icon button) dismisses it.
- **Lifetime:** kept in `localStorage` under `vigil-runchip`, so it survives a reload and other pages of the app. It goes when:
  - the visitor opens that run's results, from the chip, the panel, a link, or by being on the run's page when it finishes (`seenRun()`, called from `render()` and after the outcome settles);
  - the visitor dismisses it;
  - a new run (live or replay) starts.

  Without storage (private windows, blocked storage) it lasts as long as the page.

## 5. Investigations panel

The `#sidebar` element: the form to start a run, and past investigations.

- **Form:** "Live" or "Recorded replay" mode (`setMode()`); the drug field (a datalist of the recordings); a hint that changes with the mode (`syncForm()`); quick links to the recordings in replay mode. On a sample-mode server, Live is disabled. Only one run at a time: the button is disabled while the server is busy.
- **Past investigations** (`drawRuns()`): drug, local time, duration, "replay" and the review-next count. It has a filter box, the running run marked "running", and times labelled with the viewer's zone ("times in GMT+11").
- **Layout:**
  - From 1100 px on a run view, it is a sticky left column.
  - On the landing page, and below 1100 px, it is a floating panel in the middle of the screen over a dimmed page (`body.floating`, `.scrim`, `role="dialog"`). It unrolls like a blind and rolls up on close.
  - Escape, Close or a click on the dimmed page closes it (`setSide()`).

## 6. Landing page

Built by `intro()`. It is full width, with no sidebar.

1. **Hero:** "Drug reactions worth a closer look", a lead paragraph, and the drug form. The field hint is "E.g. montelukast". The button reads "Start investigation" or "Replay investigation" in sample mode. Recorded replays are listed as quick picks.
2. **Hero figure:** one real queue item ("Needs you / For / Against" lines and the PRR's CI plot) from the newest finished run (`landingItem()`). It is captioned "Item N of the <drug> investigation, <time>. Open it". Before this machine has a run, it comes from `GET /example`, captioned as an example.
3. **"Numbers from SQL, not from a model":** the same item's figures as the Reviewer's code sees them, captioned "Item N, as the Reviewer's code sees it."
4. **"The agents argue before you see it":** the same item's objection and exchange, captioned "Item N: the Reviewer's objection and each round of the exchange." Sections 3 and 4 show only this machine's own runs, never the example.
5. **Sign-off:** the big "Vigil" wordmark, with the crew lined up beside it on its baseline. Vigil comes first at about 1.4× the size, then the Data Clerk, Analyst, Reviewer and Skeptic, each idling out of step (`idle(agent, shift)`). Two lines follow: data sources, and "not medical advice". They use the full width, so each is one line where the screen allows. On narrow screens the line-up drops under the wordmark.

Sections rise in as they scroll into view (not with reduced motion). The old "Recent investigations" list was removed on 27 Oct; past runs are in the Investigations panel.

## 7. Run in progress

Built by `follow()`.

- **Masthead:** the drug, "In progress", the run ID, and the clock **"■ 0:04 elapsed"** (live square, 21 px mono figures, then the word). The clock counts from the run's start, taken from the run ID's UTC time, and ticks each second.
- **Stop** (`drawStop()` in `follow()`), beside the clock, for a live run only. A click asks inline, "Stop this run? No results are kept. [Stop] Keep running". Confirming sends `POST /runs/<id>/stop`; the button becomes "Stopping…" and the state "Stopping: waiting for the calls under way", since a model call or query already sent finishes first (often seconds, at most about a minute). The page then shows the stopped view: "Stopped before it finished", how long it ran, that no results were kept, and the trace file. The button goes when the run ends, and replays never show it (they have finished on the server before the page plays them).
- **Crew stage:** the five agents (Data Clerk, Analyst, Reviewer, Skeptic, and Vigil standing for the World Model) on a centred track.
  - **Waiting:** grey, faded.
  - **Working:** drawn larger, moving, with a navy "WORKING" pill.
  - **Standing by:** full colour. An agent is never shown as "done", because it can start again; the Reviewer re-checks after the Skeptic.
  - **Track:** turns navy up to each agent that has started.
- **Speech bubble:** the latest progress line of the agent at work, on one line (ellipsis, with the full text on hover).
- **Steps list:** the same five agents as a ruled list. Each row has a number, a mascot (moving for the agent at work, grey for waiting ones), what the agent does, and its state in words on the right ("Working" with the live square, "Standing by", "Waiting"). The step at work has a light blue tint and a navy bar on its left.
- **Log:** every progress line, with its local time, the agent's mini mascot and name. It sticks to the bottom unless the visitor has scrolled up.
- **Replays are paced.** A replay ends on the server in about 5 s, so the page plays its real lines out at a readable pace (about 10 a second; 15 to 20 s for the recordings). The crew and steps move with them.
  - The masthead says "Replaying a recorded run". The clock becomes "■ 64 of 143 lines replayed" with a **Skip to the result** link.
  - Every line shown is the replay's own, marked "[replay]"; only the pace is the page's.
  - The page checks every 0.7 s during a replay (2 s for live runs).
  - **Code:** in `follow()`, the queue `queue`, the flags `replay` (it is a replay) and `paced` (play slowly until skipped), the `pump` interval, `fetchLines()` and `finish()`.
- **Live runs** show lines as they arrive. When the run ends, the page shows the results (or the error).

## 8. Results of a run

Built by `render()`, in this order:

1. **Masthead:** the drug and actions: **Export queue (CSV)**, **Download dossier** (the dossier JSON) and **Copy run ID**. Below them:
   - when it was investigated (local, with the zone);
   - the label's effective date and "FAERS data to";
   - how many reports name the drug;
   - the run time against its budget, or "Replayed in N s".
2. **Notices:** "Recorded replay" (with the live run it replays and when it was recorded), always shown in full. **Warnings** about the run (Nightshift setup warnings, degraded steps, steps skipped for time) are folded into one amber bar, "⚠ 2 warnings · Degraded steps · Skipped for time · Details". A click opens each warning's details (`details.warns`).
3. **Figures** (`fig()`): reactions screened, passing the PRR screen, assessed, accepted by the Reviewer, and to review next (the key figure).
4. **Open questions** (`drawProgress()`): four boxes.
   - **N items need you** (light red, leads); **unresolved**; **not reached**; **challenged by the Skeptic**.
   - Zeros are greyed.
   - "Need you" and "not reached" have an arrow: a click switches the queue to that tab and scrolls to it.
   - It is a 2×2 grid on phones.
5. **Review queue** (see [9](#9-review-queue)).
6. **Since the last run** (`sinceLastRun()`, World Model): what changed against earlier runs of the drug, whether the label version changed, and links that open the items.
7. **The Analyst's summary:** model text, one column across the full width.
8. **How the agents got here** (`proceedings()`): one row per step and round (Data Clerk, Analyst, Reviewer round N, Skeptic, World Model), each with its mascot and counts. A Reviewer row reads "20 reviewed: 19 accepted, 1 rejected, 0 unresolved" (`reviewed` counts every finding reviewed). One column.
   - **Each row opens the agent's history** (`onAgentRow()`, `agentHistory()`): a button with an arrow that turns and a "History"/"Hide" link, like the SQL rows. Several can be open at once.
   - **With the other agents** (`exchanges()`, from the dossier):
     - Data Clerk: what it handed the Analyst;
     - Analyst: every finding sent back, its claim round by round (changed fields in bold) and the Reviewer's verdict on each;
     - Reviewer, round N: each objection with its reason (model text) and whether it went back to the Analyst; the accepted findings, folded; the reactions it named as missing;
     - Skeptic: each co-drug check, and for a challenge the Reviewer's re-review and the Analyst's revision;
     - World Model: verdicts recorded and reopened.
     
     Reaction names open their item in the queue.
   - **In the run's trace** (`timeline()`): the agent's own lines from `GET /runs/<id>/events`, read once per run (`traceLines()`). The Analyst and Reviewer also get the orchestrator's hand-offs; the Skeptic gets the re-review its challenge set off. Counts of model calls, retries, Zetaris queries and rule decisions sit above.
     - Hand-off and result lines (`HANDOFF`) are dark, with their direction ("Analyst → Reviewer", "Reviewer → Analyst"); "Only hand-offs and results" hides the rest.
     - Times are from the run's start; a replay shows each line's place in the trace (#seq), as its lines come out within seconds.
     - A Reviewer row shows the Reviewer's lines from every round (rounds overlap in time) and highlights that round's verdicts.
     - If the trace is not in this server's `logs/`, the panel says so.
9. **Appendices**, folded. Each summary has an arrow that turns, a hover tint and a "Show details"/"Hide details" link:
   - the **safety net** (serious terms outside the screen, for a person to review; not signals);
   - **World Model** verdicts across runs;
   - **Limits and model calls**: untested factors; Nightshift call counts (served by another model, memory injected, without a receipt); the model; the trace file.
10. **Colophon:** the FAERS caveat.

**CSV export columns:** run_id, drug, label_effective, faers_data_to, replay_of, rank, reaction, vigil_call, label_coverage, context, classification, decided_by, reports, prr, prr_ci_low, prr_ci_high, serious_share, needs_you_reasons, reporting_cluster, skeptic_outcome, strongest_objection, analyst_reasoning, next_check, zetaris_queries, openfda_reports. It is UTF-8 with a BOM so Excel opens it correctly.

## 9. Review queue

- **Tabs** (`TABS`; arrow keys move between them):
  - **Needs you:** the pipeline's manual-review rules (`manual_review.needed`, from `app/orchestration/manual_review.py`), plus accepted review-next items.
  - **Review next:** reviewed and `review_next`.
  - **Set aside by Vigil:** reviewed and lower priority or insufficient evidence.
  - **Not reached:** pending, not reviewed or failed.
  - **All.**

  Each tab shows its count. An empty tab is skipped when choosing the default.
- **Search:** a bordered box with a magnifier, 300 px wide (full width on phones). It filters by reaction name as you type.
- **Rows** (`queueRow()`, `whyLines()`):
  - rank;
  - reaction name (the row's button, `aria-expanded`), with its context when not a clinical event;
  - up to three short lines: **Needs you** (the reason), **For** (label coverage, PRR and CI, reports, % serious), **Against** (the strongest doubt: a computed flag first, else the Reviewer's objection in italics). Set-aside rows show **Set aside**, and rows the agents did not reach show **Status**;
  - Vigil's call and label coverage;
  - reports;
  - the PRR with a small CI plot against the threshold (`forest()`). The plot and the report count are hidden on mid-size screens.
- **One item open at a time.** Clicking a row opens its detail under it (`toggle()`).
- **Phones:** each row becomes a stacked block. Tables inside an open item (the Skeptic's) stay real tables, scrolling inside `.table-wrap`.

## 10. An open item

Built by `detail()`. What stays in view, then one tab at a time.

**Always shown:**

- a status line, for items the agents did not reach;
- the **Reviewer's strongest objection**, with a caption saying what the Reviewer then decided (`objectionBy()`);
- **Why it needs you**, the pipeline's reasons, for items in Needs you;
- the **key figures strip** (`.dstats`): PRR (with its 95% CI), reports (with expected), % serious, % fatal, label coverage (with its section). It is a 2-column grid on phones.

**Tabs** (`.dtabs`; only those with content appear). On screens from 1200 px they share the width equally, each at least as wide as its label; on phones they are one row that scrolls sideways. Each panel opens with a short note of its outcome where it has one, and its source marks and SQL links (`.dhead`).

| Tab | Content | Note |
|---|---|---|
| Assessment | The Analyst's reasoning and next check (model text, or "settled by code rules"). | – |
| Exchange | Each round: the Analyst's claim and the Reviewer's verdict (`threadHtml()`). | – |
| Reporters | Who reported it (country and reporter shares) and the reporting-cluster check. | – |
| Skeptic | Co-reported drugs: share, the co-drug's own PRR, this drug's PRR adjusted for it, possible interaction; the Skeptic's working, folded. | The outcome, e.g. "No challenge, as the PRR stays above 2…" (`skepticOutcome()`). |
| Label | The label quote and where it matched, or the label search summary. | Coverage, e.g. "Not found". |
| Figures | Three groups side by side as room allows: **Disproportionality** (reports, expected, PRR, 95% CI, chi-squared, and the CI plot against the threshold); **Information component** (IC and its lower bound, with a one-line explanation); **Seriousness** (serious and fatal, with shares). A thin-evidence warning follows in a tinted note. | – |
| Case reports | The first 10 matching FAERS reports, **fetched live from openFDA when the tab first opens** (`loadCases()`, `caseCard()`; openFDA allows browser requests). Each is a card: report ID, received date, country, reporter type; seriousness flags (Death in solid red); patient sex, age and weight; drugs, each once, suspects first with their role; the reactions, with this item's reaction first and highlighted. Past 12, a "+N more" link at the end of the list shows the rest in place, continuing the same lines, and becomes "Show fewer" (`.rx-more`, handled in `onQueueClick()`). Above the cards: "10 of N matching reports on openFDA". The page says they are not part of the run. A link to the raw JSON stays. Without a network it says it could not reach openFDA, keeps the link, and tries again next time. openFDA's codes (reporter, age unit, sex, drug role) are mapped in `QUALIFICATION`, `AGE_UNIT`, `SEX` and `ROLE`. | – |
| SQL | Every Zetaris query behind the item as a row that opens: an arrow that turns, the query ID and purpose (underlined on hover), and a "Show SQL" / "Hide SQL" link. The SQL opens indented under its row. On phones the ID is hidden. | "N Zetaris queries · open one to see its SQL". |

**SQL links** ("Its SQL", "Its N SQL queries") switch to the SQL tab, open those queries and flash them (`showQuery()`, `showTab()`).

## 11. Mascots

**The cast.** Vigil (the product) and one recoloured capsule per agent with a prop:

| Character | Colours (top / bottom) | Prop |
|---|---|---|
| Vigil | teal / orange | none |
| Data Clerk | navy / teal | stack of cards |
| Analyst | teal / navy | magnifying glass |
| Reviewer | orange / navy | tick |
| Skeptic | slate / orange | question mark |

Colours come only from the Vigil logo. The design rules are in `docs/video/mascot/HANDOFF.md`.

**Sprites.** `python -I docs/video/mascot/make_mascots.py` writes the video sprites (32×) and the page's copies (1×) to `app/static/mascots/`. The script needs Pillow, which on Ricky's laptop is in Inkscape's Python. The page names them `<who>-<face>.png`:

- **who:** `vigil`, `clerk`, `analyst`, `reviewer`, `skeptic`;
- **faces:** `neutral`, `blink`, `happy`, `alert`, `look`, `squint`, `concerned`, `bob`.

**Display rule.** Always scale by whole numbers (20 × 18, 40 × 36, 60 × 54, 100 × 90 …) with `image-rendering: pixelated` (class `.mascot`). Otherwise the pixels blur or go uneven. The canvas has clear edges (4 px at each side and 3 on top for Vigil; the agents' props reach the top and right), which are trimmed with negative margins where alignment matters.

**In the script:**

- `MASCOT` maps agent keys to sprites. The World Model and the orchestrator are Vigil.
- `REST` is each one's resting face. `WORK` is the frames it cycles while working.
- `sprite(agent, face)` returns a still image, `working(agent)` an animated one, and `idle(agent, shift)` one that idles.

**Where they appear:**

- the logo;
- the header chip;
- the crew stage, the steps list and the log of a running run;
- "How the agents got here";
- the landing sign-off;
- Vigil looking concerned on a stopped run.

**Tone.** Vigil is a drug-safety tool, so cheerful faces are used sparingly.

## 12. Time, dates and time zones

- Run times come from the run ID (UTC) and are shown in the **viewer's** zone, labelled ("Tuesday, 27 October 2026 at 03:16 PM GMT+11"; the list header says "times in GMT+11"): `when()`, `TZ`.
- Progress-log times are parsed from the trace's UTC timestamps and shown as local `HH:MM:SS` (`clockTime()`).
- A replay's recording time: `fmtTs()`, local.
- Label effective dates and "FAERS data to" are plain dates, shown **without** conversion (`fmtDate()`, `timeZone: "UTC"`), so nobody sees them a day early or late.
- Elapsed timers compare the server's start time with the viewer's clock. A wrong computer clock shifts them; time zones don't.

## 13. Responsive layout

The main breakpoints (search the CSS for `@media`):

| Width | What changes |
|---|---|
| ≤ 359 px | The crew's active mascot shrinks to 40 × 36. |
| ≤ 560 / 640 px | Phone: landing line-up at its smallest scale, crew labels except "Working" hidden, open-question boxes 2×2, stacked step rows. |
| ≤ 720 px | Top bar: no subtitle and no model name; the chip hides "<Agent> working" (but not "Finished" or "Stopped"). |
| ≤ 760 px | Queue rows as stacked blocks, figures strip 2×2, item tabs scroll sideways, open item full width. |
| ≤ 900 px | The crew stage shrinks (40 × 36 mascots, 80 × 72 active). |
| ≤ 1100 px | No sidebar column: the Investigations panel floats. |
| ≥ 1200 px | An open item's tabs share the width equally. |
| ≥ 1500 / 1700 / 2200 px | Wider containers; at 2200 px the main column zooms 1.125×. |

**Wide screens fill the width.** The summary, an open item's panels, the objection and the reasons run full width (no 760 px caps). The Figures groups and the key-figures strip spread across. No view should scroll sideways at 375 px; check with `document.documentElement.scrollWidth`.

## 14. Design system

Tokens are on `:root`. The page is light only, whatever the system setting.

- **Colours:**
  - `--paper` #f8f7f4 (page), `--sheet` #fdfcfa (panels);
  - `--ink` #1b2028, `--ink-2` #454c56, `--muted` #636974 (at least 4.65:1 on every ground);
  - `--rule` / `--rule-strong` (lines);
  - `--accent` #14366b (navy: links, live, selected);
  - `--signal` #b4441b (orange-red: review next, needs you, stopped, not found);
  - `--ok` #2f6b3f (green: finished, keys set, label covered);
  - `--unres` (purple: unresolved), `--pend` (amber: pending and replay);
  - tints `--accent-tint`, `--signal-tint`, `--ok-tint`, `--replay-tint`.
- **Type:**
  - `--serif` Newsreader for headings, big figures and the wordmark;
  - `--serif-text` for reading text;
  - `--sans` Public Sans for the interface;
  - `--mono` IBM Plex Mono for IDs, times, SQL and the clock.
- **Style:** report-like. Rules instead of cards, 2 px radii, small uppercase labels for figure captions, tabular numbers for figures.
- **Source marks:** `COMPUTED` (■ Computed: from openFDA data in Zetaris, re-checked in code) and `MODEL(agent)` (◇ Written by the <agent>, a model) label every block's source.

## 15. Honesty rules the UI follows

These come from `CLAUDE.md`. Don't break them.

- No made-up numbers or results. Everything shown comes from the API, apart from the Case reports tab, which shows openFDA's own reports, fetched live and labelled as not part of the run. The landing example is a real replay, captioned as an example.
- Computed figures are marked apart from model-written text, and model text is labelled with the agent that wrote it.
- Replays are always labelled ("Recorded replay" and "Replay investigation" in the form, "[replay]", "Recorded replay", "Replaying a recorded run", "replay" in lists and the chip). A paced replay changes only the pace, never the lines.
- Service squares claim only what is known (a key is set), not that a service works.
- "Stopped" only on a real error. An agent is never shown as "done" while it could work again.
- FAERS shows association, not causation. The caveat stays on the results and the landing page.

## 16. Accessibility

- Rows: the reaction name is a `button` with `aria-expanded` and `aria-controls`. So is each row of "How the agents got here".
- Tabs: `role="tablist"` / `tab` / `tabpanel`; arrow keys move between the queue tabs.
- The Investigations panel is a dialog while floating. Escape closes it, and focus returns to its button.
- The log is `aria-live="polite"`; decorative mascots and the crew bubble are `aria-hidden` or have empty `alt`.
- Focus rings use `--accent`. Touch targets are at least 40 px on coarse pointers.
- Reduced motion: no mascot animation, no panel blind, no landing rise, no live blinking.

## 17. Checking a change

1. Tests: `.venv\Scripts\python.exe -I -m pytest -q tests` (316 pass as of 27 Oct). Plain `python` on Ricky's laptop is Inkscape's Python, which has no pytest.
2. Start sample mode (the `vigil-sample` preview, port 8000) and look at the change at about 1440 px, 1800 px and 375 px wide.
3. To inspect the running view, replace `window.api` in the console to answer `{status: "running"}` for `/runs/<id>`. That holds the view on screen. Restore it afterwards.
4. Check for sideways scrolling at 375 px, and that every new value goes through `esc()`.
5. Update this guide and its change log.

## 18. Known gaps and ideas

- The live chip (agent at work, clock, finished or stopped) has not been seen on a live run in the browser: the preview server runs in sample mode, which shows only the replay chip.
- The finished chip is per browser (`localStorage`), not per server.
- From the 26 Oct critiques, still open: a glossary for PRR, IC and reporting cluster, and the third critique. The analyst decision feature was built on 26 Oct and **removed on 27 Oct** at the user's request (page and API).
- The investigation page has not yet been checked on a live (non-replay) run end to end.

## 19. Change log

Newest first. One line per change, with the date (Sydney).

- **27 Oct:** a Stop button beside the clock on a live run (asks inline, then "Stopping…"), with a stopped view; the server's `POST /runs/<id>/stop`.
- **27 Oct:** each agent in "How the agents got here" opens its history: its exchanges with the other agents (dossier) and its lines from the run's trace. Reviewer rows now say "N reviewed: M accepted". The safety net, World Model and Limits sections show they open (arrow, hover, "Show details").
- **27 Oct:** the orange "Replay mode" label removed from the header.
- **27 Oct:** replays get a header chip again, a plain one: the drug and "Investigation replay" (then "· finished" or "· stopped"), with no agent or clock.
- **27 Oct:** a case report's extra reactions open in place, on the same lines, instead of in a new list below.
- **27 Oct:** Case reports shown as readable cards fetched from openFDA. "Since last run" tab removed (the run's "Since the last run" section stays). Logo dances. Run warnings folded into one clickable bar.
- **27 Oct:** SQL rows show they open (arrow, "Show SQL" link, underline on hover). No header chip for replays. Item tabs keep their labels on one line.
- **27 Oct:** this guide written. Item tabs share the width equally from 1200 px. The Figures tab regrouped into Disproportionality, Information component and Seriousness, with the CI plot and a thin-evidence note.
- **27 Oct:**
  - **Replays:** paced on the run page, with a line count and "Skip to the result".
  - **Header chip:** kept across reloads, cleared when its run is opened.
  - **Landing:** hint "E.g. montelukast".
  - **Results:** search box restyled; open questions as figure boxes that open their tab.
  - **Open item:** fills wide screens; tabbed layout chosen over a report sheet, cards and an accordion.
  - **Run page and header:** timer as "0:04 elapsed"; log times local; dismiss button redesigned; the model and services group redesigned.
  - **Removed:** "Recent investigations" (landing), the side-by-side summary.
- **27 Oct:** mascots added (logo, crew stage, steps, log, rounds, landing line-up). Header chip for the run in progress. Crew stepper with "Standing by" instead of "Done". Steps restyled as a ruled list.
- **26 Oct:** the page built, critiqued twice and fixed (see `docs/UI_FIXES_HANDOFF.md`).
