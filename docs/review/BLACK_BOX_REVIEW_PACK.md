# Black Box: review pack for an outside reviewer

This document is self-contained. It explains the hackathon, its rules and scoring, our idea, what we have built so far, what the first runs produced, and what we know is weak. We want a blunt second opinion on whether this can win and what to change.

Written on Thursday 22 October 2026, about 05:00 UTC, roughly 5.5 days before the submission deadline. Facts we have tested ourselves are stated as facts. Plans are labelled as plans. Things we have not verified are labelled as unverified.

---

## 1. The hackathon

**Event.** Open Agent Hackathon 2026, run online by GenAI Works on its HackOS platform. Teams of 1 to 5 people.

**Timeline.** The build window opened Thu 22 Oct 2026, 00:00 UTC. Submissions close Tue 27 Oct 2026, 23:45 UTC. Hard deadline.

**Tracks.** Each team enters exactly one track. The track decides the judging panel and prize pool. Organisers also publish more specific "challenge statements" per track on HackOS. We have not read those yet, and they take priority over the generic text below.

| Track | Brief | Data the organisers suggest | Cash prizes (1st / 2nd / 3rd) |
|---|---|---|---|
| 01 Solving Fragmented Intelligence | Discover and work across fragmented data sources | Three or four small sources that disagree | $1,600 / $1,200 / $900 |
| 02 The Agent That Can Explain Why | Investigate complex questions across sources, connect findings, give evidence-backed answers or recommendations | Documents for one bounded question; every conclusion traceable | $1,600 / $1,200 / $900 |
| 03 Reasoning Architecture | Turn data, knowledge, memory and reasoning into reliable decisions and actions | Records, rules or policies, and memory of past decisions | $1,500 / $1,200 / $900 |
| Wildcard | Extend an existing project; only new work is scored | Old and new work kept separate | $1,000 / $600 / $400 |

Separate awards: an NVIDIA DGX Spark for the best use of NVIDIA Nemotron models (run through Meterless Nightshift, see below), and Cursor API credits for the best Cursor-built product.

**We are entering Track 02.**

### 1.1 Judging (100 points, at least three judges per submission)

| Criterion | Points | What judges look for, in the organisers' words |
|---|---|---|
| Impact | 30 | Fit with the challenge statement; a meaningful problem for its users. "Name a real user, a real problem and the track it answers." |
| Technical | 20 | Implementation, reliability, architecture. "Distinct roles, real interdependence and traceable behaviour. Failures are handled." |
| Innovation | 15 | Originality. "A thoughtful agent pattern, not a familiar chain with new labels." |
| Demo | 15 | How clearly the demo shows the solution and its value. "A real run plus a collaboration moment in the logs." |
| Product & UX | 10 | Intuitive, accessible, easy to use. "The output is something the intended user could act on." |
| Sponsor Tech | 10 | How well the sponsors' technology addresses the problem. "Zetaris and Meterless shown doing real work." |

Ties are broken on Impact.

The organisers say judges **reward**: agents doing real work, clear applications, thoughtful architecture, several agent interactions, outputs refined through iteration, agents that challenge each other, branching, reliability, clear logs, usable outputs.

Judges **discount**: UI polish without depth, single-agent systems, hardcoded demo paths, broad concepts with weak implementation, unsupported claims, sponsor technology bolted on.

Judges will also try their own inputs ("a project that only works on the three you shipped is a project that doesn't work"), may not have our API keys, and have little time: anything they cannot start, call or read counts against us.

### 1.2 Hard rules (breaking these risks disqualification)

- **Zetaris and Meterless must be load-bearing.** The organisers' test: "if I removed Zetaris, would the agent still work? If yes, it isn't integrated yet." A sponsor named in the README but absent from the code scores worse than not mentioning it.
- **Meterless, two parts.** At least one "Meterless Engine" (see 1.3) must be implemented in a working feature with a passing test. And Meterless Nightshift must be the app's primary AI provider.
- **At least two agents that genuinely interact**, with visible critique, retry or branching.
- **No hardcoded outputs, no fabricated logs, no overclaiming** in the README or deck. Logs are written by code to `logs/trace-<id>.jsonl` and never edited.
- **Data must be public, small, or labelled synthetic.** No personal or confidential data. NVIDIA's endpoint logs requests.
- **Judges must be able to run it:** a `run.py` or `POST /run` entry point, a `Dockerfile`, at least 3 sample inputs, and a `SAMPLE_MODE` that runs the real agent logic on cached data without keys.
- **Deliverables:** a demo video of 1 to 4 minutes, a slide deck, a public GitHub repo with a README, and a written explanation of how each sponsor technology is used.
- **Cursor** is named as the required development environment. (See 6.4 for our situation.)

