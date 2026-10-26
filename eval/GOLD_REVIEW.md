# Gold set review, 26 Oct 2026

The reference sets that Vigil's accuracy figures are scored against were drafted by an AI (Claude). Our rule is that a person reviews them before any accuracy figure is quoted publicly. This file records that review.

## Who, what and how

- **Reviewer:** a team member (Ricky Nguyen) with AI assistance, on 26 Oct 2026. Not a pharmacovigilance professional.
- **Rows reviewed:** 86.
  - The 71 clear rows of [gold_v2.jsonl](gold_v2.jsonl), the rows the gold v2 accuracy figures are scored on. Its 29 ambiguous rows are already excluded from scoring, so they were not reviewed.
  - The 15 serious terms outside the screen for empagliflozin and zuranolone in [gold_newdrugs_v1.jsonl](gold_newdrugs_v1.jsonl), the rows behind the safety net's "14 of 15 hidden serious terms" result. The other 202 rows of that set were not reviewed.
- **Instrument:** [gold_review_2026-10-26.xlsx](gold_review_2026-10-26.xlsx), the filled sheet. For each row it shows:
  - the AI's label and evidence
  - the app's label search, and the label text where the reaction is named
  - the label sentences the agents are shown for that reaction
  - an automatic check that the AI's quoted evidence is in the label

  Every row's label was the same version (set ID and effective date) the AI drafted from. Vigil's own answers were left out of the sheet, so the review judged the label, not the system.
- **Rules:** [LABELLING_RULES.md](LABELLING_RULES.md), unchanged. The reviewer picked one of: agree, change (with the right category), make ambiguous, or unsure. No row was marked unsure. Every row has a note.
- **Result files:** [gold_v2_reviewed.jsonl](gold_v2_reviewed.jsonl) and [gold_newdrugs_v1_reviewed.jsonl](gold_newdrugs_v1_reviewed.jsonl). Each row has a `review` field with the verdict, the note, the reviewer, the date and, where a row changed, its earlier label. The original gold files are unchanged.

## Results

| | Rows reviewed | Agree | Changed | Made ambiguous | Agreement with the AI |
|---|---|---|---|---|---|
| gold v2, clear rows | 71 | 66 | 2 | 3 | 93% |
| gold_newdrugs_v1, serious terms outside the screen | 15 | 8 | 2 | 5 | 53% |

After the review, gold v2 has 68 clear rows (was 71). gold_newdrugs_v1 has 159 (was 157), because two ambiguous rows were resolved.

The newer-drug rows were the harder calls: 10 of the 15 were already marked ambiguous by the AI. The "14 of 15 hidden serious terms surfaced" result counts whether the safety net listed those terms, not how they are classified, so the review does not change it.

## Rows that changed

| Row | Reaction | Before | After | Reviewer's note |
|---|---|---|---|---|
| gold_v2 45 | metformin METABOLIC ACIDOSIS | on_label | possible_new_signal | Section 5.1 covers lactic acidosis, a narrower event. Metabolic acidosis is a contraindication (section 4); section 7 attributes it to other drugs. Rule 2: possible_new_signal. |
| gold_v2 62 | montelukast WHEEZING | likely_indication_or_disease | ambiguous | Asthma symptom, but sections 5.5 and 6.2 also warn of worsening pulmonary symptoms in eosinophilic reactions; whether that covers the isolated symptom is unresolved. |
| gold_v2 64 | montelukast DYSPNOEA | likely_indication_or_disease | ambiguous | As for wheezing. |
| gold_v2 78 | montelukast NASAL CONGESTION | likely_indication_or_disease | on_label | Section 6.1, Table 5, lists nasal congestion as an adverse reaction; on_label comes before the rhinitis indication. |
| gold_v2 85 | sertraline INTENTIONAL SELF-INJURY | on_label | ambiguous | Suicidal behaviour does not cover all intentional self-injury (rule 2); excluded from clear scoring. |
| newdrugs 34 | empagliflozin NECROTISING FASCIITIS | possible_new_signal, ambiguous | possible_new_signal | Sections 5.3 and 6.2 and the Medication Guide limit the warning to the perineum; the report gives no site. |
| newdrugs 39 | empagliflozin AMPUTATION | on_label, ambiguous | ambiguous | Section 5.5 covers lower limbs only; an unspecified amputation could be diabetes-related or unlisted. |
| newdrugs 40 | empagliflozin OBSTRUCTIVE SLEEP APNOEA SYNDROME | likely_indication_or_disease, ambiguous | ambiguous | No label match; a diabetes comorbidity or a distinct unlisted disease. |
| newdrugs 193 | zuranolone PERINATAL DEPRESSION | on_label, ambiguous | on_label | Section 5.3 and the Medication Guide warn of new or worsening depression, which covers it; on_label comes before the indication. |
| newdrugs 195 | zuranolone SOMNOLENCE NEONATAL | possible_new_signal, ambiguous | ambiguous | Section 5.2 labels somnolence; section 8.2 has no infant data. The rules do not settle a transfer to the infant. |
| newdrugs 196 | zuranolone BRIEF PSYCHOTIC DISORDER, WITH POSTPARTUM ONSET | likely_indication_or_disease, ambiguous | ambiguous | A related postpartum illness or a distinct unlisted syndrome; section 9.3's paranoia does not cover it. |
| newdrugs 197 | zuranolone LACTATION DISORDER | possible_new_signal, ambiguous | ambiguous | Section 8.2's uncertainty about milk production is not a labelled disorder. |

The four rows flagged before the review were decided as follows:
- **METABOLIC ACIDOSIS:** changed to possible_new_signal.
- **INTENTIONAL SELF-INJURY:** made ambiguous.
- **ANXIETY and PANIC ATTACK:** kept as on_label. Sections 5.5 and 6.1 and the Medication Guide cover them, though the AI's original quotation was inaccurate.

## What this means for the figures

- **gold v2:** figures scored against `gold_v2_reviewed.jsonl` can be quoted as agreement with "a reference set drafted by an AI and reviewed by a team member with AI assistance (93% of its clear rows confirmed)". This is still not clinical validation.
- **gold_newdrugs_v1:** only 15 of its 217 rows were reviewed. Its accuracy figures remain scores against an AI-drafted reference and must say so.
- **Re-scoring:** the scorer needs each run's trace and dossier in `logs/`, so runs are re-scored on the machine that ran them.

  ```bash
  python -I eval/run_eval.py --gold eval/gold_v2_reviewed.jsonl --score-only <run_id> [<run_id> ...]
  ```

  ```bash
  python -I eval/run_eval.py --gold eval/gold_newdrugs_v1_reviewed.jsonl --score-only <run_id> [<run_id> ...]
  ```

- **Scoring check:** four montelukast runs of the current code on 26 Oct (`20261025T232106Z-a67ca7`, `20261025T235739Z-f84fab`, `20261026T002234Z-4bab43`, `20261026T003751Z-40f946`) were scored against both versions of gold v2.
  - Against the original: round 1 38 of 40, final 37 of 38.
  - Against the reviewed version: round 1 30 of 32, final 30 of 31.

  Fewer items are scored, because WHEEZING and DYSPNOEA are now ambiguous and NASAL CONGESTION changed. The accuracy is about the same.
