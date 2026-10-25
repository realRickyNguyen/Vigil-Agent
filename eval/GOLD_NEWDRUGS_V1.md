# Reference set for newer and low-data drugs (v1, 25 Oct 2026)

`eval/gold_newdrugs_v1.jsonl` is the reference set for Task 3, which tests how Vigil handles newer drugs and drugs with few reports. It has the same fields as `eval/gold_v2.jsonl` and is scored the same way (`python -I eval/run_eval.py --gold eval/gold_newdrugs_v1.jsonl --score-only <run_id> ...`).

**AI-drafted and not reviewed by a person.** Don't quote accuracy on it publicly until a team member has reviewed every row, starting with the ambiguous ones.

## Drugs and labels

Six drugs, with the label each baseline run used. The label the app chooses today is the same version for all six (checked 25 Oct).

| Drug | Label | Effective | set_id |
|---|---|---|---|
| empagliflozin | Jardiance | 26 Aug 2026 | 59ed43d9-b4e0-72a2-e063-6394a90a327d |
| semaglutide | Ozempic | 30 Jul 2026 | 42bdd912-2393-44c4-b7e0-47672ca28991 |
| tirzepatide | Zepbound | 28 Aug 2026 | 487cd7e7-434c-4925-99fa-aa80b1cc776b |
| fezolinetant | Veozah | 26 Feb 2026 | cae9f798-24f9-4580-a4fc-e6c710cbda3c |
| zuranolone | Zurzuvae | 15 Jun 2026 | f18e53b0-d0bb-422d-8de7-ab64b7292b29 |
| sotagliflozin | Inpefa | 12 Aug 2026 | 1a46614e-05f6-421a-b6f4-d6f8760d643a |

## Which reactions

Two parts, set by `origin`.
- **Top 30 screen-positive by chi-squared** (170 rows). That's what the Analyst sees: the Evans screen (PRR at least 2, chi-squared at least 4, at least 3 reports), sorted by chi-squared, first 30. Sotagliflozin has only 20 passing rows, so all 20 are in. Computed in Zetaris with the app's own `signal_sql`. The counts match the baseline dossiers.
- **Serious terms outside the screen** (47 rows). These are in the drug's own top 999 reactions but not in openFDA's all-drugs top 999, so the screen never tests them. They have at least 3 reports and match a fixed list of serious, liver, pregnancy, lactation and newborn word stems, set before labelling. `a` is the drug's report count. `prr` and `chi2` are null, because the all-drugs count isn't known. The stems also caught a few rows that aren't safety terms in the usual sense (OBSTRUCTIVE SLEEP APNOEA SYNDROME, from "OBSTRUCTI"). They are kept so the rule stays as written.

## How it was labelled

- Rules: `eval/LABELLING_RULES.md`, v1 rules and the v2 section, unchanged.
- Two extra conventions, so disputed rows are marked rather than settled quietly.
  - If the only support is pharmacology text describing an expected effect (mechanism of action, pharmacodynamics, clinical pharmacology), the row takes the category the rules give and is marked ambiguous. This matches the open "expected effect" decision in HANDOFF.
  - If the only support is a contraindication, interaction, pharmacokinetics or overdosage passage, the row is marked ambiguous.
- Blind. Each drug was labelled by an Opus subagent that saw only the rules, the full label text (every text section, named) and the term list. It saw no counts, dossiers, traces, reports or write-ups.
- Two independent passes. A second Opus subagent labelled every row again from the same inputs. A row where the two passes disagree on the category is marked ambiguous (fixed before the second pass came back). The first pass's category is kept, and the second pass's answer is added to the evidence, summarised by the session. The passes agreed on 210 of 217 categories (Cohen's kappa 0.946), and on 157 of the first pass's 158 clear rows. The 7 disagreements are now ambiguous. On 11 more rows the second pass agreed on the category but called it ambiguous where the first didn't. They stay clear under the rule, and a reviewer may want to look at them first: empagliflozin and tirzepatide IMPAIRED GASTRIC EMPTYING, semaglutide WEIGHT INCREASED, BLOOD GLUCOSE DECREASED and HEPATIC PAIN, tirzepatide ILLNESS, zuranolone BRAIN FOG, GAIT INABILITY, DEPRESSION and DEPRESSED MOOD, and sotagliflozin RENAL PAIN.
- Result: 217 rows, 157 clear and 60 ambiguous.
- Checked by code. Every quote in an `on_label` row was found in that label's text. Two fezolinetant quotes were paraphrases of real text and were made verbatim, with the category unchanged. Every term was answered exactly once, and no em dashes, en dashes or section signs are used.

## Limits

- No person has reviewed it. None of us is a pharmacovigilance professional.
- The two passes are the same model, so their agreement shows consistency, not correctness.
- The reference is the label alone. A signal the label doesn't mention can still be well known (NAION with semaglutide, for example). Then the row stays `possible_new_signal`, which is right for this task.
