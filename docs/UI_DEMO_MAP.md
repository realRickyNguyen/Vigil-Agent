# Vigil investigation page: demo map

For the person who records the demo video and writes its script. Written 27 Oct 2026 from the real page, branch `feature/investigation-page` (commit `e8ff11b`), clicked through in sample mode on http://localhost:8000/.

**How this was checked.**
- **Sample mode:** the server ran with `SAMPLE_MODE=true` (the `vigil-sample` entry in `.claude/launch.json`, which runs `python -I run.py` on port 8000). The three recordings (montelukast, isotretinoin, metformin) were replayed, and every view and tab below was opened.
- **Live runs:** the live behaviour comes from live runs made on this laptop today, opened in the same page. Their dossiers are in `logs/`, which is gitignored, so they exist only on this laptop. One live metformin run was started and stopped today to test the Stop button.
- **Not checked live:** anything marked "not checked live" was seen only on a replay.
- **Numbers:** every number and reaction name below is copied from the page or from those runs' dossiers, none invented. Times are Sydney (GMT+11) unless marked UTC.

Contents:
1. [What the UI is for](#1-what-the-ui-is-for)
2. [Guided tour](#2-guided-tour)
3. [Every screen and panel](#3-every-screen-and-panel)
4. [Demo checklist](#4-demo-checklist)
5. [Shot list](#5-shot-list-3-to-4-minutes)
6. [Glossary](#6-glossary)
7. [Things not to say](#7-things-the-presenter-must-not-say-or-imply)
8. [Problems found](#8-problems-found-while-writing-this)

---

## 1. What the UI is for

A drug-safety analyst types one drug name, and Vigil screens every reaction reported with that drug in the FDA's public adverse-event data (FAERS, through openFDA) for ones reported more often than expected. AI agents then argue over the strongest of those reactions: one classifies each against the drug's label, a second checks its numbers and wording and sends weak claims back, and a third tests whether other drugs on the same reports explain the pattern. The page hands the analyst a ranked queue of what deserves a closer look, with the evidence, the objections and the open questions behind every item, so the analyst can decide where to spend their time.

---

## 2. Guided tour

Two kinds of run:
- **Live:** Zetaris and Nightshift must be running, and the server started without sample mode. It takes 5 to 10 minutes: today's live runs took 367 s (montelukast) and 465 s (metformin).
- **Replay:** plays back a recorded live run with no service and no network. It takes about 4 s on the server, and the page plays its progress at a readable pace (about 15 to 25 s).

**Step 1. Open the page.** Go to http://localhost:8000/. You see the **landing page**:
- the headline "Drug reactions worth a closer look", with a small pixel magnifier;
- one paragraph on what Vigil does;
- the drug field with a button;
- on the right, one real item from the newest run on this machine. Today that is ACUTE KIDNEY INJURY from the live metformin run of 05:11 PM: "Review next", PRR 6.75 (6.66 to 6.85), 21,248 reports, 100% serious;
- further down, two more fragments of the same item ("Numbers from SQL, not from a model", "The agents argue before you see it") and the agent line-up.

*Means:* the landing page shows what a finished item looks like before you run anything.

**Step 2a. Start a replay.** The page offers replays when the server runs in sample mode.
1. Click **Montelukast** under "Recorded replays". It only fills the field.
2. Click **Replay investigation**.

*Means:* you are watching a recording of a live run from 26 Oct, not a new analysis.

**Step 2b. Start a live run.** The server must be live, with Zetaris and Nightshift up.
1. Type a generic name (for example `montelukast`).
2. Click **Start investigation**.

On a live server you can also replay: open **Investigations** (top bar) > **Recorded replay** > pick a drug > **Replay investigation**. On a sample-mode server, **Live** is greyed out with the line "Live runs are off: this server was started with SAMPLE_MODE=true."

**Step 3. Follow the run.** The **run page** opens:
- **Masthead:** the drug name.
  - On a live run: "In progress" and a clock, "0:42 elapsed", with a **Stop** button beside it.
  - On a replay: "Replaying a recorded run" and a counter, "22 of 187 lines replayed", with **Skip to the result**.
- **Crew:** five pixel figures (Data Clerk, Analyst, Reviewer, Skeptic, World Model). The one at work is larger and moving and says WORKING; the others say WAITING or STANDING BY.
- **Speech bubble:** the latest line of the agent at work, for example "Data Clerk [replay] queried Zetaris: reports by country for montelukast (110 rows, 0.0 s)".
- **Steps:** a numbered list of the same five agents, with one line on what each does.
- **Log:** every progress line, with its local time.

*Means:* you can see which agent is doing what, and that the numbers come from Zetaris queries and the text from model calls.

**Step 4. Skip a replay to the result.** Click **Skip to the result** beside the counter. The remaining lines show at once and the results page opens. On a live run the results open by themselves when the run ends.

**Step 4b. Stop a live run (optional).** Click **Stop** beside the clock. It asks "Stop this run? No results are kept." with **Stop** and **Keep running**. Confirm with **Stop**: the button shows "Stopping…" until the calls already under way come back. The page then reads "Stopped before it finished", with how far each agent got. Checked live today: a metformin run stopped after 19 s.

**Step 5. Read the results.** The **results page** for the montelukast replay shows, top to bottom:
1. **Masthead:** the title "Montelukast", then:
   - three buttons: **Export queue (CSV)**, **Download dossier**, **Copy run ID**;
   - a line of facts: "Label effective Aug 4, 2026", "FAERS data to Jul 30, 2026", "176,704 reports name the drug, of 20,682,701", "Replayed in 3.9 s".
2. **Recorded replay notice:** "The Zetaris results and model replies below are the ones live run 20261026T014102Z-8640f9 received on Oct 26, 2026, 12:47 PM, played back without calling any service."
3. **Figures strip:**
   - 787 reactions screened;
   - 257 pass the PRR screen;
   - 23 assessed (6 settled by code rules);
   - 23 accepted by the Reviewer;
   - 2 to review next (2 with a reporting cluster to check).
4. **Small counts:** "7 items need you", "0 unresolved", "3 not reached", "1 challenged by the Skeptic".
5. **Review queue:** five tabs, a search box and the ranked rows (step 6).
6. **Since the last run:** World Model comparison.
7. **The Analyst's summary:** model text.
8. **How the agents got here:** one row per agent and round; each opens its history.
9. **Folded sections:** Safety net, World Model, Limits and model calls.
10. **Caveat:** "FAERS reports show an association between a drug and a reported event, not that the drug caused it…"

**Step 6. Work the queue.** The tabs are **Needs you 7**, **Review next 2**, **Set aside by Vigil 21**, **Not reached 3** and **All 26**. Needs you opens first.

Each row shows:
- the rank and the reaction;
- a "Needs you" line;
- a **For** line (label status, PRR with its interval, reports, % serious);
- an **Against** line (the strongest reason to doubt it);
- Vigil's call;
- the reports;
- a small interval plot.

Click a reaction name to open it, for example **Results > Review queue > Needs you tab > open SPUTUM DISCOLOURED**. The open item shows:
- **The Reviewer's strongest objection.**
- **Why it needs you.**
- **Key figures:** PRR 25.7 (95% CI 24.38 to 27.08), 1,691 reports (79.69 expected), 96% serious, 2% fatal, Label: Not found.
- **Eight tabs:** Assessment, Exchange, Reporters, Skeptic, Label, Figures, Case reports, SQL.

Click the name again to close it. Several items can be open at once, for example PNEUMONIA and BRONCHITIS side by side down the queue.

**Step 7. See how the agents got there.** Scroll to **How the agents got here** and click any row (for example **Reviewer, round 1**, with its "History" link). It opens two parts:
- **With the other agents:** objections, revisions and challenges, from the dossier;
- **In the run's trace:** that agent's own log lines, with a checkbox "Only hand-offs and results".

**Step 8. Open a past investigation.** Click **Investigations** in the top bar. The panel lists "Past investigations · times in GMT+11", newest first: drug, review-next count, time, duration and "replay" for replays. Type in **Filter by drug** to narrow it. Click any row to open it, and **Close** (or Escape) to shut the panel.

**Step 9. Go home.** Click the **Vigil** logo (top left) to return to the landing page.

---

## 3. Every screen and panel

Data sources, used in the "From" lines below:
- **Zetaris:** a SQL query run in Zetaris on openFDA data the Data Clerk registered there.
- **Code:** Python in this repo, working on Zetaris results.
- **Model:** text written by Nemotron 3 Ultra through Meterless Nightshift, labelled with the agent's name.
- **Server:** the app's own state.
- **openFDA live:** fetched by the browser at view time; not part of the run.

### Top bar (every page)
- **Vigil logo and "Drug reaction review":** goes home. The logo dances (a short hop every few seconds).
- **Investigations button:** opens the Investigations panel.
- **Header chip:**
  - for a live run in progress: the agent at work and a clock;
  - once a run ends: "Finished" or "Stopped" until you open that run;
  - for a replay: just "Investigation replay".
  - From: server (`GET /health`, `GET /runs/<id>/events`).
- **Model and services group:** "Nemotron 3 Ultra | ■ Zetaris | ■ Nightshift".
  - The squares say only that a key or token is **set**, not that the service answers.
  - In sample mode Zetaris and Nightshift are faded, with "not used" in the tooltip.
  - From: server.

### Investigations panel
How to reach it: top bar > **Investigations**.
- **New investigation:**
  - a **Live** / **Recorded replay** switch;
  - the drug field, with a list of the recordings;
  - a button and a one-line hint.
- **Past investigations:** every finished run on this machine (one per dossier in `logs/`), with a filter box.
  - From: server (`GET /runs`).
  - Stopped runs are listed with a red "stopped" tag and how long they ran (from their traces). Failed runs are not listed, because they leave no dossier.

### Landing page
How to reach it: logo, or http://localhost:8000/ with no `#run-id`.
- **Hero:** headline, lead paragraph, drug field, button, recorded-replay quick picks.
- **Example item:** one real "review next" item from the newest run on this machine, with a link "Open it" to that run.
  - With no runs yet, it is a replay of the recorded montelukast run (`GET /example`), captioned as an example.
  - From: that run's dossier.
- **"Numbers from SQL, not from a model":** the item's disproportionality figures with a **Computed** mark. From: Zetaris and code.
- **"The agents argue before you see it":** the item's strongest objection and its round-by-round exchange. From: model (Reviewer).
- **Sign-off:** "Vigil" and the five mascots, the sponsor line and the FAERS caveat.

### Run in progress
How to reach it: start a run, or open a run that is still running.
- **Masthead:**
  - Live: drug, "In progress", run ID, clock, **Stop**.
  - Replay: "Replaying a recorded run", "N of M lines replayed" and **Skip to the result**.
- **Crew stage, speech bubble, steps list:** which agent is waiting, working or standing by. An agent is never shown as "done", because the Reviewer can start again after the Skeptic. From: server (trace lines).
- **Log:** every progress line from the trace.
  - Each line shows its local time, the agent's mascot and name.
  - In a replay each line starts with "[replay]".
  - From: the run's trace, `logs/trace-<id>.jsonl`.

### Stopped page
How to reach it: stop a live run, or open a stopped run's link while the server that ran it is still up.
- **Masthead:** drug, red "■ Stopped", "Ran for N s", run ID.
- **Summary:**
  - the frowning Vigil and "Stopped before it finished";
  - a line that nothing was kept;
  - "Stopped at", "Last step" and the trace file.
- **"How far the agents got":** each agent as "Working at the stop", "Had started" or "Not reached".
- **Actions:** **Run <drug> again**, **Back to the start**.
- From: server and trace.

### Error page
How to reach it: a run that fails, for example with Zetaris down.
- The error type, the HTTP status, whether a retry may work, and the trace file. Not shown in this demo map's runs.

### Results page

1. **Masthead.** From: dossier.
   - The drug.
   - **Export queue (CSV)**, **Download dossier** (the full JSON), **Copy run ID**.
   - When it was investigated, the label's effective date, the FAERS data date, the drug's report count, and "Run took 367 s of 600 s" (live) or "Replayed in 3.9 s" (replay).
2. **Notices.**
   - "Recorded replay" (replays only), with the live run it replays and when that was recorded.
   - Run warnings, folded into one amber bar ("⚠ N warnings · Details"). None of today's runs had warnings.
3. **Figures strip.** Reactions screened, passing the screen, assessed (and how many by code rules), accepted by the Reviewer, to review next. Below it, small counts: items that need you, unresolved, not reached, challenged by the Skeptic. The "needs you" and "not reached" counts jump to their tab when clicked. From: code.
4. **Review queue.**
   - **Legend:** a **Computed** mark ("from openFDA data in Zetaris; model claims about it are re-checked in code") and a **Written by a model** mark ("Nemotron Ultra, through Meterless Nightshift; the Analyst's text is checked by the Reviewer").
   - **Tabs:** Needs you, Review next, Set aside by Vigil, Not reached, All. Arrow keys move between them.
   - **Search reactions** box.
   - **Rows**, as in step 6. From: dossier (Zetaris figures, model calls, code rules).
5. **An open item.** Click the reaction name.
   - **Header:**
     - a status line, when it has one (for example "Review rounds ran out before the Reviewer's objection was settled"): code;
     - the Reviewer's strongest objection: model (Reviewer);
     - why it needs you: code (the pipeline's manual-review rules);
     - key figures: Zetaris and code.
   - **Assessment:** the Analyst's reasoning and **Next check**, with the classification. Model (Analyst); for an item settled by a rule, code.
   - **Exchange:** each round: what the Analyst claimed, the Reviewer's verdict (Accept, Reject or Unresolved) and its reason and objection. Model (Reviewer), except reasons that start "failed code checks", which are code (see [section 8](#8-problems-found-while-writing-this)).
   - **Reporters:** country and reporter-type shares against the drug's usual shares, and a reporting-cluster note. Zetaris and code. Only for items the pipeline checked (review-next items and items sent back).
   - **Skeptic:** a table of co-reported drugs: share of reports, that drug's own PRR, the PRR adjusted for it, and possible interaction; plus "The Skeptic's working". Zetaris counts, arithmetic in code. Only for items the Skeptic checked.
   - **Label:** the coverage outcome; for a covered item, a quote "taken from the label text by code"; otherwise the code search's summary (sections searched). Zetaris (label text) and code.
   - **Figures:**
     - disproportionality: reports, expected, PRR, 95% CI, chi-squared, with a plot;
     - information component: IC and its lower bound;
     - seriousness: serious, fatal;
     - a "Thin evidence" note when it applies (none in today's runs).
     - Zetaris and code.
   - **Case reports:** the first 10 matching FAERS reports, fetched live from openFDA by the browser when the tab opens, marked "not part of the run". Each card shows the report number, date, country, reporter type, seriousness, patient sex, age and weight, the drugs with their role, and the reactions. openFDA live. It needs a network.
   - **SQL:** every Zetaris query behind the item, by ID and purpose. Click one to see its SQL. Zetaris.
6. **Since the last run.** Changed verdicts (field, earlier → now), new items, items settled before and not now, and whether the label version changed. Computed by the World Model engine in code.
7. **The Analyst's summary.** Model (Analyst), after the last review round.
8. **How the agents got here.** One row per agent and round, with counts. Click a row for its history: exchanges from the dossier, and the agent's own trace lines. Dossier and trace.
9. **Safety net: N terms outside the screen.** Folded: click to show details. Designated medical events, serious terms outside the screen, and pregnancy and newborn terms, "for a person to review, and its terms are not signals". Zetaris (direct counts) and code.
10. **World Model: verdicts across runs.** Folded. Recorded, reopened, new, unchanged, changed, not settled now; the label version; "How earlier verdicts are used". Code (World Model engine).
11. **Limits and model calls.** Folded. Seven factors the run does not test; calls through Meterless Nightshift; the model; served by another model; with memory injected; without a receipt; the trace file. From: dossier.
12. **Colophon.** The FAERS caveat.

---

## 4. Demo checklist

Click paths start from the results page of the named run. In sample mode, open a recording with: top bar > **Investigations** > **Recorded replay** > type the drug > **Replay investigation** > **Skip to the result**. Or use the landing quick picks.

Live runs on this laptop that are worth opening, from top bar > **Investigations** > click the row with that time (no "replay" tag):

| Run | Drug | Started (Sydney) | Duration | Why open it |
|---|---|---|---|---|
| `20261027T040644Z-be2dd9` | montelukast | 03:06 PM | 367 s | Real "Since the last run" changes |
| `20261027T061125Z-ec1348` | metformin | 05:11 PM | 465 s | The landing example comes from it |
| `20261027T054534Z-7c9373` | isotretinoin | 04:45 PM | 369 s | Real trace timings |

You can also open one by URL, for example http://localhost:8000/#20261027T040644Z-be2dd9.

### a. The user and the problem
- **Where:** landing page, headline and lead paragraph. Results > Review queue > the **Needs you** tab.
- **Clicks:** open http://localhost:8000/.
- **Example:** the landing paragraph, then montelukast's 26 queue items, of which 7 need a person.
- **Say:** "A drug-safety analyst can't read every reaction reported for a drug, so Vigil sorts them into what needs a person's eyes first and says why."

### b. Input and output
- **Where:** landing page form (input); results page, Review queue (output).
- **Clicks:** Landing > Recorded replays: **Montelukast** > **Replay investigation** > **Skip to the result**.
- **Example:** montelukast in; 26 ranked items out, led by SPUTUM DISCOLOURED and FULL BLOOD COUNT ABNORMAL (both "Review next").
- **Say:** "One drug name in; a ranked review queue out, with the evidence and objections behind each item."

### c. Several data sources, registered in Zetaris at runtime
- **Where:**
  - run page log (lines such as "Data Clerk queried Zetaris: register FAERS reaction counts for montelukast", "register the newest labels for montelukast", "co-reported drugs for montelukast and PNEUMONIA");
  - an open item's **SQL** tab;
  - the masthead's "Label effective Aug 4, 2026 · FAERS data to Jul 30, 2026".
- **Clicks:** watch the log during a replay; then Results > Review queue > Needs you > open SPUTUM DISCOLOURED > **SQL** tab.
- **Example:** SPUTUM DISCOLOURED lists 12 Zetaris queries:
  - the disproportionality screen (`q-23159a7f`), report totals and label text;
  - the seriousness query;
  - reports by country and by reporter;
  - co-reported drugs, and report counts with albuterol, omalizumab and fluticasone.
- **Say:** "The Data Clerk registers the openFDA counts, the drug's label and the co-reported drugs in Zetaris for whatever drug you type, then queries them there."
- **Note:** in a replay the lines say "(already registered)" because the recording's live run found them registered; on a first live run of a new drug, registration runs fresh (not checked live for a new drug today).

### d. Zetaris doing real work
- **Where:**
  - an open item's **SQL** tab, with query IDs and the SQL itself;
  - the **Figures** tab;
  - the **Reviewer, round 1** history (How the agents got here), whose trace shows "Reviewer queried Zetaris: re-check 20 reactions for montelukast (20 rows…)".
- **Clicks:**
  1. Results > Review queue > Needs you > open SPUTUM DISCOLOURED > **SQL** tab > click `q-23159a7f` "Disproportionality screen for montelukast" (the SQL opens).
  2. Results > How the agents got here > **Reviewer, round 1** > In the run's trace.
- **Example:** the PRR 25.7 and chi-squared 32,853.4 for SPUTUM DISCOLOURED come from the screen query; the Reviewer's re-check is query `q-ab91045a` in the trace.
- **Say:** "The PRR is computed in SQL in Zetaris, every figure links to the query that made it, and the Reviewer re-runs the count and PRR in Zetaris before it accepts a model's claim."
- **Caution:**
  - The Reviewer's re-check query is **not** in the item's SQL tab; it is only in the trace (the run log and the Reviewer's history). Its SQL is in `logs/trace-<id>.jsonl` (`"agent": "reviewer", "event": "zetaris_query"`).
  - The expected count, the PRR's interval and the IC are computed in Python from the Zetaris counts, not in SQL.

### e. Meterless Nightshift and the model
- **Where:**
  - top bar ("Nemotron 3 Ultra");
  - Results > **Limits and model calls**: "Calls through Meterless Nightshift 46 · Model nvidia/nemotron-3-ultra-550b-a55b · Served by another model 0 · With memory injected 0 · Without a receipt 0";
  - log lines "Analyst model call served by nvidia/nemotron-3-ultra-550b-a55b via Nightshift in 25 s".
- **Clicks:** Results > scroll to the end > **Limits and model calls** > Show details. For the timings, open a live run: Investigations > isotretinoin 04:45 PM (369 s) > How the agents got here > **Analyst** > In the run's trace.
- **Example:** montelukast, 46 calls, all served by Nemotron 3 Ultra. In the live isotretinoin run, Analyst calls took 6 to 32 s each.
- **Say:** "Both reasoning agents run on NVIDIA Nemotron 3 Ultra through Meterless Nightshift, and every call's receipt says which model served it."
- **Note:** in a replay these lines read "in 0 s", because the replay doesn't call the model. Show timings from a live run.

### f. The Meterless World Model engine
- **Where:** Results > **Since the last run**; Results > **World Model: verdicts across runs**; How the agents got here > **World Model**.
- **Clicks:** top bar > Investigations > montelukast **03:06 PM** (367 s, live, `20261027T040644Z-be2dd9`) > Since the last run.
- **Example:** "Changed verdicts":
  - PNEUMONIA "label coverage not found → unclear";
  - SLEEP DISORDER DUE TO A GENERAL MEDICAL CONDITION "workflow status unresolved → reviewed; label coverage not found → covered; review priority review next → lower priority";
  - CHEST DISCOMFORT. 
  
  The section says "The label is the same version", and the dossier's reason is "the difference is this run's judgement on the same evidence".
- **Say:** "The World Model engine keeps every settled verdict with the label version it rests on, so the next run shows what changed and why; here the label was the same, so these changes are the agents' judgement differing on the same evidence."
- **Label-change reopening:** **not shown in the UI with real data.** No run so far has seen a label version change ("0 reopened" everywhere). It is covered by tests (`tests/test_world_model.py`, `test_pipeline_reopens_earlier_verdicts_when_the_label_changes`). Mention it in the README or the deck, not on screen.
- **In sample mode:** the World Model keeps a separate file, so a replay is compared only with earlier replays ("23 unchanged, 0 changed"). On a fresh judge machine the first replay has no earlier run.

### g. Agents that really interact
- **Where:** an open item's **Exchange** and **Skeptic** tabs; How the agents got here > **Analyst**, **Reviewer, round N**, **Skeptic** histories.
- **Best example:** montelukast **PNEUMONIA**. Its priority changed because of the exchange:
  1. In round 1 the Analyst claimed "not found on the label, clinical event, review next", and the Reviewer accepted.
  2. The Skeptic found that adjusting for albuterol (on 52% of the reports) takes the PRR from 3.52 to 1.94, below the screen's threshold of 2, and challenged it.
  3. The Reviewer re-reviewed with the challenge and **rejected** the claim.
  4. The Analyst revised its priority to **insufficient evidence**.
  5. The Reviewer **accepted** the revision.
- **Clicks:** Results > How the agents got here > **Skeptic** (shows the whole chain in one panel). Or Results > Review queue > Needs you > open PNEUMONIA > **Exchange** tab, then the **Skeptic** tab.
- **Second example (code checks):** isotretinoin **PREGNANCY**:
  1. Round 1: the Reviewer rejected "covered on the label" because pregnancy is named only as a contraindication.
  2. Round 2: the Analyst revised to "not found", and the Reviewer's code checks rejected that too: "failed code checks: not_named_in_label: label text names 'pregnancy'… in boxed_warning, warnings_and_cautions, information_for_patients, spl_medguide".
  3. The item stays **Unresolved**, with "Review rounds ran out before the Reviewer's objection was settled".
  
  Path: Results > Review queue > Needs you > open PREGNANCY > Exchange.
- **Third example (wording):** metformin **WEIGHT DECREASED**. Rejected in round 1 for overstating the evidence, accepted in round 2.
- **Say:** "The Analyst's claims don't reach you until the Reviewer accepts them; here the Skeptic's challenge went back through the Reviewer and changed pneumonia from 'review next' to 'insufficient evidence'."

### h. "Explain why"
- **Where:** an open item's header (**The Reviewer's strongest objection**), **Assessment** tab (**Next check**), **Label** tab (quote), and the **Computed** / **Written by … a model** marks.
- **Clicks:**
  - Results > Review queue > Needs you > open SPUTUM DISCOLOURED (objection and Next check).
  - Results > Review queue > All > open NIGHTMARE > **Label** tab (quote).
- **Examples:**
  - SPUTUM DISCOLOURED's objection: "88% of reports with a known country come from Canada (against 13% of the drug's overall reports)…". Its Next check: "Review individual FAERS reports for sputum discoloured to assess clinical context… also evaluate potential duplicate reports given the geographic concentration."
  - NIGHTMARE's label quote, from the boxed warning, matched on "sleep disturbances", with "The quote is taken from the label text by code."
- **Say:** "Every item carries its strongest objection and the next check to run, model text is labelled with the agent that wrote it, and label quotes are cut from the label by code, not written by the model."
- **Caution:** see [section 8](#8-problems-found-while-writing-this) on what the Computed mark does and doesn't promise.

### i. Honesty
- **Where:**
  - **Needs you** and **Not reached** tabs; the "unresolved" and "not reached" counts;
  - the "Recorded replay" notice and "[replay]" log lines;
  - the colophon caveat.
- **Clicks:**
  - Results > Review queue > **Not reached** tab (montelukast: BLOOD COUNT ABNORMAL, URTICARIA, SLEEP APNOEA SYNDROME, each "Named by the Reviewer in the last round, not reached").
  - isotretinoin or metformin: Results > Review queue > **Needs you** tab > PREGNANCY (isotretinoin) or PANCREATITIS (metformin), both **Unresolved**.
- **Failed items:** none of today's runs had a failed item, so "failed" is **not shown** with real data.
- **Say:** "Items the agents didn't reach or couldn't agree on stay in the queue and are marked, rather than dropped, and a replay is always labelled as one."

### j. Not hardcoded
- **Clearest pair:** **montelukast** and **metformin**.
  - Montelukast's review-next items are SPUTUM DISCOLOURED and FULL BLOOD COUNT ABNORMAL, both with Canadian reporting clusters. ASTHMA and WHEEZING are set aside as the treated condition.
  - Metformin's six review-next items include ACUTE KIDNEY INJURY (PRR 6.75) and METABOLIC ACIDOSIS. LACTIC ACIDOSIS (PRR 86.95) is set aside because the label's boxed warning covers it, and BLOOD GLUCOSE INCREASED is set aside as the treated condition.
- **Clicks:** run both replays; on each, Results > Review queue > **All** tab.
- **Say:** "A different drug gives a different, sensible queue: for an asthma drug the asthma terms are set aside as the disease itself, for a diabetes drug the glucose terms are."

### k. Evidence and limits
- **Uncertainty:** each row's interval plot; the open item's PRR "95% CI" and IC lower bound (Figures tab). Example: SPUTUM DISCOLOURED, PRR 25.7 (24.38 to 27.08), IC lower bound 4.32.
- **Thin evidence:** **not shown with real data.** No item in today's runs is flagged "Thin evidence", so the note never appears. Describe it in the deck if needed.
- **Reporting clusters:**
  - Montelukast, Results > Review queue > Needs you > open SPUTUM DISCOLOURED > **Reporters** tab: "88% of the 1,613 reports with a known country come from CA, against 13% of the drug's reports", then "Review next; check the reporting cluster first… The priority is unchanged." FULL BLOOD COUNT ABNORMAL: 97% from CA.
  - Isotretinoin IRRITABLE BOWEL SYNDROME: "93% came from lawyers (drug's usual 11%)", a likely litigation wave.
- **Safety net:** Results > **Safety net: 374 terms outside the screen** > Show details (montelukast). 374 terms (58 designated medical events, 195 missed serious terms, 121 pregnancy and newborn), 351 outside the screen; top unlabelled terms include ACUTE KIDNEY INJURY (1,814 of 1,818 reports serious).
- **Run warnings:** the amber "⚠ N warnings" bar under the masthead. **Not shown with today's runs** (none had warnings). The live runs `20261027T043153Z-b59273` (metformin) and `20261027T052457Z-3b77ad` carried warnings, per `docs/UI_SESSION_HANDOFF.md`, but those two weren't opened for this map.
- **Limits:** Results > **Limits and model calls**, the seven things the run does not test.
- **Say:** "Vigil shows how sure each number is, flags when reports cluster in one country or come from lawyers, and lists the serious terms it did not screen so a person can check them."

### l. Traceability
- **Where:** results masthead (**Copy run ID**, **Download dossier**, **Export queue (CSV)**), How the agents got here histories, and the run page log.
- **Clicks:**
  - Results > **Copy run ID** (toast "Run ID copied");
  - Results > **Download dossier** (`dossier-<id>.json`);
  - Results > **Export queue (CSV)**;
  - Results > How the agents got here > any row > In the run's trace.
- **Example:** run `20261027T063327Z-b17184`, trace `logs/trace-20261027T063327Z-b17184.jsonl`.
- **Say:** "Every run has an ID, a downloadable dossier, a CSV of the queue and a trace file of every query and model call; the page reads its history straight from that trace."

### m. Running without services
- **Where:** top bar (Zetaris and Nightshift faded); the landing hint "Replays a recorded live run in a few seconds, with no Zetaris, Nightshift or network"; the "Recorded replay" notice on results.
- **How a judge runs it:** `SAMPLE_MODE=true python -I run.py`, then open http://localhost:8000/, or `docker run --rm -p 8000:8000 -e SAMPLE_MODE=true vigil` (README, "Without Zetaris, Nightshift or a network").
- **Say:** "A judge with no Zetaris, no Nightshift and no network can replay the three recorded live runs, clearly labelled as replays."
- **Note:** the **Case reports** tab needs a network; without one it shows "Could not reach openFDA…". Everything else works offline.

### n. Product and UX touches (only if they help the story)
- **Agent histories:** How the agents got here > click a row. The best ten seconds, because it shows the interaction.
- **Keyboard:** Results > Review queue: click a tab, then the left and right arrow keys. Escape closes the Investigations panel.
- **Search:** "Search reactions" in the queue, for example type `pneu`.
- **Mascots:** the crew on the run page moves with the agent at work; worth a second during the replay, not a dedicated shot.
- **Phone layout:** works at 375 px wide (checked today). Probably not worth video time.

---

## 5. Shot list (3 to 4 minutes)

**Drug:** montelukast. It has every story in one run:
- a Skeptic challenge that changed an item (PNEUMONIA);
- reporting clusters (Canada);
- treated-condition calls (ASTHMA);
- label quotes (NIGHTMARE);
- not-reached items;
- a live run on this laptop with real World Model changes.

Metformin is the second drug for "not hardcoded".

**Live run or replay:** record the main flow on the **replay**. It takes seconds, gives the same result every time, and is clearly labelled. Then cut to the **live** montelukast run (`20261027T040644Z-be2dd9`, 367 s) for:
- real timings in the trace;
- "Run took 367 s of 600 s";
- the World Model's changed verdicts.

Show the start of a **live** run for a few seconds, so the viewer sees Zetaris and Nightshift working (the services' squares, real query durations). A full live run takes 6 to 8 minutes, uses NVIDIA trial credits and can give different verdicts from one run to the next, so don't record it whole. Starting a live run needs the server in live mode (`vigil-live` in `.claude/launch.json`) with Zetaris and Nightshift up. The landing page's form starts a live run there; Stop it after the shot.

| # | Screen | Action | Seconds | Covers |
|---|---|---|---|---|
| 1 | Landing | Hold on the headline and paragraph; point at the example item's For and Against | 15 | a, b |
| 2 | Landing (live server) | Type `montelukast`, click **Start investigation**; show the run page for a few seconds: Data Clerk working, log lines "queried Zetaris… (N rows, x s)"; then **Stop** | 15 | c, d, e |
| 3 | Investigations panel > Recorded replay | Replay montelukast; let the crew and log run a few seconds; **Skip to the result** | 15 | b, m, i |
| 4 | Results, top | Masthead, "Recorded replay" notice, figures strip (787 screened, 257 pass, 23 assessed, 2 review next) | 15 | b, i, l |
| 5 | Review queue, Needs you | Open SPUTUM DISCOLOURED: objection, figures, Next check; Reporters tab (88% from CA) | 25 | h, k |
| 6 | Same item | SQL tab, open the screen query; Figures tab | 15 | d |
| 7 | How the agents got here | Open **Skeptic**: the PNEUMONIA chain (challenge, Reviewer reject, Analyst revision, accept) | 25 | g |
| 8 | Review queue | Open PNEUMONIA > Skeptic tab (albuterol: PRR adjusted to 1.94) | 10 | g, c |
| 9 | Review queue, All | Open NIGHTMARE > Label tab (quote cut by code) | 10 | h |
| 10 | Not reached tab | Three items named by the Reviewer, not reached | 8 | i |
| 11 | Live run `be2dd9` | Investigations > montelukast 03:06 PM; Since the last run (three changed verdicts, same label) | 20 | f |
| 12 | Same live run | How the agents got here > Analyst > trace with real call times; Limits and model calls (calls, model, served by) | 15 | e, l |
| 13 | Metformin replay | Queue All tab: LACTIC ACIDOSIS set aside (on the label), ACUTE KIDNEY INJURY review next | 15 | j |
| 14 | Results, end | Safety net (374 terms, not signals); caveat line | 12 | k, i |
| 15 | Results masthead | Download dossier, Export CSV, Copy run ID | 8 | l |

Total about 3 min 40 s. To cut to 3 minutes, drop shots 9, 10 and 15.

---

## 6. Glossary

- **PRR (proportional reporting ratio):** how much more often a reaction appears in reports about this drug than in reports about all other drugs. PRR 3 means three times as often. It measures reporting, not risk.
- **95% CI (confidence interval):** the range the PRR would likely fall in if the reporting were repeated; a narrow range means many reports. Vigil draws it as a small bar.
- **Chi-squared:** a number for how unlikely the reporting imbalance is to be chance alone. The screen needs 4 or more.
- **The screen:** a reaction passes if it has 3 or more reports, PRR 2 or more and chi-squared 4 or more (the Evans criteria).
- **Expected count:** how many reports of this reaction the drug would have if it were reported like all other drugs.
- **IC (information component):** log2 of observed over expected reports. Its lower 95% bound above 0 means more reports than expected, allowing for chance.
- **Label coverage:** whether the drug's current label already describes the reaction as an effect:
  - **covered:** yes, with a quote;
  - **not found:** not named in any section searched;
  - **unclear:** only a related or broader term;
  - **not assessed:** for the treated condition or non-clinical terms.
- **Review next:** Vigil's highest call. A clinical event the label doesn't cover (or covers unclearly) with a strong reporting pattern, accepted by the Reviewer, worth a person's closer look.
- **Needs you:** items where a person must decide. Review-next items, plus items where:
  - label coverage is unclear;
  - the Reviewer rejected a claim;
  - the dispute is unresolved;
  - adjusting for a co-reported drug lowers the PRR by 30% or more;
  - the agents didn't reach the item.
- **Set aside by Vigil:** reviewed and given lower priority or insufficient evidence, with the reason (for example "Likely the treated condition or the disease itself").
- **Not reached:** the agents ran out of rounds or time before assessing it (pending, not reviewed or failed). Shown, not dropped.
- **Unresolved:** the Reviewer kept objecting and the review rounds ran out. A person has to settle it.
- **Reporting cluster:** most of the reports come from one country, or from lawyers, more than is usual for the drug. Re-filed copies or litigation can inflate the count without making the pattern false.
- **Safety net:** serious terms the screen skipped (designated medical events, pregnancy and newborn terms, mostly-serious terms outside the screen), listed for a person to check. They are not signals.
- **Co-reported drug:** another drug named on the same reports, for example albuterol on 52% of montelukast's pneumonia reports.
- **Adjusted PRR:** the drug's PRR recalculated to allow for one co-reported drug. If it drops below 2, the Skeptic challenges the finding.

---

## 7. Things the presenter must not say or imply

| Don't say | Why |
|---|---|
| "Montelukast causes sputum discolouration" (or any "causes") | FAERS shows association, not causation; the page's own caveat says so. Say "is reported more often than expected". |
| "Reviewed" or "accepted" items were checked by a safety professional | The Reviewer is a model plus code checks. No person reviewed them. |
| "Vigil found a new safety signal" | Review next means worth a closer look. Duplicates, litigation, confounding by indication and co-reported drugs aren't ruled out; the Limits list says what isn't tested. |
| "Saves analysts N hours" or any time saving | Not measured against a person. |
| "Vigil is accurate to N%" | The gold set was labelled by an AI and has not had a person's review (CLAUDE.md). |
| "Every number is re-checked against Zetaris" | The Reviewer re-checks each finding's report count, PRR and screen in Zetaris. The expected count, CI and IC are computed in Python from Zetaris counts and not re-checked; seriousness and reporter shares aren't re-checked either. |
| "The model computed the PRR" or "the model wrote the quote" | The PRR is SQL in Zetaris; quotes are cut from the label by code. |
| "The results are the same every time" | Live runs on the same evidence can differ: the montelukast run of 03:06 PM changed three verdicts against the one before it (same label). Replays are the same every time because they are recordings. |
| "The World Model reopened verdicts when the label changed" (as if seen in this demo) | No run so far has seen a label change; that path is shown only by tests. |
| Showing a replay as if it were live | Replays are labelled; keep the "Recorded replay" notice and "[replay]" lines in shot. |
| "No patient data is shown" | The Case reports tab shows individual (de-identified) FAERS reports with sex, age and weight, fetched from openFDA by the browser. |
| "Uses Cursor" | The team doesn't use Cursor (CLAUDE.md). |

---

## 8. Problems found while writing this

Nothing below was changed in this task.

1. **README says no case-level data reaches the app, but the Case reports tab shows case-level reports.**
   - **Where:** `README.md:304` "All data is public: openFDA adverse-event aggregates and drug labels. No case-level or personal data reaches the app or the model."; `README.md:294` "**Aggregate data only:** no case-level review…"; `README.md:185` "Vigil works on aggregate counts…".
   - **What is true:** the agents and the model use only aggregate counts and label text. The Case reports tab (`app/static/index.html`, `loadCases()` and `caseCard()`) fetches the first 10 matching FAERS reports **from the browser straight to openFDA**. The server and the model never see them. They are public and de-identified, but case-level: report number, date, country, reporter type, patient sex, age, weight, drugs and reactions.
   - **Fix:**
     - Line 304 needs changing, for example: "The agents and the model use only aggregate counts and label text. The page's Case reports tab shows up to 10 public, de-identified FAERS case reports per item, fetched by the viewer's browser from openFDA; they never reach the server or the model."
     - Line 294 should say the *analysis* is aggregate-only.
     - Line 185 is fine as written.

2. **The "Computed" mark promises more checking than happens for some blocks.**
   - **Wording:** the mark's tooltip reads "Computed from openFDA data in Zetaris SQL or by code. The Reviewer's code re-checks every count, PRR and label quote a model cites." The queue legend reads "Computed from openFDA data in Zetaris; model claims about it are re-checked in code".
   - **What the Reviewer's code does:** re-queries Zetaris for each finding's report count, PRR and chi-squared (`app/agents/reviewer.py`, `code_checks()`); checks the label wording (`term_in_label`, `not_named_in_label`); and checks that evidence IDs exist. It doesn't re-check the expected count, the PRR's 95% CI or the IC: these are computed in Python from the Zetaris 2×2 counts (`app/data/uncertainty.py`).
   - **Blocks that carry the mark, and whether the wording fits:**

     | Block | Accurate? | Why |
     |---|---|---|
     | Queue legend (`index.html` ~1512) | Mostly | "Model claims … are re-checked" is true for cited counts, PRRs and label wording. |
     | Figures tab (~1999) | Partly | Reports, PRR and chi-squared come from the screen query and are re-checked. Expected, 95% CI, IC and IC lower bound are Python on Zetaris counts and not re-checked. Seriousness comes from its own Zetaris query and is not re-checked. |
     | Landing "Disproportionality" fragment (~2172) | Partly | Same as the Figures tab. |
     | Label tab (~1982) | Yes | The quote and the search are code on the label text from Zetaris. |
     | Reporters tab (~1969) | No re-check | Zetaris queries plus code shares, context only; the "re-checks" sentence in the tooltip doesn't apply. |
     | Skeptic tab (~1975) | No re-check | Zetaris counts plus Python adjusted PRR and Omega; no re-check. |
     | Assessment tab, for items settled by a rule (~1958) | Yes | A code rule, no model. |
     | "Since the last run" lede (~1588) | Yes | "Computed by the World Model" is accurate. |

   - **Fix:** reword the tooltip to say what "Computed" means everywhere, and leave the re-check claim to the legend. For example: "Computed: from openFDA data queried in Zetaris, with arithmetic in code; not written by a model. A model's cited counts, PRRs and label wording are re-checked by the Reviewer's code." Optionally add "computed in code from the counts above" to the Figures tab beside Expected, 95% CI and IC.

3. **Code-check rejections are labelled as model text.** The Exchange tab and the agent histories mark the Reviewer's reasons "Written by the Reviewer, a model". But a reason that starts "failed code checks: …" comes from code (isotretinoin PREGNANCY, round 2). Fix: in `threadHtml()` and the history panel, show those reasons with a Computed mark, or the label "Reviewer's code check".

4. **The Reviewer's re-check query isn't in the item's SQL tab.** The claim "the Reviewer re-checks in Zetaris" can be shown only through the trace (the run log, the Reviewer's history panel, or `logs/trace-<id>.jsonl`). The query isn't in the dossier's `evidence_queries`. Fix: add the re-check query (for example `q-ab91045a`, "re-check 20 reactions for montelukast") to `evidence_queries` and to each re-checked item's SQL list.

5. **Replays show "0.0 s" and "in 0 s" timings.** Lines such as "Reviewer model call served by … via Nightshift in 0 s" and "Data Clerk queried Zetaris: … (110 rows, 0.0 s)" appear in replays (run log, agent histories). A viewer could read that as instant model calls. Fix: in replay lines show the recorded duration, or omit it. Meanwhile, show timings from a live run in the video.

6. **The Investigations list is crowded with test replays.** On this laptop it lists dozens of replays from today's testing ("Isotretinoin · 2 next · replay", over and over), which makes the live runs hard to find on video. Logs must not be hand-edited (CLAUDE.md). Options:
   - record from a machine with a fresh `logs/`;
   - use **Filter by drug**;
   - open the runs by URL;
   - add a "Live only" filter (code change).

7. **"New this run" in Since the last run includes items that weren't new.** In replays, BLOOD COUNT ABNORMAL, URTICARIA and SLEEP APNOEA SYNDROME are listed as "New this run", though they were in the earlier run as not reached; they're new only as *settled* verdicts. Fix: label it "Not settled in the earlier run" or similar, or count them apart.

8. **Sample mode's World Model compares replays with replays.** "Since the last run" in a replay reads "against 1 earlier run … 23 unchanged", where the earlier run is just a previous replay. That is true but shows nothing. Fix: say so in the section when both runs are replays, or compare a replay against the recording's own earlier live run.

9. **Some features are untested with real data.**
   - **Thin evidence:** no item in any run on this laptop has `thin_evidence`, so the warning never shows.
   - **Label-change reopening:** shown only by tests.
   - **Failed items:** none in today's runs.
   - **Run warnings:** the warnings bar wasn't opened for this map.
   
   Fix: none needed in code; don't present them as seen.

10. **The figures strip says "over 2 review rounds" when the Skeptic round also ran.** Montelukast: "23 Accepted by the Reviewer over 2 review rounds", though How the agents got here also shows the Skeptic's challenge round with its re-review. Minor. Fix: count the challenge review, or say "over 2 review rounds and a challenge review".

11. **Stopped runs after a server restart: fixed since this map was written.** Stopped runs are now read back from their traces, listed as "stopped" and open after a restart.

12. **There is no glossary on the page.** PRR, IC, chi-squared and "reporting cluster" appear unexplained, apart from a few tooltips and the IC note in the Figures tab. Open since the 26 Oct critiques. Fix: a short "What these terms mean" fold on the results page, using section 6 of this file.

13. **Not checked live today:**
    - a full live run followed in the browser from start to results;
    - the live header chip while an agent works (the Stopped chip was seen live);
    - registration of a drug never registered before.
    
    The live runs used here were opened after they finished.
