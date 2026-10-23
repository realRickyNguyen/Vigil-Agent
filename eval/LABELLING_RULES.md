# Gold set labelling rules (v1, 22 Oct 2026)

The gold set says how each FAERS reaction *should* be classified, so the agents can be scored. This file explains how the labels were made, so anyone can check or repeat them.

## Who labelled it, and the limits

- Labelled by Claude (an AI assistant) on 22 Oct 2026, reading the label text the app itself uses. **Not yet reviewed by a person.** None of us is a pharmacovigilance professional. Before quoting accuracy numbers publicly, a team member should review every row, especially those marked `ambiguous`.
- Ground truth is **the label the system sees**: the one openFDA returns for the drug's generic name, registered in Zetaris. Its `set_id` and effective date are on each row. A different manufacturer's label for the same drug could differ.
- For metformin, openFDA returned the label of ZITUVIMET (sitagliptin + metformin). The gold labels follow that label, because the agents see it too. This is a known data issue (the Data Clerk should prefer single-ingredient labels).

## Which reactions are labelled

For each drug: the 20 reactions with the highest chi-squared among those passing the Evans screen (PRR ≥ 2, chi² ≥ 4, at least 3 reports), computed in Zetaris from openFDA data last updated 30 Jul 2026. The Analyst sees the top 30 by the same order, so most of what it classifies is covered. Findings outside the gold set are counted as "not scored".

Drugs: montelukast (asthma, allergic rhinitis), atorvastatin (cholesterol, cardiovascular risk), metformin (type 2 diabetes), sertraline (depression and other psychiatric disorders), isotretinoin (severe acne). Total: 100 rows.

## Categories and the order they are applied

Apply the first rule that matches.

1. **`not_meaningful`.** The term describes the product, its use, the report, or a circumstance rather than a clinical reaction. Examples: product-use and dosing errors, "drug ineffective" and "therapeutic product effect incomplete", "drug interaction" (no named event), treatment noncompliance, drug abuse, exposure during pregnancy, induced abortion, MedDRA social-circumstance terms such as "loss of personal independence in daily activities".
2. **`on_label`.** The label (any section: boxed warning, warnings, precautions, adverse reactions including postmarketing lists, contraindications) describes this reaction **as something the drug may cause or worsen**, using the same event, a synonym, or a broader term that clearly contains it. "Sleep disturbances" covers "nightmare". "Cough" covers "productive cough". A **narrower** label term does not cover a broader reaction: "thrombocytopenia" does not cover "full blood count abnormal".
   - A label that warns the drug can worsen the treated condition makes that condition `on_label`. For example, sertraline's warning about clinical worsening and depression listed among adverse events.
3. **`likely_indication_or_disease`.** The reaction is the condition the drug treats, a symptom or sign of it, a measure of it (for example blood glucose for a diabetes drug), or a complication of it. Also: outcomes the drug is given to prevent (for example myocardial infarction for a statin), and closely related diseases of the treated population. Mentioning the disease in the indications section does not make it `on_label`.
4. **`possible_new_signal`.** None of the above: the label does not describe it, and it is not the treated disease. This is a statistical flag only, not a claim that the drug causes it.

## The `ambiguous` flag

`ambiguous: true` means two categories are defensible and a reasonable reviewer could pick either. Ambiguous rows are left out of accuracy figures and reported separately. Common reasons:
- vague lab terms ("blood count abnormal")
- a reaction that is both the treated disease and a labelled effect
- pregnancy terms for a drug whose boxed warning is about pregnancy
- events typical of the treated population but not the treated disease itself (falls, chronic kidney disease)

## Evidence

Each row records:
- the label section and a short quote, if the label covers the reaction
- or the search terms that found nothing, if it does not

The label text was searched with regular expressions over all label sections, not only the sentences the app's retrieval returns.

## Known gaps in the taxonomy

- There is no category for **non-specific** terms (for example "full blood count abnormal"). They fall into `possible_new_signal` but are not actionable. A fifth category may be worth adding to the app.
- Litigation-driven reporting is not a category. Examples: atorvastatin and diabetes, isotretinoin and inflammatory bowel disease. The planned Skeptic agent is meant to detect it from reporter type.

## Version 2 (23 Oct 2026)

`eval/gold_v2.jsonl`, built by `eval/build_gold_v2.py`, replaces v1 as the default for scoring. v1 is kept unchanged for comparison with the 22 Oct baseline.

**Why.** Two changes on 23 Oct altered what the agents see:
- The drug search now uses generic name OR active substance (Bryan's finding). Each drug's top 20 by chi-squared changed: atorvastatin swapped 6 reactions, metformin, sertraline and isotretinoin 1 or 2 each, montelukast none.
- The Data Clerk now picks the newest single-ingredient prescription label instead of openFDA's first match. Metformin's label is no longer ZITUVIMET (sitagliptin + metformin).

**How.**
- Same rules and categories as v1, applied to the new top 20 and the newly chosen label (its `set_id` is on each row).
- Rows still in the top 20 keep their v1 decision unless the new label no longer supports the v1 evidence. Each row's `origin` says which applies: `kept from v1` (83), `re-checked against the new label` (7), `new in the top 20` (10).
- Re-checked: montelukast pneumonia and bronchitis (the newest label has no pediatric adverse-reaction list), metformin acute kidney injury (named only in the combination label's sitagliptin part) and weight decreased, sertraline intentional overdose, paranoia and drug abuse (evidence wording changed).
- Labelled by Claude (AI) from the label text and the screen only, **before looking at any output of the 23 Oct evaluation runs**. Earlier runs on 23 Oct had been looked at, for a few items. **Not yet reviewed by a person.**
