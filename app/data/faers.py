"""The Clerk: registers openFDA sources in Zetaris for a drug and answers evidence queries with SQL.
Not an LLM agent. All numbers the agents see come from these queries.

Shared baseline (scripts/zetaris/openfda_baseline.sql, Part A):
  openfda.faers_reaction_totals  reports per reaction, all drugs, top 999
  openfda.faers_total            all reports, split by the serious flag
Per drug, created at runtime:
  openfda_rest.faers_d2_<slug>_reactions_raw / openfda.faers_d2_<slug>_reactions
  openfda_rest.faers_d2_<slug>_total_raw     / openfda.faers_d2_<slug>_total
  openfda_rest.label_d_<slug>_raw           current label from drug/label
The d2 tables use drug_search() (two fields). The older faers_d_<slug> tables used generic_name alone; they
stay in Zetaris because REST tables cannot be dropped through SQL, so the new search needed new names.
"""
import json
import re
import urllib.parse

from app.adapters.zetaris import ZetarisClient, ZetarisError
from app.schemas import QueryResult, Signal

OPENFDA = "https://api.fda.gov/drug"
DRUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{1,48}$")
LABEL_FIELDS = ("boxed_warning", "warnings_and_cautions", "warnings", "precautions",
                "adverse_reactions", "contraindications", "indications_and_usage")


class DrugNotFound(RuntimeError):
    pass


def validate_drug(drug: str) -> str:
    """The drug name ends up in a URL and in table names, so only plain names are allowed."""
    drug = (drug or "").strip()
    if not DRUG_RE.match(drug):
        raise ValueError("drug must be 2-49 letters, digits, spaces or hyphens")
    return drug.lower()


