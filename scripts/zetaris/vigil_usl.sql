-- =============================================================================
-- Vigil USL: three public sources, one Unified Semantic Layer, two DQ rules.
-- Written 27 Oct 2026 for the Zetaris evaluation criteria (1a to 1c). Write-up
-- and results: docs/ZETARIS_USL.md.
--
-- Standalone. The app does not read this USL: Vigil's agents query the
-- SchemaStore views that app/data/faers.py registers at runtime. This file
-- builds the same data as a USL for three drugs (the three recorded sample
-- runs: montelukast, isotretinoin, metformin), adds a third source, and
-- shows the USL lifecycle and its DQ rules on it.
--
-- Prerequisite: Part A of scripts/zetaris/openfda_baseline.sql (the
-- OPENFDA_REST database, the openfda container and the two all-drug tables).
--
-- Run the whole file through the REST API (re-runs skip what exists):
--   python -I scripts/zetaris/run_sql.py scripts/zetaris/vigil_usl.sql
-- Or one part at a time with --start-at "PART 2:" --stop-before "PART 3:".
-- The multi-table COMPILE USL holds semicolons, so it sits between
-- "begin one statement" / "end one statement" markers and run_sql.py sends it
-- whole. The SQL Editor splits it, per the Zetaris getting-started notes; use
-- the REST runner, JDBC or the USL > New USL screen for that statement.
--
-- Syntax follows the Zetaris getting-started USL package
-- (open_data/usl/sql/02_sic_edgar_usl_create.sql) and the SQL companion,
-- section 8. The whole file ran through the REST API on 27 Oct 2026
-- (results in docs/ZETARIS_USL.md, "First run"). That run confirmed bigint
-- and boolean column types in USL DDL, and ACTIVATE over a UNION ALL of
-- explode()-based REST tables.
--
-- Sources (all public, aggregate or reference data, no key):
--   1. openFDA drug adverse event API (FAERS)   https://open.fda.gov/apis/drug/event/
--   2. openFDA drug label API (SPL)             https://open.fda.gov/apis/drug/label/
--   3. NLM RxNav RxClass API (ATC classes)      https://lhncbc.nlm.nih.gov/RxNav/APIs/RxClassAPIs.html
-- openFDA terms: https://open.fda.gov/terms/ . RxNav terms:
-- https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html . openFDA says not to
-- rely on it for medical decisions.
-- =============================================================================


-- =============================================================================
-- PART 1: onboard the sources (criterion 1b)
-- =============================================================================

-- 1.1 openFDA FAERS and labels. The table names and URLs are exactly the ones
-- app/data/faers.py register_drug() creates, so on a machine that has run
-- these drugs every CREATE is a SKIP, and on a fresh one the app later finds
-- them already there.

CREATE LIGHTNING REST TABLE faers_d2_montelukast_reactions_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22montelukast%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22montelukast%22%29&count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE faers_d2_montelukast_total_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22montelukast%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22montelukast%22%29&count=serious",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE label_d2_montelukast_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22montelukast%22&sort=effective_time:desc&limit=10",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

CREATE LIGHTNING REST TABLE faers_d2_isotretinoin_reactions_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22isotretinoin%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22isotretinoin%22%29&count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE faers_d2_isotretinoin_total_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22isotretinoin%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22isotretinoin%22%29&count=serious",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE label_d2_isotretinoin_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22isotretinoin%22&sort=effective_time:desc&limit=10",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

CREATE LIGHTNING REST TABLE faers_d2_metformin_reactions_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22metformin%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22metformin%22%29&count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE faers_d2_metformin_total_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=%28patient.drug.openfda.generic_name%3A%22metformin%22%20OR%20patient.drug.activesubstance.activesubstancename%3A%22metformin%22%29&count=serious",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE label_d2_metformin_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22metformin%22&sort=effective_time:desc&limit=10",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

