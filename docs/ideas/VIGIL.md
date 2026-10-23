# Vigil: Drug Reaction Review, design (updated 22 Oct 2026, 17:00 Sydney)

Named **Black Box** until 23 Oct 2026, with agents called Clerk, Hunter and Judge (now Data Clerk, Analyst and Reviewer). Traces and evaluation reports from before the rename keep the old names.

Practical state, how to run and next steps: [../HANDOFF.md](../HANDOFF.md). This file covers the design and the reasons behind it. Items are marked **built**, **planned** or **unknown**.

**Track:** 02, The Agent That Can Explain Why. We have not yet read the HackOS challenge statement for Track 02; it overrides the generic brief. The track can be changed until the deadline.

## Pitch

Vigil helps a drug-safety analyst decide which reported drug-reaction patterns deserve a closer look, and shows the evidence and objections behind that shortlist.

The pitch changed on 22 Oct after an outside review. The earlier one, "find side effects the label does not warn about yet", promised more than the results support: most strong signals turn out to be labelled effects or the treated disease, and the rest are often vague terms. The product's value is triage with an inspectable trail, not discovery. The name refers to the FDA's boxed warning.

## User and problem

**User:** a drug-safety analyst at a small biotech or hospital pharmacy doing first-pass review of public reporting patterns.

**Their task:** decide which associations deserve further examination, which have straightforward explanations, and which cannot yet be assessed.

**The data:** the FDA Adverse Event Reporting System (FAERS) is public, with about 20.7 million reports (openFDA, data updated 30 Jul 2026). Strong statistical flags often reflect the treated disease or labelled effects, so reading them needs interpretation. Vigil reduces the repetitive evidence reconciliation and keeps a decision trail an analyst can check.

## Why Track 02

- Track 02 asks for an investigation across sources that ends in an evidence-backed answer, with every conclusion traceable.
- The organisers' Track 02 example, ChurnWhy, has the same skeleton: a "correlation, not causation" caveat, and an evaluator that re-queries Zetaris to check the analyst's numbers.
- Track 01 is about reconciling records into one sourced answer. Track 03 is about decisions and actions. Neither fits as well.

## Input and output (built: decision contract v2)

**Input:** `{"drug": "<generic name>"}`. File examples are in `input_examples/`.

**Output:** a dossier whose core is a **review queue**. For each assessed reaction:

| Field | Values | Meaning |
|---|---|---|
| `context` | `clinical_event`, `treated_condition`, `non_clinical` | What kind of term it is |
| `label_coverage` | `covered`, `not_found`, `unclear`, `not_assessed` | Whether the current label already describes it as a drug effect |
| `review_priority` | `review_next`, `insufficient_evidence`, `lower_priority` | Whether an analyst should look next |
| `workflow_status` | `reviewed`, `unresolved`, `not_reviewed`, `pending`, `failed` | Whether the review finished, and how |
| `strongest_objection` | text | The Reviewer's best argument against the finding as it stands |
| `next_check` | text | One concrete check that would settle or advance it |
| `label_quote` | text | The label sentence, extracted by code, never written by the model |
| `history` | list | Each round's claim, verdict and objection |

The queue is ranked `review_next` first. Counts show how much of the screen was covered: reactions screened, passing the screen, shown to the Analyst, picked, assessed, decided by rule, reviewed, unresolved, pending, failed. A fixed caveat says that FAERS shows reporting association, not causation, and that this is not medical advice.

The older single category (`on_label`, `possible_new_signal`, `likely_indication_or_disease`, `not_meaningful`) is derived from `context` and `label_coverage` for the gold set.

**Rule from the review:** every finding promoted for review must state the claim, the supporting evidence, the strongest objection, the limitation and the next check. If the evidence cannot support the claim, narrow it or leave it unresolved. No numeric confidence: nothing is calibrated.

## Data in Zetaris

All sources are public openFDA endpoints, using aggregate counts only, so no case-level data reaches the app or the model.

| Zetaris object | openFDA query | State |
|---|---|---|
| `openfda.faers_reaction_totals` | `drug/event.json?count=patient.reaction.reactionmeddrapt.exact&limit=999` | Built (shared baseline) |
| `openfda.faers_total` | `drug/event.json?count=serious` (sum of the two rows) | Built |
| `openfda.faers_d2_<drug>_reactions` | `search=(patient.drug.openfda.generic_name:"<drug>" OR patient.drug.activesubstance.activesubstancename:"<drug>")&count=...reactionmeddrapt.exact&limit=999`, fully URL-encoded | Built, created at runtime (the older `faers_d_` tables used generic_name alone) |
| `openfda.faers_d2_<drug>_total` | same search, `count=serious` | Built, created at runtime |
| `openfda_rest.label_d_<drug>_raw` | `drug/label.json?search=openfda.generic_name:"<drug>"&limit=1` | Built, created at runtime |
| Reporter type for one drug and reaction | `search=<drug> AND <reaction>&count=primarysource.qualification` | Planned (Skeptic) |

**Confirmed facts about openFDA (22 Oct):**
- Count queries return flat `results: [{term, count}]`, which Zetaris flattens with `LATERAL VIEW explode`.
- Without a key, `limit` up to 999 works and 1,000 returns `API_KEY_MISSING`. openFDA's documentation says 1,000; our test says 999.
- The label endpoint serves the current label only.
- Reporter type comes back as integer codes 1 to 5. What each code means still needs checking against the field reference.