def slug(drug: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", drug.lower()).strip("_")[:40]


def sql_str(value: str) -> str:
    """Spark SQL string literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def drug_search(drug: str) -> str:
    """openFDA search for the reports that name a drug: the harmonised generic name OR FDA's coded active
    substance, fully URL-encoded. openFDA fills generic_name only when it can match the reported product to a
    product record, and that often fails (on 23 Oct, atorvastatin: 249,606 reports by generic_name, 519,437
    by either field), which left many of the drug's reports among "all other drugs". Each field finds
    reports the other misses: generic_name catches brand-only reports, activesubstancename plainly named
    generics and non-US names. Found by Bryan against FDA's raw quarterly files."""
    expr = (f'(patient.drug.openfda.generic_name:"{drug}" OR '
            f'patient.drug.activesubstance.activesubstancename:"{drug}")')
    return urllib.parse.quote(expr, safe="")


def rest_table(name: str, endpoint: str) -> str:
    return (f'CREATE LIGHTNING REST TABLE {name} FROM OPENFDA_REST REQUEST(\n'
            f'    endpoint "{endpoint}",\n    method "get",\n    response_type "json",\n'
            f'    http_encoding "URLENCODED"\n) HEADER (\n) BODY ()')


def count_view(view: str, raw: str, term_alias: str) -> str:
    return (f"CREATE SCHEMASTORE VIEW {view} WITH CONTAINER openfda AS\n"
            f"SELECT r.term AS {term_alias}, r.`count` AS reports\n"
            f"FROM openfda_rest.{raw}\nLATERAL VIEW explode(results) AS r")


def signal_sql(s: str, reaction: str | None = None, min_a: int = 3) -> str:
    """2x2 disproportionality table per reaction: PRR and Yates-corrected chi-squared."""
    where = f"dr.reports >= {min_a}" + (f" AND dr.reaction = {sql_str(reaction)}" if reaction else "")
    return f"""SELECT reaction, a, b, c, d,
  ROUND((a / (a + b)) / (c / (c + d)), 2) AS prr,
  ROUND((a + b + c + d) * POWER(GREATEST(ABS(a * d - b * c) - (a + b + c + d) / 2, 0), 2)
        / ((a + b) * (c + d) * (a + c) * (b + d)), 1) AS chi2
FROM (
  SELECT dr.reaction,
    CAST(dr.reports AS DOUBLE) AS a,
    CAST(dt.total - dr.reports AS DOUBLE) AS b,
    CAST(rt.reports - dr.reports AS DOUBLE) AS c,
    CAST(gt.total - dt.total - rt.reports + dr.reports AS DOUBLE) AS d
  FROM openfda.faers_d2_{s}_reactions dr
  JOIN openfda.faers_reaction_totals rt ON rt.reaction = dr.reaction
  CROSS JOIN (SELECT SUM(reports) AS total FROM openfda.faers_d2_{s}_total) dt
  CROSS JOIN (SELECT SUM(reports) AS total FROM openfda.faers_total) gt
  WHERE {where}
) t
WHERE c > 0
ORDER BY prr DESC"""


def to_signal(rec: dict) -> Signal:
    return Signal(reaction=rec["reaction"], a=int(float(rec["a"])), b=int(float(rec["b"])),
                  c=int(float(rec["c"])), d=int(float(rec["d"])),
                  prr=float(rec["prr"]), chi2=float(rec["chi2"]))


class Clerk:
    def __init__(self, zetaris: ZetarisClient):
        self.z = zetaris

    def register_drug(self, drug: str) -> dict:
        """Create the per-drug REST tables and views if they do not exist yet."""
        s = slug(drug)
        q = urllib.parse.quote(f'"{drug}"')
        search = f"search={drug_search(drug)}"
        created = {
            "reactions_raw": self.z.ensure(rest_table(
                f"faers_d2_{s}_reactions_raw",
                f"{OPENFDA}/event.json?{search}&count=patient.reaction.reactionmeddrapt.exact&limit=999"),
                f"register FAERS reaction counts for {drug}"),
            "total_raw": self.z.ensure(rest_table(
                f"faers_d2_{s}_total_raw", f"{OPENFDA}/event.json?{search}&count=serious"),
                f"register FAERS report total for {drug}"),
            "label_raw": self.z.ensure(rest_table(
                f"label_d_{s}_raw", f"{OPENFDA}/label.json?search=openfda.generic_name:{q}&limit=1"),
                f"register current label for {drug}"),
            "reactions": self.z.ensure(count_view(f"faers_d2_{s}_reactions", f"faers_d2_{s}_reactions_raw", "reaction"),
                                       f"flatten reaction counts for {drug}"),
            "total": self.z.ensure(count_view(f"faers_d2_{s}_total", f"faers_d2_{s}_total_raw", "serious_flag"),
                                   f"flatten report total for {drug}"),
        }
        # Cache every run: CACHE TABLE is cheap once cached, and the cache does not survive a Zetaris restart.
        for raw in (f"faers_d2_{s}_reactions_raw", f"faers_d2_{s}_total_raw", f"label_d_{s}_raw"):
            self.z.run(f"CACHE TABLE openfda_rest.{raw}", f"cache {raw}", ddl=True)
        return created

    def totals(self, drug: str) -> dict:
        s = slug(drug)
        try:
            res = self.z.run(
                f"SELECT (SELECT SUM(reports) FROM openfda.faers_d2_{s}_total) AS drug_reports, "
                f"(SELECT SUM(reports) FROM openfda.faers_total) AS all_reports, "
                f"(SELECT meta.last_updated FROM openfda_rest.faers_total_raw) AS data_last_updated",
                f"report totals for {drug}")
        except ZetarisError as e:
            raise DrugNotFound(f"openFDA has no adverse event reports for '{drug}' ({e})") from e
        rec = res.records()[0]
        if not rec.get("drug_reports"):
            raise DrugNotFound(f"openFDA has no adverse event reports for '{drug}'")
        return {**rec, "query_id": res.query_id}

    def signals(self, drug: str) -> tuple[QueryResult, list[Signal]]:
        res = self.z.run(signal_sql(slug(drug)), f"disproportionality screen for {drug}")
        return res, [to_signal(r) for r in res.records()]

    def signal(self, drug: str, reaction: str, agent: str = "judge") -> tuple[QueryResult, Signal | None]:
        """Re-query one reaction, so the Judge checks numbers against Zetaris rather than the Hunter's copy."""
        res = self.z.run(signal_sql(slug(drug), reaction=reaction, min_a=1),
                         f"re-check {reaction} for {drug}", agent=agent)
        recs = res.records()
        return res, (to_signal(recs[0]) if recs else None)

    def label(self, drug: str) -> tuple[str | None, dict]:
        """Current label sections. Fields vary between labels (and DESCRIBE truncates long schemas),
        so fetch the whole label record as JSON and pick the sections present."""
        raw = f"openfda_rest.label_d_{slug(drug)}_raw"
        try:
            res = self.z.run(f"SELECT to_json(r) AS label FROM {raw} LATERAL VIEW explode(results) AS r",
                             f"label text for {drug}")
        except ZetarisError:
            return None, {}
        if not res.rows:
            return res.query_id, {}
        rec = json.loads(res.rows[0][0])
        out = {f: " ".join(rec[f]) for f in LABEL_FIELDS if rec.get(f)}
        out.update({k: rec[k] for k in ("effective_time", "set_id") if rec.get(k)})
        return res.query_id, out
