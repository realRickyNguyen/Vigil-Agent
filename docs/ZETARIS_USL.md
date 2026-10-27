# Vigil on Zetaris: the Unified Semantic Layer

This is our answer to the "Build with Zetaris" evaluation criteria. Part 1 (build a USL) points to the SQL and its results. Part 2 (reflect on the USL) is written out here.

Written 27 Oct 2026. Vigil's agents query Zetaris SchemaStore views that the app registers at runtime ([app/data/faers.py](../app/data/faers.py)); they do not read a USL. We built the USL afterwards, on 27 Oct, from the same tables plus a third source, so we could judge what the USL adds. Both are described below, and we say which one each number comes from.

| Criterion | Where |
|---|---|
| 1a Use case and data sources | [Use case and sources](#1a-use-case-and-sources), and [VIGIL.md](ideas/VIGIL.md) for the full design |
| 1b Onboard sources, 2 to 3 exploratory queries each | [scripts/zetaris/vigil_usl.sql](../scripts/zetaris/vigil_usl.sql), parts 1 and 2 (three queries per source) |
| 1c USL with its DDL, queries showing it active, a DQ rule running | [vigil_usl.sql](../scripts/zetaris/vigil_usl.sql), parts 3 to 5; results in [First run](#first-run-of-the-usl) |
| 2a Time saved against hand coding, with a hand-coded part compared | [2a](#2a-time-saved-against-a-hand-coded-approach), [scripts/zetaris/handcoded_prr.py](../scripts/zetaris/handcoded_prr.py) |
| 2b Would the USL help in our work | [2b](#2b-would-the-usl-help-in-our-work) |
| 2c A requirement to make the USL stronger | [2c](#2c-requirement-parameterised-rest-sources-for-the-usl) |

## 1a Use case and sources

A drug-safety analyst gets a drug name and has to decide which reported drug-reaction patterns deserve a closer look. Vigil registers that drug's public FDA data in Zetaris, computes a disproportionality screen (PRR with a Yates chi-squared) in SQL, and hands the strongest patterns to two Nemotron agents, which classify each one against the drug's label and challenge each other's findings. Every number an agent cites comes from a Zetaris query, and the Reviewer re-runs those queries before accepting a finding.

| # | Source | Provider | What it gives | Used by the app | In the USL |
|---|---|---|---|---|---|
| 1 | Drug adverse event API (FAERS) | openFDA | Report counts per reaction, for one drug and for all drugs; totals; co-reported drugs; reporter country and type | Yes, since 22 Oct | `drug_summary`, `reaction_all_drugs`, `drug_reaction` |
| 2 | Drug label API (SPL) | openFDA | The newest labels for the drug: sections, product type, generic names, boxed warning | Yes, since 22 Oct | `drug_label` |
| 3 | RxClass API | NLM RxNav | The drug's RxNorm ID and ATC classes | No, USL only (27 Oct) | `drug_class` |

All three are public and need no key. FAERS is used as aggregate counts only, so no case-level record reaches the app or the model.

## First run of the USL

Run on 27 Oct 2026 on our local Zetaris, through the REST API, with the baseline from [openfda_baseline.sql](../scripts/zetaris/openfda_baseline.sql) Part A already in place:

```
python -I scripts/zetaris/run_sql.py scripts/zetaris/vigil_usl.sql
```

All 57 statements succeeded after one fix, described below. The numbers are copied from the runner's output; openFDA data date 2026-07-30.

**Part 1, onboarding.** The nine openFDA tables already existed from earlier Vigil runs and were skipped. The RxNav database and its three tables were created. All twelve tables were cached.

**Part 2, exploratory queries.** All nine ran.

| Query | Result |
|---|---|
| FAERS 1, top reactions, all drugs | DRUG INEFFECTIVE 1,299,274; OFF LABEL USE 856,386; DEATH 849,903 |
| FAERS 2, montelukast reports | 176,707, of which 62.4% marked serious |
| FAERS 3, montelukast reactions outside the all-drug top 999 | 212 of 999 |
| Labels 1, metformin's ten newest labels | 8 single-ingredient, 2 pioglitazone and metformin combinations |
| Labels 2, labels with a boxed warning | 10 of 10 for each drug |
| Labels 3, montelukast boxed warning names neuropsychiatric events | 10 of 10 |
| RxNav 1, metformin's ATC classes | A10BA Biguanides for the ingredient, A10BD for 13 combinations |
| RxNav 2, ingredient and combination rows | montelukast 1 and 0, isotretinoin 2 and 0, metformin 1 and 13 |
| RxNav 3, isotretinoin's classes | RxCUI 6064: D10AD (topical retinoids) and D10BA (retinoids for acne) |

**Part 3, the USL.** `COMPILE USL` deployed all five tables, so `bigint` and `boolean` columns work in USL DDL. The first `ACTIVATE` failed:

> Schema mismatch for table 'lightning.metastore.vigil.vigil_usl.drug_summary'. Mismatched columns: Column 'reports': nullable -> NOT NULL

`ACTIVATE` checks nullability against the DDL, and a `SUM` or a field read from JSON can be null. Zetaris's error suggested `COALESCE(reports, 0)` and gave a corrected statement. We wrapped every `NOT NULL` column in `COALESCE`, as the Zetaris getting-started example does. openFDA count lists have no null terms or counts, so no row changed. After that all five tables activated, including the ones built from a `UNION ALL` over three `explode()` REST tables. A second `COMPILE USL IF NOT EXISTS` ran without error.

**Part 4, the USL in use.**

- **USL 1, rows per table:** `drug_summary` 3, `reaction_all_drugs` 999, `drug_reaction` 2,997, `drug_class` 4, `drug_label` 30.
- **USL 2, Vigil's screen over the USL:** top PRR per drug with its ATC class. Montelukast's top three were OBSTRUCTIVE AIRWAYS DISORDER (PRR 38.92), SPUTUM DISCOLOURED (25.69) and ASTHMA (23.94); metformin's was LACTIC ACIDOSIS (86.93); isotretinoin's was INFLAMMATORY BOWEL DISEASE (426.97). For montelukast's ten rows, the report count, PRR and chi-squared equal those from [handcoded_prr.py](../scripts/zetaris/handcoded_prr.py) run the same day, to every printed digit.
- **USL 3, the label each drug would get:** one single-ingredient prescription label per drug, each with a boxed warning (montelukast 20260804, isotretinoin 20260827, metformin 20260909).

Isotretinoin has two ATC classes. The query shows one class per drug, the alphabetically first, so its rows read "Retinoids for topical use in acne".

**Part 5, data quality.** `LIST DQ USL` showed eight rules: three primary keys and four foreign keys generated from the DDL, and our custom rule.

| Rule | Table | Records | Valid | Invalid |
|---|---|---|---|---|
| Foreign key `drug` | `drug_reaction` | 2,997 | 2,997 | 0 |
| Foreign key `reaction` | `drug_reaction` | 2,997 | 2,264 | **733** |
| Custom `rx_single_ingredient` | `drug_label` | 30 | 28 | **2** |
| Primary key `set_id` | `drug_label` | 30 | 30 | 0 |
| Foreign key `drug` | `drug_label` | 30 | 30 | 0 |

- **The 733 reactions** are each drug's reported reactions that are missing from the all-drug top 999: isotretinoin 363, montelukast 212, metformin 158. Vigil's PRR screen cannot see them, because its join needs both counts. Before this, that limit lived in the Python of the app's separate safety net ([app/data/safety_net.py](../app/data/safety_net.py)). `SHOW DQ INVALID RECORD` lists them, most reported first. For montelukast the list starts with RHINITIS ALLERGIC (1,061 reports). It also holds neuropsychiatric terms, the subject of montelukast's boxed warning, such as SLEEP TERROR (859), OBSESSIVE-COMPULSIVE DISORDER (453) and NEUROPSYCHIATRIC SYMPTOMS (289). A plain inner join drops these rows without saying so. The rule names them.
- **The 2 labels** are metformin's two pioglitazone and metformin combination labels. They are exactly the labels `choose_label()` in the app skips.

The montelukast count of 212 matches the hand-coded check, which found the same number from openFDA directly.

## 2a Time saved against a hand-coded approach

### The hand-coded part

[scripts/zetaris/handcoded_prr.py](../scripts/zetaris/handcoded_prr.py) does the screen without Zetaris. It fetches the same four openFDA count lists with `urllib`, joins them in Python dicts and computes the same 2×2 table, PRR and chi-squared as `signal_sql()`. It imports nothing from `app/`. It then compares its result with the Zetaris screen recorded in `samples/montelukast.json.gz` on 26 Oct.

Result for montelukast, run 27 Oct:

| | Hand-coded (27 Oct) | Zetaris (recorded 26 Oct) |
|---|---|---|
| Reactions screened | 787 | 787, the same set |
| Montelukast reports | 176,707 | 176,704 |
| All reports | 20,682,701 | 20,682,701 |
| Reaction counts that match | 677 of 787 | |
| Largest count difference | 2 reports | |
| Largest PRR difference | 0.02 | |
| Time for one drug | 10 to 12 s | |

openFDA gave the same data date (2026-07-30) on both days, but its montelukast total moved by 3 reports between the recording and this run. Three calls on 27 Oct all gave 176,707. The small count and PRR differences follow from that drift. With the same day's data the two agree exactly: the USL's screen on 27 Oct gave the same count, PRR and chi-squared as the hand-coded script for each of montelukast's ten strongest rows (see [First run](#first-run-of-the-usl)). On 22 Oct the first Zetaris screen had also matched a separate Python calculation ([VIGIL.md](ideas/VIGIL.md#signal-score-built)).

### What the comparison shows

For one fixed calculation, Zetaris saved us very little. The screen is about 20 lines of Python by hand (`screen()` in the script) and about 20 lines of SQL builder in `signal_sql()`, plus an 86-line REST client ([app/adapters/zetaris.py](../app/adapters/zetaris.py)) that does what the hand-coded fetch does. The time went elsewhere:

1. **Each new question was one SQL statement.** Between 23 and 25 Oct we added the Skeptic's co-reported drug checks, the report-source flags and the safety net. Each one registers an openFDA count as a table and asks its question in SQL against tables that already exist. By hand, each would have needed its own fetching, caching and joining code.
2. **Caching came with the tables.** `CACHE TABLE` keeps an openFDA response for every later query in the run, across all agents. Without an openFDA key we have about 1,000 calls a day, and the Reviewer re-queries every finding. By hand we would have had to write and test a response cache.
3. **The evidence trail came almost free.** Every statement goes through one client that writes the SQL, row count and a query ID to the trace. The Reviewer re-runs a finding's numbers against the same tables and rejects any number with no query ID behind it. A hand-coded version needs the same trail built around each fetch.
4. **The USL adds checks we had written in Python.** The foreign key rule on `drug_reaction.reaction` lists the reactions the screen cannot see, which the safety net works out in Python. The one-line `rx_single_ingredient` rule states part of what `choose_label()` and its helpers do in about 35 lines of Python. The USL does not replace either: the app still needs the result, not only the flag. It does make each check visible in Zetaris and runnable without our code.

Zetaris also cost us time, and the cost is the subject of 2c. Our view is that on the data layer it roughly broke even for this project: it saved time on items 1 to 3 and lost about as much to the workarounds in 2c. The saving would grow with more sources or more drugs, and the costs would not.

## 2b Would the USL help in our work

Our day-to-day work is biomedical research: public reference data and APIs joined to study data held on university HPC systems.

**Where it would help:**
- **Joining public reference APIs.** A lot of our time goes into code that fetches from a public API, flattens nested JSON, caches it and joins it to something else. Here, a REST table plus a USL activation query did that in SQL, and the declared schema says what each table holds. That suits projects that pull from several such APIs.
- **Stating data rules where others can see them.** A key or a `REGISTER DQ` rule says in one line what a reference table must satisfy, and `SHOW DQ ALL INVALID` lists the rows that break it. In research code those checks are often buried in a script and run only by its author.
- **Giving an agent one governed view.** For agent work like Vigil, a USL is a place to point the model that has types and descriptions and nothing else.

**Where it would not help, yet:**
- **Data on HPC file systems.** Our large datasets sit on HPC storage under data agreements. Zetaris cannot read files on a local disk (it needs object storage such as S3), and most of that data cannot be moved to a service outside the agreement.
- **Analysis.** Statistics and models still run in Python or R. A USL feeds them; it does not replace them.
- **Small one-off pulls.** For a single API and a single table, the setup costs more than a script.

**A project that would benefit (bonus).** A drug-class review: the same screen for every drug in an ATC class, such as all leukotriene receptor antagonists or all SGLT2 inhibitors, to see which signals are shared across the class and which belong to one drug. RxNav gives the class members, and FAERS and labels give the rest. With today's USL each added drug means four REST registrations and a new branch in four activation queries. Our forecast (not measured): about 30 minutes per drug by hand-written SQL, so a class of six drugs is three hours of SQL before any analysis. With the parameterised sources proposed in 2c, adding a drug becomes one row in `drug_summary`, and the class takes minutes. That forecast rests on the 2c feature existing.

## 2c Requirement: parameterised REST sources for the USL

*Written as a product requirement for Zetaris.*

### Problem

A Zetaris REST table has one fixed URL. Any app that asks about a user-supplied value, such as a drug, a company or a postcode, has to create a new REST table for each value at runtime, and a USL activated over those tables has to be edited for each value.

Evidence from Vigil's recorded montelukast run (26 Oct, [output_examples/montelukast](../output_examples/montelukast/)):
- The run sent 122 Zetaris statements. 78 were `CREATE LIGHTNING REST TABLE` statements for tables that already existed, which came back as "already exists" errors that our client catches.
- Each statement is a 2 to 2.5 s round trip even when the table already exists. Eight in a row took a median of 22 s, so we had to run them in parallel ([faers.py](../app/data/faers.py), `register_drug()`).
- The tables pile up: three per drug (`faers_d2_<drug>_reactions_raw`, `faers_d2_<drug>_total_raw`, `label_d2_<drug>_raw`) and one per Skeptic, safety-net or report-source query (`faers_q_<hash>`). The recipe we followed said only views can be dropped reliably in SQL, so the rest stay in the `openfda_rest` schema.
- When we changed the openFDA search on 23 Oct, every old table name was taken, so we had to give the new tables new names (`faers_d_` became `faers_d2_`).
- The USL in [vigil_usl.sql](../scripts/zetaris/vigil_usl.sql) holds three drugs. Adding a fourth means four new REST tables and a new `UNION ALL` branch in four activation queries.

### User story

As a developer building an agent on Zetaris, I want to declare a REST source once with named parameters and bind them when I query or activate a USL table, so that the agent can ask about any value without creating, naming or cleaning up a table per value.

### Requirements

1. **Parameters in the endpoint.** `CREATE LIGHTNING REST TABLE` accepts named, typed parameters that fill placeholders in the endpoint, with Zetaris doing the URL encoding.
2. **Binding at query time.** A query passes values as arguments, or by a lateral join from another table, so one statement can fetch for many values.
3. **USL activation over a parameterised source.** A USL table can be activated from one, with its parameters bound from another USL table (for example `drug_summary.drug`).
4. **Cache keyed by the resolved URL**, with a time-to-live, so repeated values do not refetch and the cache survives a restart. Today `CACHE TABLE` is per table and is lost on restart.
5. **Upstream HTTP status reported as such.** openFDA answers "no match" with a 404. Zetaris reports it as `HTTP 400: REST API call failed:` followed by a Java error, so our client parses the message to tell "no such drug" from a real failure. A 404 should come back as an empty result or a typed error with the upstream status.

### Acceptance criteria

- Vigil's per-drug registration step (3 tables, 2 views, 3 caches today) is replaced by zero DDL statements per drug.
- A run of montelukast sends no `CREATE` statements after the first run on an install.
- Adding a drug to `vigil_usl` is one row of data, with no change to any activation query.
- An upstream 404 gives a result the client can tell apart from an upstream 5xx without parsing text.

### Example of the proposed feature (bonus; proposed syntax, does not run)

```sql
-- Declared once per install.
CREATE LIGHTNING REST TABLE faers_reaction_counts FROM OPENFDA_REST
PARAMETERS (drug STRING)
REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=(patient.drug.openfda.generic_name:\"{drug}\" OR patient.drug.activesubstance.activesubstancename:\"{drug}\")&count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    cache_ttl "7 days",
    not_found "empty"
) HEADER () BODY ();

-- The USL table no longer names any drug. Adding a drug is a row in drug_summary.
ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.drug_reaction AS
SELECT d.drug, r.term AS reaction, CAST(r.`count` AS BIGINT) AS reports
FROM lightning.metastore.vigil.vigil_usl.drug_summary d,
     LATERAL openfda_rest.faers_reaction_counts(drug => d.drug)
     LATERAL VIEW explode(results) AS r;

-- An agent asks about one drug without any DDL.
SELECT r.term, r.`count`
FROM openfda_rest.faers_reaction_counts(drug => 'empagliflozin')
LATERAL VIEW explode(results) AS r;
```

The resulting `vigil_usl` keeps the same five tables and both DQ rules, but its activation queries no longer change when drugs are added.

### Other gaps we hit (smaller)

| Gap | What happened | Where |
|---|---|---|
| Two subqueries over one exploded view fail | `MISSING_ATTRIBUTES` when a query reads the same exploded REST view twice; we restructured to read each view once | [faers.py](../app/data/faers.py), `list_sizes_sql()` and `scope_sql()`, 25 Oct |
| No `IF NOT EXISTS` on REST tables | "already exists" comes back as an HTTP error, so every client needs a catch | [zetaris.py](../app/adapters/zetaris.py), `ensure()` |
| Cross-table DQ rules | We wanted `drug_reaction.reports <= reaction_all_drugs.reports`; the Zetaris notes say a rule correlated across tables is unconfirmed, so it stays a plain query | Zetaris getting-started SQL companion, section 8.6 |
| `DESCRIBE BY` text | Parentheses are rejected in a Lightning database description | [openfda_baseline.sql](../scripts/zetaris/openfda_baseline.sql), A1 |