### 1.3 The sponsor technology

- **Zetaris** is a data federation platform. It runs locally in Docker. It turns outside sources (REST APIs, files, databases) into SQL tables that can be joined and cached, and it has a semantic layer with data-quality rules. Our app sends SQL to it through its REST API.
- **Meterless Nightshift** is a local gateway with an OpenAI-compatible API. It routes model calls to cloud or local models. Here it routes to NVIDIA Nemotron models on trial credits, which have a per-minute cap. Nightshift adds its own features on top: racing several models in parallel, memory that reinjects earlier answers, answer fusion, judging, and a "reasoning scaffold".
- **Meterless Engines** are open-source reference designs for agent infrastructure: H-MEM (tiered memory across sessions), World Model (shared, provenance-stamped, bitemporal world state), Markovian (long tasks in bounded chunks) and Scout Intent (request classification, risk flags, prompt-injection guard). They are designs to implement, not a library to install.
- **NVIDIA Nemotron** models: we use `nemotron-3-ultra-550b-a55b` through Nightshift.
- **Cursor** is an AI code editor.

---

## 2. Our idea: Black Box

**One line.** An agent team that investigates whether a drug has a side effect its label does not warn about yet, argues against its own findings, and shows the evidence behind every conclusion.

The name refers to the FDA's "boxed warning", its strongest label warning. It also nods to the track's theme of explaining why.

### 2.1 User and problem

**Intended user.** A drug-safety (pharmacovigilance) analyst at a hospital pharmacy or a small biotech, or a health journalist.

**The problem.** The FDA Adverse Event Reporting System (FAERS) is public and holds about 20.7 million reports from doctors, pharmacists, consumers and lawyers. It contains early warnings about side effects before labels mention them. But reading it well needs statistics and an understanding of its biases:

- **Confounding by indication:** the disease itself causes the symptom.
- **Notoriety bias:** reports spike after media coverage.
- **Lawyer-driven reporting.**
- **Duplicate reports.**

Most potential users do not have the time or the skills for this.

**Each run answers one bounded question:** does drug X have reported reactions that its current label does not cover, and does each one survive scrutiny?

### 2.2 Data

All data is public and comes from openFDA (api.fda.gov), registered in Zetaris as REST tables. We use **aggregate count endpoints only**, so no individual case report ever reaches the app or the model.

| Zetaris table | What it holds | Status |
|---|---|---|
| Baseline reaction totals | Reports per reaction across all drugs (top 999; the no-key limit is 999 rows) | Built |
| Total reports | All reports, split by the serious flag | Built |
| Per-drug reaction counts | Reactions reported with the drug | Built, created at runtime for any drug name |
| Per-drug total | Reports mentioning the drug | Built, created at runtime |
| Current label | Label sections: boxed warning, warnings, adverse reactions, indications and so on | Built, created at runtime |
| Indications, reporter type, report timeline, co-reported drugs, recalls | Evidence for the Skeptic agent | Planned |

**Method.** Standard disproportionality analysis in SQL inside Zetaris:
- **PRR** (proportional reporting ratio): how much more often a reaction is reported with this drug than with all other drugs.
- **Chi-squared:** how strong the evidence is.
- **Screen:** the Evans criteria (PRR ≥ 2, chi² ≥ 4, at least 3 reports).

We checked the Zetaris results against an independent Python calculation, and they match to two decimal places.

### 2.3 Agent system (built)

```
input {"drug": "montelukast"}
  │
  ▼
Clerk (code, no LLM)
  registers openFDA tables in Zetaris for this drug, runs the PRR/chi² screen in SQL, fetches the label
  │
  ▼
Hunter, step 1: pick (Nemotron via Nightshift)
  chooses up to 10 reactions worth reviewing from the 30 strongest screen rows
  │
  ▼
Hunter, step 2: classify
  rules settle easy cases in code:
    • administrative MedDRA terms → not meaningful
    • reaction named in the label's indications section → the treated disease
    • reaction named literally elsewhere in the label → on label
  the model classifies the rest, seeing only the label sentences relevant to each reaction
  categories: on_label | possible_new_signal | likely_indication_or_disease | not_meaningful
  │
  ▼
Judge (code checks first, then Nemotron)
  code checks the model cannot overrule:
    • re-queries Zetaris and confirms the numbers
    • confirms the cited query IDs exist
    • confirms the claimed label term appears in the label, and extracts that sentence itself
    • a "new signal" must pass the screen and must not be named in the label
  then the model reviews the reasoning, and names important reactions nobody has looked at
  │
  ├── rejections and missing reactions go back to the Hunter (at most 2 revision rounds)
  │   accepted findings are kept and not re-done
  ▼
Dossier (JSON) + trace (JSONL)
  each finding: verdict, numbers, SQL, label sentence, reasoning, who decided (rule or model)
  plus the factors not yet tested, and a fixed caveat: association, not causation; not medical advice
```