## Signal score (built)

Report-based 2×2 table per reaction, computed in Zetaris SQL:
- a = drug and reaction
- b = drug total − a
- c = reaction total − a
- d = all reports − drug total − reaction total + a

PRR = (a / (a + b)) / (c / (c + d)), with a Yates-corrected chi-squared. The screen is the Evans criteria: PRR ≥ 2, chi² ≥ 4, a ≥ 3.

Zetaris results matched an independent Python calculation. That validates the arithmetic, not the choice of population. Screen-positive means "worth a look", not novelty or causation.

## Agents

| Component | Kind | Job | State |
|---|---|---|---|
| Data Clerk | Code | Registers sources in Zetaris, runs the screen, fetches the label | Built |
| Rules | Code | Settles easy cases: administrative terms, the treated condition named in indications, the reaction named literally in the label | Built |
| Analyst | Nemotron Ultra via Nightshift | Picks up to 10 of the 30 strongest screen rows, then assesses them (context, coverage, priority, reasoning, next check) in batches of 3, seeing only the label sentences relevant to each reaction | Built |
| Reviewer | Code checks, then Nemotron Ultra | Code: numbers re-queried from Zetaris, evidence IDs real, label term present, fields consistent. Model: accept, reject with an objection, or unresolved; names missing reactions | Built |
| Skeptic | Zetaris queries plus Nemotron | One evidence operation (reporter-type composition) for the top review-next items. Context only, never proof | Planned |

**Loop:**
- Rejections and missing reactions go back to the Analyst for at most 2 revision rounds. Accepted findings are never redone.
- A revision that returns to an answer the Reviewer already rejected ends as `unresolved`, and so does an objection still standing when the rounds run out.
- Reactions the Reviewer names in the last round become `pending`.

**Resilience:**
- At most 2 model calls run at a time.
- A failed batch is retried one item per call.
- Persistent failures are reported (`failed`, `not_reviewed`), never guessed.

## Meterless

- **Nightshift** is the only model provider. Both agents are pinned to `nvidia/nemotron-3-ultra-550b-a55b`, with Nightshift set to one lane and no racing; see HANDOFF for why. The trace records the model that actually served each call.
- **World Model engine** (planned, required). Stable IDs for facts and claims, evidence links, source versions, timestamps, objections and decision states that the agents read. Behaviour test: changing a supporting label version reopens a dependent "not covered" verdict. We will **not** claim it reconstructs historical FAERS.
- **Scout Intent and H-MEM:** deferred.
- **Unknown:** whether organisers accept a Python engine implementation with our own tests.

## Evaluation (built)

- **Gold set:** `eval/gold_v1.jsonl` (100 reactions, 5 drugs), with rules in `eval/LABELLING_RULES.md`. Labelled by an AI assistant from the label text; **a person still needs to review it**. It is a development check, not clinical validation.
- **Scorer:** `eval/score.py`. It measures:
  - Analyst round-1 accuracy against final accuracy
  - what the Reviewer did to each item: fixed, caught, kept, unresolved
  - the gold category of every "review next" item
  - unresolved and open items
  - repeat-run agreement
- **First result** (contract v1, one montelukast run): 6/7 round-1 and 7/8 final on clear gold items. The Reviewer kept one wrong answer ("loss of personal independence" should be non-clinical).
- **Backtest:** off the critical path. FDA's labeling-change database cannot be scripted. openFDA returns the latest version of each case. Montelukast's warnings were in the precautions by 2012, so the 2020 boxed warning was an upgrade. See `eval/BACKTEST_FEASIBILITY.md`.

## Demo plan (draft)

About 3 minutes from one real run, with any time compression labelled:
1. The analyst's question.
2. The input and evidence scope (the counts).
3. One real exchange where the Reviewer's objection or the Skeptic's evidence changes a priority, or leaves an explained `unresolved`.
4. The resulting queue.
5. How a judge runs it.

**Strongest candidate climax:** a high-PRR signal whose priority drops once reporter-type evidence shows litigation-heavy reporting. Atorvastatin with type 2 diabetes and isotretinoin with inflammatory bowel disease are both in the gold set. **Avoid:** the montelukast early-detection story, and the full-blood-count flip-flop (it reads as instability).

## Limitations to state

- Counting reports that mention the drug includes reports where it was not the suspect drug. This broadens the population; it does not necessarily inflate the PRR.
- Coverage limits: the baseline holds only the 999 most-reported reactions, and the Analyst reviews at most 10 picks plus Reviewer-named additions. Both are shown in the counts.
- The aggregate data allows no case review and no duplicate removal. Marginal counts (reporter type, indication) give context, not adjustment for confounding.
- The label is the latest prescription label filed under the drug's most common single-ingredient generic name: one manufacturer's version among many. Before 23 Oct it was whichever label openFDA returned first, which for metformin was a combination product (ZITUVIMET).
- The Analyst and the Reviewer use the same model, so their agreement is not independent corroboration. The code checks are the independent part.

## Responsible use

- Not medical advice. The output and README say so. The input is a drug name, not a chat, which avoids personal treatment questions.
- openFDA's disclaimer (do not rely on it for medical decisions; results are unvalidated) is repeated in the output.
- Only aggregate public counts and label text reach NVIDIA's logged endpoint.
