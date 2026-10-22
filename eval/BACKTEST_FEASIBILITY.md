# Can we build a backtest set? (checked 22 Oct 2026)

**Goal.** Run Black Box "as of" a past date and test whether it would have flagged a reaction before the label added it.

## FDA Drug Safety-related Labeling Changes (SrLC) database

- It covers safety labeling changes from January 2016 onward. For each change you can search by drug and date range, and see the label section that changed (boxed warning, contraindications, warnings and precautions, adverse reactions and so on).
- **It cannot feed an automated set.** The page offers no bulk download, no export and no API. A scripted request from this machine returned FDA's "excessive requests" bot page on the first try.
- It is still useful **by hand**: a person can look up a few changes in a browser and record them as cited facts.

## DailyMed (NLM): workable

- `GET https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}/history.json` lists the published versions of a label. Tested: works.
- `GET .../spls/{setid}.xml` returns the full label text (XML only; the `.json` form returned nothing). Tested: works.
- **Repackager labels act as dated snapshots.** Many repackagers stopped updating, so their last version freezes the label as it was. Example: a Physicians Total Care Singulair (montelukast) label, last published 21 Feb 2012.
- So a past label can be compared with today's label. Reactions in today's label but missing from the old one were added in between. They become the ground truth for a backtest.

## What we learned about montelukast

The 2012 snapshot already mentions neuropsychiatric events, suicidality, aggression and dream abnormalities in its precautions. It has no boxed warning. The March 2020 change (date to confirm on FDA's site) **upgraded an existing warning to a boxed warning**. It did not add a new reaction. **Montelukast is therefore not a clean "caught it early" example** for the demo, and we should not present it that way.

## How a backtest would work (not built)

1. **Pick drug and date.** For a drug, pick a frozen snapshot label from DailyMed with publication date D.
2. **Ground truth.** Diff the snapshot against the current label: reactions named now but not at D are positives.
3. **As-of statistics.** Recompute the screen with reports received before D. openFDA supports `receivedate:[20040101 TO D]` in `search`, so this is one more Zetaris REST table per drug and date.
4. **Run as of D.** Run the agents with the snapshot label and the as-of screen.
5. **Measure.** The share of positives the agents flag as `possible_new_signal` (recall), and how many flags are not positives (precision against a later label).

**Effort:** about a day. **Risks:**
- DailyMed returns XML, and the Zetaris REST tables we use expect JSON, so the label diff would run outside Zetaris. That is acceptable for evaluation tooling, but it is not product data.
- Label wording changes make the diff noisy, so it needs the same synonym care as the gold set.
- openFDA FAERS coverage before 2004 is thin.