**Reliability features:**
- Model calls run two at a time, in small batches.
- A failed batch is retried one item per call.
- A reaction that still fails is reported as "not classified", not guessed.
- A finding whose review failed is reported as "not reviewed by Judge", not accepted.
- If the pick call fails, the Hunter falls back to the top reactions by chi-squared.

There are 22 offline unit tests.

### 2.4 Planned, not built

1. **Skeptic agent.** A third agent that attacks each "possible new signal" with its own Zetaris queries:
   - the share of reports filed by lawyers or consumers
   - a reporting spike after one date
   - co-reported drugs
   - the most common indications, to stratify the counts
   - recalls in the same period
2. **World Model engine** (the Meterless engine we plan to implement, with a passing test). Every fact and agent claim is stored with provenance (query ID, source URL, retrieval time, which agent and run). Facts are bitemporal, so the investigation can be replayed "as of" a past date.
3. **Backtest demo.** Run the investigation as of a date before a known label change, and see whether the agents would have raised the signal early. Candidate: montelukast, which got an FDA boxed warning for neuropsychiatric events in March 2020 (date to verify). We would report the result either way.
4. **Possibly H-MEM:** reuse Judge-accepted classifications across runs (with provenance), to cut model calls.
5. **Possibly Scout Intent:** guard against personal medical questions ("should I stop my medication?") and prompt injection.
6. **Judge-facing pieces:** `SAMPLE_MODE` on cached data, Dockerfile, README, a simple UI, the deck and the video.

---

## 3. What the first runs produced

All runs use montelukast, an asthma and allergy drug. 174,922 FAERS reports mention it; 787 of its reactions were screened and 256 pass.

### 3.1 Run history (same day, same input)

| Run | Setup | Duration | Model calls succeeded / failed attempts | Notes |
|---|---|---|---|---|
| A | Lightning model, first version | 58 min | 26 / 47 | 4 reactions left unclassified; the Judge accepted everything; the revision loop repeated the same work |
| B | After the speed fixes (rules, per-reaction label excerpts, parallel calls, smarter loop) | 14 min | 8 / 13 | Two Judge batches failed, and a bug counted those findings as accepted (since fixed) |
| C | Nightshift reconfigured: one model (Ultra), no racing | 9 min | 12 / 5 | Judge rejected 2 findings in round 1 and 1 in round 2; nothing unclassified or unreviewed |

The main cause of the failures was Nightshift racing two models: an empty reply from one model failed the whole request.

### 3.2 Run C findings (the current best)

| Reaction | PRR | Final classification | Decided by |
|---|---|---|---|
| Asthma | 24.0 | Treated disease | Rule |
| Wheezing | 21.7 | Treated disease | Model |
| Obstructive airways disorder | 39.2 | Treated disease | Model |
| Dyspnoea | 4.2 | Treated disease | Model |
| Cough | 5.1 | On label | Rule |
| Productive cough | 9.9 | On label | Model |
| Sinusitis | 5.9 | On label | Rule |
| Aggression | 5.9 | On label (boxed warning) | Rule |
| Nightmare | 7.1 | On label ("sleep disturbances" in the boxed warning) | Model |
| Sputum discoloured | 25.9 | Possible new signal | Model |
| Full blood count abnormal | 23.8 | Possible new signal | Model, after a debate |
| Sleep disorder due to a general medical condition | 23.1 | Possible new signal | Model, after the Judge rejected "on label" |
| Loss of personal independence in daily activities | 9.6 | Possible new signal | Model |

**An example of the agents disagreeing** (from the trace):
1. The Hunter called "full blood count abnormal" a new signal.
2. The Judge rejected that, because the label mentions thrombocytopenia.
3. The Hunter switched to "on label".
4. The Judge rejected that too: thrombocytopenia doesn't cover the broader term.
5. The Hunter went back to "new signal", and the Judge accepted.

**What we think of these results:**
- The treated-disease and on-label calls look right.
- The four "possible new signals" are the weak part. They are vague terms or probably disease-related, and a real safety analyst would not act on them as they stand.
- Several real neuropsychiatric signals with strong numbers were not reviewed this run (anxiety, depression, middle insomnia). The Judge named some as missing in the last round, after the round limit was reached.

---

## 4. How we score ourselves today (please challenge this)

