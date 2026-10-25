# Clinical reliability (task 2, 25 Oct 2026)

Bryan's task 2 makes Vigil's answers to "What does the label already say?" and "What weakens it?" more reliable, and shows how thin each piece of evidence is. It's the commits from `95170a6` to `65d7c50`, on top of `53d100d`.

- 235 offline tests passed at `65d7c50`, the 8 server tests included, and each commit passed them on its own.
- Ricky's five files (`app/server.py`, `run.py`, `app/config.py`, `Dockerfile`, `.dockerignore`) are the same as at `53d100d`. Commit `475e184` added a setting to `app/config.py` and `a5da998` took it out again, so only the history touches it. Every limit is a module constant.
- Task 2's own commits change [docs/HANDOFF.md](HANDOFF.md) only by code-map rows and one pointer paragraph.
- The API returns the whole dossier, so the new fields come through unchanged.

**What can change a status.** The label search's code checks are meant to. They reject coverage cited from a section that doesn't count, and they reject "not found" when the search names the reaction where coverage counts. Everything else here is context only (report sources, uncertainty marks, the scope block, the manual-review flag and the safety net), with one exception. The Reviewer is told to reject reasoning that calls a thin row significant, strong or robust. When the run budget skips the revision round, an item rejected that way ends unresolved.

## What it adds

| Piece | Commits | Main files | What it does |
|---|---|---|---|
| Label search | `95170a6`, `288c5bf`, `2855075`, `dd420d5` | [label.py](../app/data/label.py), [faers.py](../app/data/faers.py), [reviewer.py](../app/agents/reviewer.py), [rules.py](../app/agents/rules.py) | Also fetches the Medication Guide, patient leaflet, patient counselling, mechanism of action, pharmacodynamics, interactions, pharmacokinetics and the pregnancy sections. Before any model call, code looks for each reaction's name in every fetched section, and the prompt and the dossier item say what was searched and where it was found. |
| Report sources | `475e184`, `a5da998` | [sources.py](../app/data/sources.py), `report_sources` in [faers.py](../app/data/faers.py), [pipeline.py](../app/orchestration/pipeline.py) | For review-next items, openFDA counts by country and by reporter type, against the drug's usual mix, as Zetaris REST tables. Context flags only. |
| Uncertainty and scope | `2fbcca2` | [uncertainty.py](../app/data/uncertainty.py), `screen_table` in [analyst.py](../app/agents/analyst.py), [pipeline.py](../app/orchestration/pipeline.py) | The expected count, PRR 95% interval, IC025 (Norén et al. 2013) and a thin-evidence mark for every screened row, worked out in code. A `data.scope` block names both 999 caps. |
| Manual-review flag | `0b33b20` | [manual_review.py](../app/orchestration/manual_review.py), [MANUAL_REVIEW_RULES.md](../eval/MANUAL_REVIEW_RULES.md) | A flag with reasons on every dossier item. The rules were committed before any run scored them. |
| Safety net | `2f41eac`, `17e91ee`, `13421ee`, `861096b`, `6d66f8b`, `65d7c50` | [safety_net.py](../app/data/safety_net.py), `serious_terms` in [faers.py](../app/data/faers.py) | Serious terms outside the screen, for a person to review. Never in the queue or a prompt. |
| Rule fixes | `e5d1ba1` | [rules.py](../app/agents/rules.py) | Dosing and handling errors go aside, and a population named in the indications goes to the model. |

The tests are in [test_label_search.py](../tests/test_label_search.py), [test_sources.py](../tests/test_sources.py), [test_uncertainty.py](../tests/test_uncertainty.py), [test_manual_review.py](../tests/test_manual_review.py), [test_label_rules.py](../tests/test_label_rules.py) and [test_safety_net.py](../tests/test_safety_net.py).