-- 1.2 NLM RxNav: the ATC drug classes for each drug. A second provider, so it
-- gets its own Lightning database. The response is
-- {"rxclassDrugInfoList": {"rxclassDrugInfo": [{"minConcept": {rxcui, name,
-- tty}, "rxclassMinConceptItem": {classId, className, classType}, ...}]}}.
-- tty IN is the ingredient itself; MIN rows are combination products
-- (checked by curl on 27 Oct: metformin has 1 IN row and 13 MIN rows,
-- isotretinoin 2 IN rows, montelukast 1).
CREATE LIGHTNING DATABASE RXNAV_REST DESCRIBE BY "NLM RxNav RxClass REST source";

CREATE LIGHTNING REST TABLE rxclass_montelukast_raw FROM RXNAV_REST REQUEST(
    endpoint "https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName=montelukast&relaSource=ATC",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE rxclass_isotretinoin_raw FROM RXNAV_REST REQUEST(
    endpoint "https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName=isotretinoin&relaSource=ATC",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();
CREATE LIGHTNING REST TABLE rxclass_metformin_raw FROM RXNAV_REST REQUEST(
    endpoint "https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName=metformin&relaSource=ATC",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

-- 1.3 Cache, so the queries below do not refetch from the providers.
CACHE TABLE openfda_rest.faers_d2_montelukast_reactions_raw;
CACHE TABLE openfda_rest.faers_d2_montelukast_total_raw;
CACHE TABLE openfda_rest.label_d2_montelukast_raw;
CACHE TABLE openfda_rest.faers_d2_isotretinoin_reactions_raw;
CACHE TABLE openfda_rest.faers_d2_isotretinoin_total_raw;
CACHE TABLE openfda_rest.label_d2_isotretinoin_raw;
CACHE TABLE openfda_rest.faers_d2_metformin_reactions_raw;
CACHE TABLE openfda_rest.faers_d2_metformin_total_raw;
CACHE TABLE openfda_rest.label_d2_metformin_raw;
CACHE TABLE rxnav_rest.rxclass_montelukast_raw;
CACHE TABLE rxnav_rest.rxclass_isotretinoin_raw;
CACHE TABLE rxnav_rest.rxclass_metformin_raw;


-- =============================================================================
-- PART 2: exploratory queries, three per source (criterion 1b)
-- =============================================================================

-- FAERS 1. The ten most reported reactions across all drugs. Expect DRUG
-- INEFFECTIVE first, about 1.3 million reports.
SELECT reaction, reports
FROM openfda.faers_reaction_totals
ORDER BY reports DESC
LIMIT 10;

-- FAERS 2. Montelukast reports, and the share marked serious (serious flag 1).
-- On 27 Oct openFDA gave 176,707 reports for this search.
SELECT SUM(r.`count`) AS reports,
       ROUND(SUM(CASE WHEN r.term = 1 THEN r.`count` ELSE 0 END) / SUM(r.`count`), 3) AS serious_share
FROM openfda_rest.faers_d2_montelukast_total_raw
LATERAL VIEW explode(results) AS r;

-- FAERS 3. How many of montelukast's 999 most reported reactions are missing
-- from the all-drug top 999. The screen's inner join drops these, so they
-- can never be screened. The hand-coded check found 212 on 27 Oct.
SELECT COUNT(*) AS drug_reactions,
       SUM(CASE WHEN t.reaction IS NULL THEN 1 ELSE 0 END) AS outside_all_drug_top_999
FROM (SELECT r.term AS reaction
      FROM openfda_rest.faers_d2_montelukast_reactions_raw
      LATERAL VIEW explode(results) AS r) d
LEFT JOIN openfda.faers_reaction_totals t ON t.reaction = d.reaction;

-- Labels 1. The ten newest metformin labels: which are single-ingredient
-- prescription labels. On 27 Oct, 2 of the 10 were pioglitazone combinations.
SELECT r.set_id, r.effective_time,
       concat_ws(', ', r.openfda.product_type) AS product_type,
       concat_ws(', ', r.openfda.generic_name) AS generic_name
FROM openfda_rest.label_d2_metformin_raw
LATERAL VIEW explode(results) AS r
ORDER BY r.effective_time DESC;

-- Labels 2. Per drug, how many of the ten candidates carry a boxed warning.
SELECT 'montelukast' AS drug, COUNT(*) AS labels,
       SUM(CASE WHEN r.boxed_warning IS NOT NULL THEN 1 ELSE 0 END) AS with_boxed_warning
FROM openfda_rest.label_d2_montelukast_raw LATERAL VIEW explode(results) AS r
UNION ALL
SELECT 'isotretinoin', COUNT(*), SUM(CASE WHEN r.boxed_warning IS NOT NULL THEN 1 ELSE 0 END)
FROM openfda_rest.label_d2_isotretinoin_raw LATERAL VIEW explode(results) AS r
UNION ALL
SELECT 'metformin', COUNT(*), SUM(CASE WHEN r.boxed_warning IS NOT NULL THEN 1 ELSE 0 END)
FROM openfda_rest.label_d2_metformin_raw LATERAL VIEW explode(results) AS r;

-- Labels 3. Does each montelukast label's boxed warning name the
-- neuropsychiatric events added in 2020?
SELECT r.set_id, r.effective_time,
       instr(lower(concat_ws(' ', r.boxed_warning)), 'neuropsychiatric') > 0 AS names_neuropsychiatric
FROM openfda_rest.label_d2_montelukast_raw
LATERAL VIEW explode(results) AS r
ORDER BY r.effective_time DESC;

-- RxNav 1. Every ATC class RxNav links to metformin, ingredient and
-- combination rows alike.
SELECT i.minConcept.tty AS tty, i.minConcept.name AS concept,
       i.rxclassMinConceptItem.classId AS atc_class_id, i.rxclassMinConceptItem.className AS atc_class_name
FROM rxnav_rest.rxclass_metformin_raw
LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
ORDER BY tty, concept;

-- RxNav 2. Ingredient rows against combination rows, per drug. Many
-- combination products are one reason Vigil reports a combination share.
SELECT 'montelukast' AS drug, SUM(CASE WHEN i.minConcept.tty = 'IN' THEN 1 ELSE 0 END) AS ingredient_rows,
       SUM(CASE WHEN i.minConcept.tty = 'MIN' THEN 1 ELSE 0 END) AS combination_rows
FROM rxnav_rest.rxclass_montelukast_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
UNION ALL
SELECT 'isotretinoin', SUM(CASE WHEN i.minConcept.tty = 'IN' THEN 1 ELSE 0 END),
       SUM(CASE WHEN i.minConcept.tty = 'MIN' THEN 1 ELSE 0 END)
FROM rxnav_rest.rxclass_isotretinoin_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
UNION ALL
SELECT 'metformin', SUM(CASE WHEN i.minConcept.tty = 'IN' THEN 1 ELSE 0 END),
       SUM(CASE WHEN i.minConcept.tty = 'MIN' THEN 1 ELSE 0 END)
FROM rxnav_rest.rxclass_metformin_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i;

-- RxNav 3. The RxNorm ID and ATC class of each ingredient itself.
SELECT 'isotretinoin' AS drug, i.minConcept.rxcui AS rxcui,
       i.rxclassMinConceptItem.classId AS atc_class_id, i.rxclassMinConceptItem.className AS atc_class_name
FROM rxnav_rest.rxclass_isotretinoin_raw
LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
WHERE i.minConcept.tty = 'IN';


-- =============================================================================
-- PART 3: the USL (criterion 1c)
-- Five tables. drug_reaction and drug_class and drug_label hang off
-- drug_summary by drug; drug_reaction also references reaction_all_drugs.
-- Each foreign key generates a DQ rule. The reaction key is the one that
-- matters: it marks every drug reaction the PRR screen cannot see because it
-- is outside the all-drug top 999 (FAERS 3 above).
-- =============================================================================

CREATE NAMESPACE IF NOT EXISTS lightning.metastore;
CREATE NAMESPACE IF NOT EXISTS lightning.metastore.vigil;

-- begin one statement
COMPILE USL IF NOT EXISTS vigil_usl DEPLOY NAMESPACE lightning.metastore.vigil DDL
CREATE TABLE drug_summary (
    drug varchar(50) NOT NULL PRIMARY KEY,
    reports bigint NOT NULL
);
CREATE TABLE reaction_all_drugs (
    reaction varchar(200) NOT NULL PRIMARY KEY,
    reports bigint NOT NULL
);
CREATE TABLE drug_reaction (
    drug varchar(50) NOT NULL FOREIGN KEY REFERENCES drug_summary(drug),
    reaction varchar(200) NOT NULL FOREIGN KEY REFERENCES reaction_all_drugs(reaction),
    reports bigint NOT NULL
);
CREATE TABLE drug_class (
    drug varchar(50) NOT NULL FOREIGN KEY REFERENCES drug_summary(drug),
    rxcui varchar(20),
    atc_class_id varchar(10),
    atc_class_name varchar(200)
);
CREATE TABLE drug_label (
    set_id varchar(64) NOT NULL PRIMARY KEY,
    drug varchar(50) NOT NULL FOREIGN KEY REFERENCES drug_summary(drug),
    effective_time varchar(8),
    product_type varchar(200),
    generic_name varchar(500),
    has_boxed_warning boolean
);
-- end one statement

UPDATE USL lightning.metastore.vigil.vigil_usl SET DESCRIPTION 'Vigil drug safety model - openFDA FAERS report counts, openFDA labels and NLM RxNav ATC classes for three drugs.';
UPDATE USL lightning.metastore.vigil.vigil_usl.drug_summary SET TABLE DESCRIPTION 'One row per drug - FAERS reports naming it as generic name or active substance.';
UPDATE USL lightning.metastore.vigil.vigil_usl.reaction_all_drugs SET TABLE DESCRIPTION 'FAERS reports per reaction across all drugs - openFDA top 999 only.';
UPDATE USL lightning.metastore.vigil.vigil_usl.drug_reaction SET TABLE DESCRIPTION 'FAERS reports per drug and reaction - the drug top 999.';
UPDATE USL lightning.metastore.vigil.vigil_usl.drug_class SET TABLE DESCRIPTION 'ATC classes of the ingredient from NLM RxNav - tty IN rows only.';
UPDATE USL lightning.metastore.vigil.vigil_usl.drug_label SET TABLE DESCRIPTION 'The ten newest openFDA labels per drug - the candidates Vigil chooses from.';

-- Referenced tables first. ACTIVATE checks nullability against the DDL: a
-- NOT NULL column needs a SELECT that cannot return null, so those columns
-- are wrapped in COALESCE, as Zetaris's own error message suggests (checked
-- 27 Oct). openFDA count lists have no null terms or counts, so no row
-- changes.
ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.drug_summary AS
SELECT drug, COALESCE(reports, 0) AS reports FROM (
  SELECT 'montelukast' AS drug, CAST(SUM(r.`count`) AS BIGINT) AS reports
  FROM openfda_rest.faers_d2_montelukast_total_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT 'isotretinoin', CAST(SUM(r.`count`) AS BIGINT)
  FROM openfda_rest.faers_d2_isotretinoin_total_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT 'metformin', CAST(SUM(r.`count`) AS BIGINT)
  FROM openfda_rest.faers_d2_metformin_total_raw LATERAL VIEW explode(results) AS r
) t;

ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.reaction_all_drugs AS
SELECT COALESCE(r.term, '') AS reaction, COALESCE(CAST(r.`count` AS BIGINT), 0) AS reports
FROM openfda_rest.faers_reaction_totals_raw
LATERAL VIEW explode(results) AS r;

ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.drug_reaction AS
SELECT drug, COALESCE(reaction, '') AS reaction, COALESCE(reports, 0) AS reports FROM (
  SELECT 'montelukast' AS drug, r.term AS reaction, CAST(r.`count` AS BIGINT) AS reports
  FROM openfda_rest.faers_d2_montelukast_reactions_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT 'isotretinoin', r.term, CAST(r.`count` AS BIGINT)
  FROM openfda_rest.faers_d2_isotretinoin_reactions_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT 'metformin', r.term, CAST(r.`count` AS BIGINT)
  FROM openfda_rest.faers_d2_metformin_reactions_raw LATERAL VIEW explode(results) AS r
) t;

ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.drug_class AS
SELECT 'montelukast' AS drug, i.minConcept.rxcui AS rxcui,
       i.rxclassMinConceptItem.classId AS atc_class_id, i.rxclassMinConceptItem.className AS atc_class_name
FROM rxnav_rest.rxclass_montelukast_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
WHERE i.minConcept.tty = 'IN'
UNION ALL
SELECT 'isotretinoin', i.minConcept.rxcui, i.rxclassMinConceptItem.classId, i.rxclassMinConceptItem.className
FROM rxnav_rest.rxclass_isotretinoin_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
WHERE i.minConcept.tty = 'IN'
UNION ALL
SELECT 'metformin', i.minConcept.rxcui, i.rxclassMinConceptItem.classId, i.rxclassMinConceptItem.className
FROM rxnav_rest.rxclass_metformin_raw LATERAL VIEW explode(rxclassDrugInfoList.rxclassDrugInfo) AS i
WHERE i.minConcept.tty = 'IN';

ACTIVATE USL TABLE lightning.metastore.vigil.vigil_usl.drug_label AS
SELECT COALESCE(set_id, '') AS set_id, drug, effective_time, product_type, generic_name, has_boxed_warning FROM (
  SELECT r.set_id AS set_id, 'montelukast' AS drug, r.effective_time AS effective_time,
         concat_ws(', ', r.openfda.product_type) AS product_type,
         concat_ws(', ', r.openfda.generic_name) AS generic_name,
         r.boxed_warning IS NOT NULL AS has_boxed_warning
  FROM openfda_rest.label_d2_montelukast_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT r.set_id, 'isotretinoin', r.effective_time, concat_ws(', ', r.openfda.product_type),
         concat_ws(', ', r.openfda.generic_name), r.boxed_warning IS NOT NULL
  FROM openfda_rest.label_d2_isotretinoin_raw LATERAL VIEW explode(results) AS r
  UNION ALL
  SELECT r.set_id, 'metformin', r.effective_time, concat_ws(', ', r.openfda.product_type),
         concat_ws(', ', r.openfda.generic_name), r.boxed_warning IS NOT NULL
  FROM openfda_rest.label_d2_metformin_raw LATERAL VIEW explode(results) AS r
) t;


-- =============================================================================
-- PART 4: show the USL is active (criterion 1c)
-- =============================================================================

-- USL 1. Rows per table. Expect 3 drugs, 999 all-drug reactions, up to 2,997
-- drug reactions, 4 class rows (isotretinoin has two) and up to 30 labels.
SELECT 'drug_summary' AS usl_table, COUNT(*) AS row_count FROM lightning.metastore.vigil.vigil_usl.drug_summary
UNION ALL SELECT 'reaction_all_drugs', COUNT(*) FROM lightning.metastore.vigil.vigil_usl.reaction_all_drugs
UNION ALL SELECT 'drug_reaction', COUNT(*) FROM lightning.metastore.vigil.vigil_usl.drug_reaction
UNION ALL SELECT 'drug_class', COUNT(*) FROM lightning.metastore.vigil.vigil_usl.drug_class
UNION ALL SELECT 'drug_label', COUNT(*) FROM lightning.metastore.vigil.vigil_usl.drug_label;

-- USL 2. Vigil's screen, written against the USL: PRR and Yates chi-squared
-- per drug and reaction (the same formula as signal_sql() in
-- app/data/faers.py), with the drug's ATC class from RxNav. The all-report
-- total still comes from the baseline view openfda.faers_total, so this query
-- also joins the USL to a SchemaStore view. Ten strongest per drug by PRR.
SELECT drug, atc_class_name, reaction, a, prr, chi2 FROM (
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY drug ORDER BY prr DESC) AS rank_in_drug FROM (
    SELECT dr.drug, dc.atc_class_name, dr.reaction, dr.reports AS a,
      ROUND((CAST(dr.reports AS DOUBLE) / ds.reports)
            / (CAST(ra.reports - dr.reports AS DOUBLE) / (gt.total - ds.reports)), 2) AS prr,
      ROUND(CAST(gt.total AS DOUBLE)
            * POWER(GREATEST(ABS(CAST(dr.reports AS DOUBLE) * (gt.total - ds.reports - ra.reports + dr.reports)
                                 - CAST(ds.reports - dr.reports AS DOUBLE) * (ra.reports - dr.reports))
                             - gt.total / 2, 0), 2)
            / (CAST(ds.reports AS DOUBLE) * (gt.total - ds.reports) * ra.reports * (gt.total - ra.reports)), 1) AS chi2
    FROM lightning.metastore.vigil.vigil_usl.drug_reaction dr
    JOIN lightning.metastore.vigil.vigil_usl.drug_summary ds ON ds.drug = dr.drug
    JOIN lightning.metastore.vigil.vigil_usl.reaction_all_drugs ra ON ra.reaction = dr.reaction
    LEFT JOIN (SELECT drug, MIN(atc_class_name) AS atc_class_name
               FROM lightning.metastore.vigil.vigil_usl.drug_class GROUP BY drug) dc ON dc.drug = dr.drug
    CROSS JOIN (SELECT SUM(reports) AS total FROM openfda.faers_total) gt
    WHERE dr.reports >= 3 AND ra.reports > dr.reports
  ) t
) ranked
WHERE rank_in_drug <= 10
ORDER BY drug, prr DESC;

-- USL 3. The label Vigil's choose_label() rule would pick for each drug: the
-- newest single-ingredient prescription label.
SELECT drug, set_id, effective_time, generic_name, has_boxed_warning FROM (
  SELECT l.*, ROW_NUMBER() OVER (PARTITION BY drug ORDER BY effective_time DESC) AS newest
  FROM lightning.metastore.vigil.vigil_usl.drug_label l
  WHERE product_type = 'HUMAN PRESCRIPTION DRUG' AND generic_name NOT LIKE '% AND %'
) t
WHERE newest = 1;


-- =============================================================================
-- PART 5: data quality rules (criterion 1c)
-- Rule 1 comes from the foreign key on drug_reaction.reaction. Rule 2 is a
-- custom row rule: a label is usable only if it is a single-ingredient
-- prescription label, the rule app/data/faers.py choose_label() applies in
-- Python. Constraint rules are named after their column (Zetaris notes,
-- section 8.6), so check LIST DQ before the SHOW statements.
-- =============================================================================

REGISTER DQ rx_single_ingredient TABLE lightning.metastore.vigil.vigil_usl.drug_label AS product_type = 'HUMAN PRESCRIPTION DRUG' AND generic_name NOT LIKE '% AND %';

LIST DQ USL lightning.metastore.vigil.vigil_usl;

-- Expect invalid records: the drug reactions outside the all-drug top 999
-- (212 for montelukast alone on 27 Oct), plus those of the other two drugs.
RUN DQ TABLE lightning.metastore.vigil.vigil_usl.drug_reaction;
SHOW DQ INVALID RECORD reaction TABLE lightning.metastore.vigil.vigil_usl.drug_reaction;

-- Expect invalid records: the combination labels among the candidates (2 of
-- metformin's 10 on 27 Oct).
RUN DQ TABLE lightning.metastore.vigil.vigil_usl.drug_label;
SHOW DQ ALL INVALID TABLE lightning.metastore.vigil.vigil_usl.drug_label;


-- =============================================================================
-- Teardown (commented out). REMOVE USL and DROP NAMESPACE worked on Zetaris
-- 2.4.3.1 per the Zetaris notes (section 8.4). Leave the REST tables: the
-- app uses them.
-- =============================================================================

-- REMOVE USL vigil_usl NAMESPACE lightning.metastore.vigil;
-- DROP NAMESPACE lightning.metastore.vigil;