| Criterion | Our guess | Why |
|---|---|---|
| Impact (30) | 20 to 24 | Real problem and plausible users, but the current output's "new signals" are weak, and a judge may ask who would actually use it |
| Technical (20) | 13 to 16 | Real multi-agent loop, code checks, traces and fallbacks; slow (9 min per run); no engine yet; no Docker or sample mode yet |
| Innovation (15) | 9 to 12 | Adversarial pharmacovigilance with code-verified claims is uncommon; the backtest could lift this if it works |
| Demo (15) | 7 to 11 | Strong debate moments exist in the trace; no UI yet; a 9-minute run must be cut down for video |
| Product & UX (10) | 4 to 6 | JSON output only today |
| Sponsor Tech (10) | 5 to 7 | Zetaris does the joins and statistics, Nightshift serves every call; engine not built yet; see the concerns in 6.3 |

---

## 5. Constraints

- **Time:** about 5.5 days left, including the deck, video and README.
- **Machine:** one Windows laptop with 16 GB RAM and little free disk.
- **Zetaris and Nightshift both run locally,** so a judge cannot reach our instance. `SAMPLE_MODE` with cached data is how judges will run it. (How judges are expected to use a local Zetaris is an open question to the organisers.)
- **NVIDIA access** is on trial credits with a per-minute cap. Nightshift calls take 20 to 70 seconds each and sometimes fail.
- **Zetaris REST tables have a fixed URL each.** We create new tables for each drug at runtime. They cannot be deleted through SQL, so they accumulate.
- **openFDA without a key** allows about 1,000 requests per day (documented, not tested by us). We cache.

---

## 6. Known weaknesses and open questions

### 6.1 Product and story
- Who exactly is the user, and what do they do with the dossier? Today the dossier is a list. It is not a ranked "what to look at next".
- The signals that most need judgement ("possible new signals") are where quality is weakest.
- The backtest story depends on label-history dates that openFDA does not provide (it serves only the current label). We would need DailyMed label history, or a dated, cited fact.
- There is no UI yet.

### 6.2 Agent design
- Only two agents so far (plus deterministic code). The Skeptic is planned.
- The Hunter picks 10 of 256 passing reactions. Picks have favoured high-count respiratory terms over neuropsychiatric ones.
- The round limit stops the loop before the Judge's final "missing" list is handled.
- A run takes 9 minutes. Most of that is Nightshift latency.

### 6.3 Data and sponsor fit
- All data comes from one provider (openFDA), through several endpoints. A judge could ask why Zetaris is needed rather than calling the API directly. Our answer today: Zetaris does the cross-table joins, the statistics, caching, and runtime registration of new sources. We are unsure whether that will look load-bearing enough.
- Possible second sources: DailyMed (label history), ClinicalTrials.gov (side effects in trials), PubMed (literature). These would make the federation more meaningful, but each costs time and adds risk.
- The drug search matches the generic name anywhere in a report, including drugs that were not the suspect, so counts are inflated.
- The baseline holds only the top 999 reactions, so rarer reactions are not screened.
- FAERS limits: voluntary reports, duplicates, no denominator. We state these in the output.

### 6.4 Process
- Development so far has been done with Claude Code, because the organisers had not delivered the Cursor credits. We plan to move to Cursor when they arrive, and to state this history honestly in the README.

---

## 7. What we would like from the reviewer

Please be direct. We would rather hear "this will not win, because…" now than in a week.

1. **Winning potential.** Score us on each of the six criteria with a short reason. Say whether this idea can win Track 02, and what the main thing holding it back is.
2. **Track fit.** Is Track 02 the right choice, or would Track 01 or 03 suit it better?
3. **Story and user.** Is the problem compelling to a non-specialist judge? Is the user believable? What should the demo's emotional or "aha" moment be?
4. **Product design.** What should the user see and do? What would make the output something they could act on?
5. **Agent system.** Are the roles distinct and is the interaction real, or does it look like "a familiar chain with new labels"? Should we add the Skeptic, merge roles, or change the loop?
6. **Data.** Is one provider through Zetaris enough? Which second source, if any, adds the most for the least effort? Are there methodological problems a pharmacovigilance expert would flag?
7. **Sponsor technology.** Will the Zetaris and Meterless use look load-bearing? Which Meterless engine would score best here: World Model, H-MEM or Scout Intent?
8. **Risks.** What could make a judge distrust the project (medical-advice concerns, overclaiming, weak signals)?
9. **Priorities.** With 5.5 days left, list the top 5 to 7 changes ranked by expected points per hour of work. Say what to cut.

Separate what you are confident about from your opinion, and say when an answer depends on facts this document does not give.
