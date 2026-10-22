# Black Box: design (draft, 22 Oct 2026)

**Status:** proposal; agents not built. The go/no-go data test **passed on 22 Oct**: openFDA works as Zetaris REST tables, tables can be created at runtime through the REST API, and the PRR join in Zetaris matches an independent Python calculation (`scripts/zetaris/openfda_baseline.sql`, run with `scripts/zetaris/run_sql.py`). Items are marked **confirmed** (tested by us), **proposal** or **unknown**.

**Track:** 02, The Agent That Can Explain Why. We have not yet read the HackOS challenge statement for Track 02. If it is narrower than the generic brief, check fit before committing. The track can be changed until the deadline.

## Pitch

An agent team that investigates whether a drug has a side effect its label does not warn about, argues against its own findings, and shows the evidence for every conclusion.

The name refers to the FDA's boxed warning, its strongest label warning.

## User and problem

The user is a drug-safety (pharmacovigilance) analyst at a hospital pharmacy or small biotech, or a health journalist. The FDA Adverse Event Reporting System (FAERS) is public and holds about 20.7 million reports (confirmed, openFDA `meta.results.total`, data updated 30 Jul 2026). Reading it well needs statistics and knowledge of its biases, which most of these users do not have time for.

Each run answers one bounded question: does drug X have a reported side effect that its label does not cover, and does that signal survive scrutiny?

## Why Track 02 and not 01 or 03

- Track 02 asks for investigation across sources ending in evidence-backed answers where every conclusion is traceable. That is the product.
- The organisers' Track 02 example (ChurnWhy) has the same skeleton: a "correlation, not proven causation" caveat and an Evaluator that re-queries Zetaris to check the Analyst's numbers. Black Box needs both for medical reasons.
- Track 01 is about reconciling disagreeing records into one sourced answer. Our sources disagree, but the output is an explanation, not a reconciled record.
- Track 03 is about decisions and actions. A drug-safety tool should not take actions.

## Input and output

Input (`input_examples/*.json`):

```json
{ "drug": "montelukast", "reaction": null, "as_of": "2019-01-01" }
```

`reaction` is optional (null means screen all reactions). `as_of` is optional and runs the backtest.

Output is a signal dossier. Each candidate side effect carries:

- a verdict: `on_label`, `emerging_signal`, `explained_by_confounder` or `insufficient_data`
- a confidence level
- evidence: the numbers, the SQL that produced them, and the source URLs
- `untested_factors`
- a fixed caveat that FAERS reports show association, not causation

## Data in Zetaris

All sources are public openFDA endpoints. We use aggregate count queries only, so no individual case reports pass through the app or the model.

| Zetaris table | openFDA query | Purpose |
|---|---|---|
| `faers_reaction_totals` | `drug/event.json?count=patient.reaction.reactionmeddrapt.exact&limit=999` | Reports per reaction across all drugs. The baseline. One fixed URL. |
| `faers_total` | `drug/event.json?limit=1` | Total report count (`meta.results.total`) |
| `faers_drug_reactions` | `search=<drug>&count=patient.reaction.reactionmeddrapt.exact` | Reactions reported with this drug |
| `faers_drug_total` | `search=<drug>&limit=1` | Total reports for this drug |
| `faers_drug_indications` | `search=<drug>&count=patient.drug.drugindication.exact` | What patients took the drug for (Skeptic) |
| `faers_reporter_type` | `search=<drug>+AND+<reaction>&count=primarysource.qualification` | Who filed the reports (Skeptic) |
| `faers_timeline` | `search=<drug>+AND+<reaction>&count=receivedate` | Reports over time (backtest, spike detection) |
| `faers_comedication` | `search=<drug>+AND+<reaction>&count=patient.drug.openfda.generic_name.exact` | Other drugs in the same reports (Skeptic) |
| `drug_label` | `drug/label.json?search=openfda.generic_name:<drug>` | Label text and effective date |
| `drug_recalls` | `drug/enforcement.json?search=<drug>` | Recalls and bad batches (Skeptic) |

### What we confirmed about openFDA (22 Oct, by curl)

- Count queries return a flat `results: [{term, count}]` array. This is the shape Zetaris handles well.
- Count queries do not return a total. A search with `limit=1` returns `meta.results.total`, which gives the totals for the 2×2 table.
- Without an API key, a count query accepts `limit` up to 999. `limit=1000` returns `API_KEY_MISSING`. So the baseline holds the top 999 reactions only. Rarer reactions would need a key or a per-reaction lookup.
- The montelukast label in openFDA has a `boxed_warning` field for serious neuropsychiatric events and `effective_time` 20260305. The label endpoint returns the current label, not the history.
- `primarysource.qualification` comes back as integer codes 1 to 5. The meaning of each code (we expect 4 = lawyer) still needs checking against the openFDA field reference.
- Searching by `patient.drug.openfda.generic_name.exact:"MONTELUKAST SODIUM"` returned 121,068 reports.

## Signal score

Standard disproportionality, computed in SQL on Zetaris:

- a = reports with the drug and the reaction
- b = reports with the drug and not the reaction
- c = reports with the reaction and not the drug
- d = reports with neither

PRR = (a / (a + b)) / (c / (c + d)). Screening threshold (Evans criteria): PRR ≥ 2, chi² ≥ 4, a ≥ 3.

### First numbers (confirmed, 22 Oct, computed in Python from openFDA, not yet in Zetaris)

Montelukast against the top-999 baseline, all dates. Of 780 reactions with at least 3 reports:

- The top of the list is the drug's own indication: obstructive airways disorder (PRR 47), asthma (27), wheezing (26), seasonal allergy (15). This is confounding by indication, the Skeptic's first check. A plain PRR ranking without a Skeptic would give a misleading answer.
- The neuropsychiatric signal is present but lower down: nightmare (PRR 5.7, rank 43), aggression (5.5), anger (5.3), suicidal ideation (4.2), abnormal dreams (3.4). All pass the PRR ≥ 2 screen.
- These counts include reports filed after the 2020 boxed warning, so they carry notoriety bias. The backtest has to cut by `receivedate` to say anything about early detection.

The calculation is in `scripts/zetaris/openfda_baseline.sql` (query B3). Zetaris should reproduce these values.

### Approximations

b = drug total − a. c = reaction total − a. d = grand total − a − b − c. One limit applies. A report can list many reactions, and these totals count reports, so the 2×2 table is approximate. We will state this as a limitation.

## Agents

| Agent | Model via Nightshift | Job | Can block or retry? |
|---|---|---|---|
| Intake | Nemotron Lightning + Scout Intent engine | Parses the request. Redirects personal medical questions ("should I stop my medication?") to a clinician. Blocks prompt injection. | Blocks |
| Hunter | Nemotron Super | Runs the screen and ranks candidate signals. Matches MedDRA reaction terms in FAERS to the free text of the label. | No |
| Skeptic | Nemotron Super | Attacks each signal with its own queries: confounding by indication, lawyer-driven reporting, a notoriety spike after one date, co-medication, a recalled batch | Sends signals back |
| Judge | Nemotron Super (or Ultra) | Re-runs key numbers on Zetaris. Rejects claims without a query ID. Forces the caveat. Gives verdicts. | Rejects and retries, at most 2 rounds |
| Writer | Nemotron Lightning | Writes the dossier from the verdicts | No |

The collaboration moment for the demo (the numbers will come from the real run):

1. Hunter flags "suicidal ideation".
2. Skeptic finds a large share of the drug's reports list depression as the indication, and marks the signal as possibly confounded.
3. Hunter replies with a count restricted to reports with other indications.
4. Judge re-queries, confirms the number, and gives the verdict.

Every step goes to `logs/trace-<id>.jsonl`.

## Meterless

- **Nightshift** is the only model provider. Every agent call goes through `http://127.0.0.1:8088/v1` with a pinned Nemotron model.
- **World Model engine** (primary, with the passing test). Every fact an agent writes is an event with provenance: query ID, source URL and retrieval time. Facts are bitemporal (when the report happened, when we learned it), which drives the `as_of` backtest. Competing Hunter and Skeptic claims about one signal go through the engine's merge rules.
- **Scout Intent engine** (second). The Intake guard.
- **H-MEM** (optional). Remembers earlier verdicts per drug across runs.

Unknown: whether organisers accept a Python port of an engine with ported tests. Ask on HackOS.

## Demo and sample inputs

Candidates. Each needs checking against the data before we rely on it.

1. Montelukast, `as_of` 2019-01-01. The FDA added the boxed warning for neuropsychiatric events in March 2020. Would the agents have raised the signal before that, and by how much? Report the result either way.
2. Semaglutide, current data. NAION appeared on European labels in 2025.
3. A negative control: an old, well-understood drug where the right answer is "nothing beyond the label".

Video plan (3:30):

| Time | Segment |
|---|---|
| 0:00–0:20 | Problem, user, "Track 02" |
| 0:20–0:45 | Architecture diagram, data is public openFDA |
| 0:45–1:30 | Hunter and Skeptic exchange in the live trace |
| 1:30–2:15 | Backtest: montelukast as of 2019 |
| 2:15–2:45 | Zetaris queries and Nightshift/Nemotron calls in the trace |
| 2:45–3:30 | Dossier, caveat, limitations |

## Risks, in the order to test them

1. ~~openFDA as a Zetaris REST table.~~ **Confirmed working (22 Oct).** Baseline, totals and the montelukast tables all registered, cached and queried.
2. ~~Per-drug tables.~~ **Confirmed (22 Oct):** `CREATE LIGHTNING REST TABLE`, `CREATE SCHEMASTORE VIEW` and `CACHE TABLE` all work through `POST /sql-editor/sqls/run`. The Clerk can register a table for any drug at runtime, so a new input gives a real answer. Still to decide: naming and clean-up for tables created per run. `DROP VIEW` works in SQL; REST tables can only be removed in Data Explorer, so they will pile up.
3. **Rate limits.** openFDA documents about 240 requests per minute and 1,000 per day per IP without a key (not confirmed by us; the responses carried no rate-limit headers). Use `CACHE TABLE`. A free key goes in the URL, so it must never be committed in SQL.
4. **Label history.** openFDA serves the current label. For "when was this warning added" we may need DailyMed label history. Check before promising the backtest's label date.
5. **Reporter codes.** Confirm the meaning of `primarysource.qualification` codes.
6. **World Model port.** Organiser answer needed.

## Responsible use

- The app is not medical advice. The UI, README and deck say so, and Intake redirects personal questions.
- openFDA's own disclaimer says not to rely on it for medical decisions and to treat results as unvalidated. We repeat that.
- Only aggregate counts reach the model, so no case-level data goes to NVIDIA's logged endpoint.

## Schedule (Sydney dates)

- 22 Oct: openFDA in Zetaris; runtime DDL test; HackOS questions.
- 23 Oct: minimal loop, Hunter → Judge on one drug, with a trace.
- 24 Oct: Skeptic, retries, World Model port and tests.
- 25 Oct: backtest, `SAMPLE_MODE` cache, Dockerfile, full judge-style test.
- 26 Oct: UI, README, deck, video.
- 27 Oct: submit with buffer before 27 Oct 23:45 UTC (28 Oct 10:45 Sydney).
