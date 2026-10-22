-- =============================================================================
-- Black Box spike: register openFDA FAERS count endpoints as Zetaris tables.
-- Design: docs/ideas/BLACK_BOX.md
--
-- Pattern copied from the Zetaris getting-started PokeAPI recipe
-- (open_data/rest_apis/sql/non_rate_limited/02_pokeapi_create.sql), which
-- works on this machine. Parts A and B both ran successfully on 22 Oct 2026
-- through the REST API, and B3 matched an independent Python calculation.
--
-- Run the whole file through the REST API (skips objects that already exist):
--   python -I scripts/zetaris/run_sql.py scripts/zetaris/openfda_baseline.sql
-- Or paste into the Zetaris SQL Editor, one statement at a time. Part A is
-- the baseline. Part B checks a search parameter in the URL and the
-- signal-score join.
--
-- Source: openFDA drug adverse event endpoint (FAERS), public, no key.
--   Terms:   https://open.fda.gov/terms/
--   License: https://open.fda.gov/license/
-- openFDA says: do not rely on it for medical decisions; treat results as
-- unvalidated.
--
-- Checked by curl on 22 Oct 2026 (data last_updated 2026-07-30):
--   * count queries return a flat array: {"meta": {...}, "results": [{"term", "count"}]}
--   * without an API key, count queries accept limit up to 999
--     (limit=1000 returns API_KEY_MISSING), so the baseline is the top 999
--     reactions only
--   * count=serious returns two rows (1 = serious, 2 = not serious); their
--     sum is a total in the same flat shape. It is about 0.05% below
--     meta.results.total because a few reports lack the serious field
--     (all reports: 20,682,701 vs 20,692,690; montelukast: 121,016 vs 121,068)
--
-- Never put an openFDA API key in this file. Without a key openFDA documents
-- roughly 240 requests/minute and 1,000/day per IP, so cache the tables.
-- =============================================================================


-- =============================================================================
-- Part A: baseline (go/no-go)
-- =============================================================================

-- A1. Lightning database for this source. The description allows only
-- letters, digits, spaces and _ . - , (parentheses are rejected).
CREATE LIGHTNING DATABASE OPENFDA_REST DESCRIBE BY "openFDA drug adverse event FAERS REST source";

-- A2. Schemastore container for the flattened views. Run once; skip on a
-- re-run if it already exists.
CREATE SCHEMASTORE CONTAINER openfda;

-- A3. Reports per reaction across all drugs (top 999).
CREATE LIGHTNING REST TABLE faers_reaction_totals_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

-- A4. Total reports, split by the serious flag.
CREATE LIGHTNING REST TABLE faers_total_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?count=serious",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

-- A5. Flatten the reaction counts.
CREATE SCHEMASTORE VIEW faers_reaction_totals WITH CONTAINER openfda AS
SELECT
    r.term AS reaction,
    r.`count` AS reports
FROM openfda_rest.faers_reaction_totals_raw
LATERAL VIEW explode(results) AS r;

-- A6. Flatten the totals.
CREATE SCHEMASTORE VIEW faers_total WITH CONTAINER openfda AS
SELECT
    r.term AS serious_flag,
    r.`count` AS reports
FROM openfda_rest.faers_total_raw
LATERAL VIEW explode(results) AS r;

-- A7. Cache so later queries do not refetch from openFDA. Syntax taken from
-- the Zetaris catalog notes; untested here. If it errors, carry on and note it.
CACHE TABLE openfda_rest.faers_reaction_totals_raw;
CACHE TABLE openfda_rest.faers_total_raw;

-- A8. Checks. Expected (as of 22 Oct): first query gives 999 rows starting
-- with DRUG INEFFECTIVE (about 1.3 million), OFF LABEL USE, DEATH. Second
-- gives about 20.68 million.
SELECT reaction, reports
FROM openfda.faers_reaction_totals
ORDER BY reports DESC
LIMIT 10;

SELECT SUM(reports) AS total_reports
FROM openfda.faers_total;


-- =============================================================================
-- Part B (optional): one drug, and the signal score
-- Tests a search filter inside the URL (%22 = double quote, %20 = space)
-- and a cross-table join in Zetaris.
-- =============================================================================

-- B1. Reactions reported with montelukast (top 999).
CREATE LIGHTNING REST TABLE faers_montelukast_reactions_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=patient.drug.openfda.generic_name.exact:%22MONTELUKAST%20SODIUM%22&count=patient.reaction.reactionmeddrapt.exact&limit=999",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

-- B2. Total montelukast reports, split by the serious flag.
CREATE LIGHTNING REST TABLE faers_montelukast_total_raw FROM OPENFDA_REST REQUEST(
    endpoint "https://api.fda.gov/drug/event.json?search=patient.drug.openfda.generic_name.exact:%22MONTELUKAST%20SODIUM%22&count=serious",
    method "get",
    response_type "json",
    http_encoding "URLENCODED"
) HEADER (
) BODY ();

CREATE SCHEMASTORE VIEW faers_montelukast_reactions WITH CONTAINER openfda AS
SELECT
    r.term AS reaction,
    r.`count` AS reports
FROM openfda_rest.faers_montelukast_reactions_raw
LATERAL VIEW explode(results) AS r;

CREATE SCHEMASTORE VIEW faers_montelukast_total WITH CONTAINER openfda AS
SELECT
    r.term AS serious_flag,
    r.`count` AS reports
FROM openfda_rest.faers_montelukast_total_raw
LATERAL VIEW explode(results) AS r;

CACHE TABLE openfda_rest.faers_montelukast_reactions_raw;
CACHE TABLE openfda_rest.faers_montelukast_total_raw;

-- B3. Signal score (PRR) for montelukast against the baseline.
--   a = drug and reaction, b = drug without reaction,
--   c = reaction without drug, d = neither.
-- Approximate: reports can list several reactions, and reactions outside the
-- baseline's top 999 drop out of the join. Expect neuropsychiatric terms
-- (e.g. NIGHTMARE, AGGRESSION) near the top if the montelukast signal shows.
SELECT
    dr.reaction,
    dr.reports AS a,
    dt.total - dr.reports AS b,
    rt.reports - dr.reports AS c,
    gt.total - dt.total - rt.reports + dr.reports AS d,
    ROUND(
        (dr.reports / dt.total)
        / ((rt.reports - dr.reports) / (gt.total - dt.total)),
        2
    ) AS prr
FROM openfda.faers_montelukast_reactions dr
JOIN openfda.faers_reaction_totals rt
  ON rt.reaction = dr.reaction
CROSS JOIN (SELECT SUM(reports) AS total FROM openfda.faers_montelukast_total) dt
CROSS JOIN (SELECT SUM(reports) AS total FROM openfda.faers_total) gt
WHERE dr.reports >= 3
ORDER BY prr DESC
LIMIT 25;


-- =============================================================================
-- Teardown (commented out). DROP VIEW is the only teardown the Zetaris recipe
-- calls reliable; remove REST tables and the database in Data Explorer.
-- =============================================================================

-- DROP VIEW openfda.faers_montelukast_total;
-- DROP VIEW openfda.faers_montelukast_reactions;
-- DROP VIEW openfda.faers_total;
-- DROP VIEW openfda.faers_reaction_totals;