**Label search, in more detail.**
- **How a name is found.** The search finds the MedDRA name or its two words the other way round, a set synonym ("discontinuation syndrome" for WITHDRAWAL SYNDROME, hypoglycaemia for BLOOD GLUCOSE DECREASED), or for a term with a direction its words next to a word for that change. FAERS's `^` apostrophe is read as `'`.
- **What can support coverage.** Only warnings, adverse reactions, patient counselling and the side-effect parts of a Medication Guide or leaflet.
- **What never counts on its own.** Pharmacology is quoted as an expected effect of the drug. Contraindications, a Limitation of Use, interactions, pharmacokinetics, the pregnancy sections and the leaflets' "who should not take" parts don't count on their own.
- **Enforcement.** `code_checks` rejects coverage cited from a section that doesn't count, and rejects "not found" when the search names the reaction where coverage counts. The rules still settle coverage only from the professional safety sections.
- **Checked offline on the real labels.**
  - Sertraline PANIC ATTACK is in its Medication Guide.
  - Ozempic WEIGHT DECREASED is an expected effect.
  - Ozempic DECREASED APPETITE is found nowhere.
  - Metformin METABOLIC ACIDOSIS is named only where it doesn't count.
  - Sertraline WITHDRAWAL SYNDROME is covered as "discontinuation syndrome".

**Report sources.**
- **The flags.** One country holds 60% or more of the reports with a known country, 30 or more points above the drug's usual share. Lawyers filed 20% or more. Health professionals filed under 50%.
- **When a flag is unknown.** Each flag needs 10 reports. The reporter checks are "unknown" when under half of the item's reports say who reported.
- **How they're used.** The Reviewer sees the flags but is told never to reject on one alone.
- **Timing.** The checks run in the background while the Reviewer works through the other items first, and the waits are bounded by the run budget.

**Uncertainty.** A row is thin when it has under 5 reports or IC025 at or below 0. Both prompts say a thin row must be called thin evidence, never significant, strong or robust. Sotagliflozin's RENAL PAIN (4 reports, PRR interval 5.5 to 38.8) is the case that prompted it.

**Manual-review flag.** It has five triggers.
- under 5 reports
- "unclear" coverage, or a name found only where it doesn't count
- any Reviewer rejection
- any status other than reviewed
- a Skeptic attenuation

It changes no status, priority or ranking, and no agent sees it.

**Safety net.** It has three sections, and a term sits in the first that takes it.
- `designated_medical_events`, EMA's 62 designated medical events (EMA/326038/2020)
- `missed_serious_terms`, Bryan's rule of 25 Oct
- `pregnancy_and_newborn`, pregnancy, breastfeeding and newborn terms, matched by whole words, with no cap

A missed serious term is any clinical term outside the screen (by a 999 cap or the 3-report floor) where more than half of the drug's reports with it are flagged serious in FAERS, with no cap. The threshold is the module constant `SERIOUS_SHARE = 0.5`. The dossier shows it and each term's serious share. The serious counts come from the run's existing seriousness query, so nothing new is downloaded. The section's limits count every term outside the screen that isn't listed. That covers terms half or less serious, terms the rule can't judge because they have no serious count below a full serious list's cutoff, and non-clinical terms the rules set aside. Nothing is dropped silently.

**The clinical layout, Bryan's of 25 Oct.** A reviewer's first question is whether a serious reaction is already on the label, so the section is laid out for that.
- A summary line comes first. It gives the terms listed, how many are outside the screen, how many the label search doesn't find by name, and the 5 of those with the most serious reports.
- Designated medical events come first, always shown, even with 1 report. Then the missed serious terms, then pregnancy and newborn terms.
- In every section, terms the label search doesn't find come first, then terms named only outside effect text (such as a contraindication), then terms covered by effect text. Within each, they run by serious reports, with an unknown count last.
- Every row has its reports, serious reports and share, its label status with the sections, a designated medical event flag and a thin mark under 3 reports, plus its screen status.
- It's display only. `test_a_whole_run_never_promotes_safety_net_terms` runs the whole pipeline with and without the safety net and checks every prompt is the same, word for word.

Counts come from the drug's own reaction table in Zetaris, which costs no openFDA call when that list is complete. When it's full at 999, 2 or 3 direct counts are added.

Checked read-only through Zetaris on 25 Oct.
- **Semaglutide**, 171 missed serious terms, including medullary and papillary thyroid cancer, necrotising and obstructive pancreatitis, and paralytic ileus, at 98 to 100% serious. FOOD CRAVING (14% serious), SENSITIVE SKIN and INJECTION SITE DISCHARGE are left out, and PANCREATITIS stays among the designated medical events.
- **Empagliflozin**, led by EUGLYCAEMIC DIABETIC KETOACIDOSIS, KETOACIDOSIS and FOURNIER^S GANGRENE.
- **Zuranolone**, 67 missed serious terms, such as BRIEF PSYCHOTIC DISORDER, WITH POSTPARTUM ONSET (4), HOMICIDAL IDEATION and TRANSIENT ISCHAEMIC ATTACK (2 each), and 17 pregnancy terms, with EXPOSURE VIA BREAST MILK (22) and SOMNOLENCE NEONATAL (8). The limits count 212 more terms outside the screen that are half or less serious.

The earlier rule took the 10 most-reported hidden terms, which picked FOOD CRAVING and missed the thyroid cancers. The first version of the new rule (`17e91ee`) also missed terms that are in the all-drugs list but have only 1 or 2 reports, so the screen never reaches them either. That lost 29 of zuranolone's terms, and `13421ee` fixed it.

Rendered read-only with each drug's chosen label on 25 Oct. The render passes no screen rows, so every term counts as outside the screen.
- **Semaglutide**, 307 terms, 292 not found by name and 4 named only outside effect text. MEDULLARY THYROID CANCER is covered by the boxed warning and the Medication Guide and sits at row 170 of 171 in its section, below every unlabelled term. PAPILLARY THYROID CANCER, a different tumour the label doesn't name, stays not found at row 25. The summary's top 5 are OPTIC ISCHAEMIC NEUROPATHY, GASTROINTESTINAL HYPOMOTILITY, BLINDNESS, CYCLIC VOMITING SYNDROME and RENAL FAILURE.
- **Empagliflozin**, 285 terms, 256 not found by name. FOURNIER^S GANGRENE and NECROTISING FASCIITIS are covered. EUGLYCAEMIC DIABETIC KETOACIDOSIS leads the summary, though a broader warning covers it (decision 9).
- **Zuranolone**, 86 terms, 84 not found by name, most of them thin. ACUTE KIDNEY INJURY and PANCREATITIS head the list with 1 report each.

## Effect on the gold set (offline, real chosen labels)

Against `53d100d` the code changes 5 of 100 rows in [gold v2](../eval/gold_v2.jsonl) and 7 of 100 in [gold v1](../eval/gold_v1.jsonl).
- In 4 v2 and 5 v1 rows, all gold on_label, "not found" is now rejected because the label names them. They're sertraline PANIC ATTACK, metformin BLOOD GLUCOSE DECREASED, atorvastatin BLOOD CREATINE PHOSPHOKINASE INCREASED, and isotretinoin's lipid terms.
- Atorvastatin's diabetes rows (ambiguous in gold) now go to the model instead of being settled as the treated condition.
- The gold files are unchanged.

## Results

The results at Ricky's code defaults (4 model calls at a time, 1 revision round, a 600 s budget) are in the [README](../README.md#results-so-far)'s Results section and [eval/reports/reeval-25oct-summary.md](../eval/reports/reeval-25oct-summary.md). Task 2 ran there as `13421ee`. Its later commits change only the safety net's display, which no agent sees. Task 2's earlier live checks used a developer's `.env` (2 model calls at a time, 2 revision rounds), so they're superseded.

## Decisions left open

1. **An "expected pharmacology" category.** Gold has none. For now a reaction the label names only in its pharmacology is coverage "unclear", so it scores as a possible new signal, and its priority is left to the agents. Semaglutide WEIGHT DECREASED shows it. IMPAIRED GASTRIC EMPTYING ended unresolved once, over "delays gastric emptying" in pharmacodynamics-style warning text.
2. **The "unknown" reporter cut-off.** Under half of an item's reports say who reported. Only about 28% of 2026 Q2 reports do.
3. **Preferring the brand holder's label over repackager copies.** It would change `choose_label` and the basis of gold v2, so nothing here does it.
4. **The safety net's length.** Bryan chose the missed-serious rule with no cap, so semaglutide shows 171 missed serious terms and 83 pregnancy terms. There's no report floor either, so a small drug lists many thin terms. 65 of zuranolone's 67 have only 1 or 2 reports. A few product-use or vague terms the rules don't catch also appear, such as PRESCRIPTION DRUG USED WITHOUT A PRESCRIPTION, DRUG TITRATION ERROR and ADVERSE REACTION. For a full list, pregnancy terms below its cutoff come from an openFDA word search, which goes beyond the fixed list in the brief.
5. **The thin-row rule and the run budget.**
   - The Reviewer is told to reject reasoning that calls a thin row strong. When the revision round is skipped for time, that item ends unresolved. This is the one way the context can change a status.
   - The report-source waits draw on the same run budget, so in a slow run they leave less time for later steps.
6. **ACCIDENTAL OVERDOSE.** It's now set aside as a dosing error, following the gold rules for dosing errors ([LABELLING_RULES.md](../eval/LABELLING_RULES.md)). OVERDOSE and INTENTIONAL OVERDOSE stay clinical.
7. **Gold v2's metformin METABOLIC ACIDOSIS row** (on_label, already flagged for human review) may disagree more often, because contraindication, interaction and pharmacokinetic text no longer counts.
8. **Two wordings only the safety net reads (`6d66f8b`).** The label search matches British to US spelling but not -ise words, or cancer to carcinoma. So semaglutide's MEDULLARY THYROID CANCER (the boxed warning's "medullary thyroid carcinoma") and PANCREATITIS NECROTISING ("necrotizing pancreatitis") weren't found. The safety net's label status now tries both and says when it used one. The agents' search is unchanged, to keep the re-evaluation's inputs fixed, so it still misses them. Folding both into [label.py](../app/data/label.py) would fix the agents too. The carcinoma wording is tried only for terms of 3 or more words, because a two-word THYROID CANCER would match inside "medullary thyroid carcinoma" and read as covered. Setting `LABEL_VARIANTS = ()` in [safety_net.py](../app/data/safety_net.py) turns the fallback off.
9. **A broader label term.** The label search finds names, not broader terms. Empagliflozin's top missed serious term, EUGLYCAEMIC DIABETIC KETOACIDOSIS (2,234 serious reports), shows as not found, though its label has a "Diabetic Ketoacidosis ... and Other Ketoacidosis" warning. The summary says a broader term may still cover a term it doesn't find. A hint that names the broader term in effect text would help a reviewer, but it would be a fourth label state, so it isn't built.

## Known limits

- **The label search finds names, set synonyms and simple changes only.** A broader term, such as "suicidal thoughts and behaviors" for SUICIDE ATTEMPT, isn't found, and the "not named" line says so.
- **A leaflet's "most important information" part can list risk factors.** Metformin's "get dehydrated" is an example. A name there still blocks "not found", which is why the rules don't settle coverage from patient text.
- **Background Zetaris calls can outlive the run.** The report-source and safety-net pools cancel queued work when a run ends, but a call already running finishes. So `run.py` can wait after the dossier is written, and a late query line can land in the trace after `run_end`. This has no effect on results.
- **Time.** Building the safety net, with a label search for every term, took 2.1 s for semaglutide's 307 terms, after the queue is ranked.
- **Cost.** Each review-next item's report-source check costs 2 to 4 openFDA reads, plus the same again per run for the drug's usual mix. The safety net costs 0 to 3. That's within the no-key limit of about 1,000 a day.
- **A stray character.** [docs/HANDOFF.md](HANDOFF.md) holds a control character (BEL) from `44c9bb4`, which predates task 2.
