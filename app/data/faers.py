"""The Data Clerk: registers openFDA sources in Zetaris for a drug and answers evidence queries with SQL.
Not an LLM agent. All numbers the agents see come from these queries.

Shared baseline (scripts/zetaris/openfda_baseline.sql, Part A):
  openfda.faers_reaction_totals  reports per reaction, all drugs, top 999
  openfda.faers_total            all reports, split by the serious flag
Per drug, created at runtime:
  openfda_rest.faers_d2_<slug>_reactions_raw / openfda.faers_d2_<slug>_reactions
  openfda_rest.faers_d2_<slug>_total_raw     / openfda.faers_d2_<slug>_total
  openfda_rest.label_d2_<slug>_raw          the 10 newest labels for the drug; choose_label() picks one
For the Skeptic, created at runtime and shared across runs:
  openfda_rest.faers_q_<hash>               one openFDA count query each (co-reported drugs, pair counts)
The d2 tables use drug_search() (two fields). The older faers_d_<slug> tables used generic_name alone; they
stay in Zetaris because REST tables cannot be dropped through SQL, so the new search needed new names.
"""
import hashlib
import json
import re
import urllib.parse

from app.adapters.zetaris import ZetarisClient, ZetarisError
from app.data.label import INDICATION, NOT_COVERAGE, PATIENT, PHARMACOLOGY, SECTIONS, clinical_pharmacology_parts
from app.schemas import QueryResult, Signal

OPENFDA = "https://api.fda.gov/drug"
DRUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{1,48}$")
# The first seven are the sections the app has always read. Since 25 Oct also the patient labelling, the pharmacology
# and the sections that never count as coverage, so the code search can say where a reaction is named.
LABEL_FIELDS = tuple(dict.fromkeys(SECTIONS + (INDICATION,) + PATIENT + PHARMACOLOGY + NOT_COVERAGE))
# Both fields that name a co-drug, so the list matches what drug_search() finds.
CO_DRUG_FIELDS = ("patient.drug.openfda.generic_name.exact", "patient.drug.activesubstance.activesubstancename.exact")
REACTION_FIELD = "patient.reaction.reactionmeddrapt.exact"
SERIOUS_FLAGS = {"serious": "serious:1", "death": "seriousnessdeath:1"}
COUNT_LIMIT = 999  # openFDA's largest count list without a key
PAIR_COUNTS = ("n", "n_r", "n_x", "n_xr", "n_y", "n_yr", "n_xy", "n_xyr")


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


def phrase(field: str, value: str) -> str:
    """One openFDA search clause, fully URL-encoded, so the endpoint never holds a raw quote or apostrophe.
    Used for reactions; drugs and co-drugs go through drug_search() so they match the per-drug tables."""
    return f"{field}:" + urllib.parse.quote(f'"{value}"', safe="")


def count_view(view: str, raw: str, term_alias: str) -> str:
    return (f"CREATE SCHEMASTORE VIEW {view} WITH CONTAINER openfda AS\n"
            f"SELECT r.term AS {term_alias}, r.`count` AS reports\n"
            f"FROM openfda_rest.{raw}\nLATERAL VIEW explode(results) AS r")


def signal_sql(s: str, reaction: str | None = None, min_a: int = 3, reactions: list[str] | None = None) -> str:
    """2x2 disproportionality table per reaction: PRR and Yates-corrected chi-squared."""
    where = f"dr.reports >= {min_a}" + (f" AND dr.reaction = {sql_str(reaction)}" if reaction else "")
    if reactions:
        where += f" AND dr.reaction IN ({', '.join(sql_str(r) for r in reactions)})"
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


LABEL_CANDIDATES = 10


# Words that describe a dosage form, not an ingredient: "ATORVASTATIN CALCIUM, FILM COATED" is one ingredient.
FORM_WORDS = {"FILM", "COATED", "EXTENDED", "DELAYED", "MODIFIED", "IMMEDIATE", "RELEASE", "ORAL", "TABLET",
              "TABLETS", "CAPSULE", "CAPSULES", "SOLUTION", "SUSPENSION", "INJECTION", "CHEWABLE", "ORALLY",
              "DISINTEGRATING", "ER", "XR", "SR", "DR", "MG", "MCG", "ML", "USP", "KIT"}


def ingredient_parts(name: str) -> list[str]:
    """The parts of a product name that name ingredients. Combination names join them with AND, commas,
    slashes, or (in activesubstancename) backslashes."""
    parts = [p.strip() for p in re.split(r" AND |,|/|\\", name.upper())]
    return [p for p in parts if p and not all(w in FORM_WORDS or re.fullmatch(r"[\d.%]+", w) for w in p.split())]


def single_ingredient(name: str) -> bool:
    return len(ingredient_parts(name)) <= 1


def choose_label(records: list[dict]) -> tuple[dict, dict]:
    """Pick one label from candidates sorted newest first: a single-ingredient prescription label if there is
    one, else a single-ingredient label, else the newest. openFDA's first match used to win, which gave
    metformin the ZITUVIMET (sitagliptin + metformin) label and could give montelukast an old label without
    the 2020 boxed warning (15 of its 64 labels lack it). The rule names no drug."""
    def describe(r):
        o = r.get("openfda") or {}
        names = o.get("generic_name") or []
        return {"single": len(names) == 1 and single_ingredient(names[0]),
                "rx": "HUMAN PRESCRIPTION DRUG" in (o.get("product_type") or [])}
    tiers = [("single-ingredient prescription label", lambda d: d["single"] and d["rx"]),
             ("single-ingredient label", lambda d: d["single"]), ("newest label", lambda d: True)]
    for rule, ok in tiers:
        for r in records:
            if ok(describe(r)):
                o = r.get("openfda") or {}
                return r, {"rule": rule, "candidates": len(records), "set_id": r.get("set_id"),
                           "effective_time": r.get("effective_time"), "generic_name": o.get("generic_name"),
                           "brand_name": o.get("brand_name"), "product_type": o.get("product_type"),
                           "has_boxed_warning": bool(r.get("boxed_warning"))}


def seriousness_summary(records: list[dict]) -> dict:
    """{reaction: {"serious", "death", "serious_share", "death_share"}} from the seriousness() query rows."""
    def count(rec, k):
        if rec.get(k) is not None:
            return int(float(rec[k]))
        return None if int(float(rec.get(f"{k}_terms") or 0)) >= COUNT_LIMIT else 0

    out = {}
    for rec in records:
        a = int(float(rec["a"]))
        c = {k: count(rec, k) for k in SERIOUS_FLAGS}
        out[rec["reaction"]] = {**c, **{f"{k}_share": (round(v / a, 3) if v is not None and a else None)
                                        for k, v in c.items()}}
    return out


def combination_summary(rows: list[tuple[str, str, int]], drug: str, drug_reports: int) -> dict:
    """How many of the drug's reports name it inside a combination product, from (field, product name, reports)
    rows over the drug's reports. Bryan found this is 1% for atorvastatin but 46% for acetaminophen and 12% for
    metformin; a reaction can then belong to the partner drug (opioid dependence under acetaminophen). One report
    can name several products, and each field counts separately, so this takes the larger field's sum and is
    approximate."""
    word = re.compile(rf"\b{re.escape(drug.upper())}\b")
    by_field: dict[str, dict[str, int]] = {}
    for field, name, reports in rows:
        if word.search(name.upper()) and not single_ingredient(name):
            by_field.setdefault(field, {})[name] = by_field.get(field, {}).get(name, 0) + reports
    if not by_field:
        return {"share": 0.0, "reports": 0, "top_products": [], "partners": []}
    field, products = max(by_field.items(), key=lambda kv: sum(kv[1].values()))
    total = sum(products.values())
    partners: dict[str, int] = {}
    for name, reports in products.items():
        for part in ingredient_parts(name):
            if not word.search(part):
                partners[part] = partners.get(part, 0) + reports
    top = sorted(products.items(), key=lambda kv: -kv[1])[:5]
    return {"share": round(min(total / drug_reports, 1.0), 3) if drug_reports else 0.0, "reports": total,
            "field": field, "top_products": [{"name": n, "reports": r} for n, r in top],
            "partners": [p for p, _ in sorted(partners.items(), key=lambda kv: -kv[1])[:5]]}


class DataClerk:
    def __init__(self, zetaris: ZetarisClient):
        self.z = zetaris
        self.label_choice = None

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
                f"label_d2_{s}_raw", f"{OPENFDA}/label.json?search=openfda.generic_name:{q}"
                                     f"&sort=effective_time:desc&limit={LABEL_CANDIDATES}"),
                f"register the newest labels for {drug}"),
            "reactions": self.z.ensure(count_view(f"faers_d2_{s}_reactions", f"faers_d2_{s}_reactions_raw", "reaction"),
                                       f"flatten reaction counts for {drug}"),
            "total": self.z.ensure(count_view(f"faers_d2_{s}_total", f"faers_d2_{s}_total_raw", "serious_flag"),
                                   f"flatten report total for {drug}"),
        }
        # Cache every run: CACHE TABLE is cheap once cached, and the cache does not survive a Zetaris restart.
        for raw in (f"faers_d2_{s}_reactions_raw", f"faers_d2_{s}_total_raw", f"label_d2_{s}_raw"):
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

    def signal(self, drug: str, reaction: str, agent: str = "reviewer") -> tuple[QueryResult, Signal | None]:
        """Re-query one reaction, so the Reviewer checks numbers against Zetaris rather than the Analyst's copy."""
        res = self.z.run(signal_sql(slug(drug), reaction=reaction, min_a=1),
                         f"re-check {reaction} for {drug}", agent=agent)
        recs = res.records()
        return res, (to_signal(recs[0]) if recs else None)

    def recheck(self, drug: str, reactions: list[str], agent: str = "reviewer") -> tuple[QueryResult, dict]:
        """signal() for many reactions in one Zetaris query: {reaction: Signal}, absent if not in the screen.
        On 24 Oct twenty one-reaction re-checks took 3.5 to 4 minutes of a 6-minute review."""
        res = self.z.run(signal_sql(slug(drug), min_a=1, reactions=reactions),
                         f"re-check {len(reactions)} reactions for {drug}", agent=agent)
        return res, {s.reaction: s for s in map(to_signal, res.records())}

    def _count_table(self, search: str, count: str, purpose: str, limit: int | None = None) -> str:
        """A REST table for one openFDA count query, named by a hash of its URL so that runs and drugs
        asking the same question share one table (they cannot be deleted through SQL)."""
        url = f"{OPENFDA}/event.json?search={search}&count={count}" + (f"&limit={limit}" if limit else "")
        name = "faers_q_" + hashlib.sha1(url.encode()).hexdigest()[:12]
        self.z.ensure(rest_table(name, url), purpose)
        return name

    def combination_products(self, drug: str, drug_reports: int) -> tuple[QueryResult | None, dict | None]:
        """Product names across all of the drug's reports, by both name fields, summarised by
        combination_summary(). None if the query fails; the run goes on without it."""
        raws = [(field.split(".")[-2], self._count_table(drug_search(drug), field,
                                                         f"register product names ({field.split('.')[-2]}) for {drug}",
                                                         999)) for field in CO_DRUG_FIELDS]
        try:
            res = self.z.run(" UNION ALL ".join(f"SELECT '{f}' AS field, r.term AS product, r.`count` AS reports "
                                                f"FROM openfda_rest.{raw} LATERAL VIEW explode(results) AS r"
                                                for f, raw in raws), f"combination products for {drug}")
        except ZetarisError:
            return None, None
        rows = [(rec["field"], rec["product"], int(float(rec["reports"]))) for rec in res.records()]
        return res, combination_summary(rows, drug, int(float(drug_reports)))

    def seriousness(self, drug: str) -> tuple[QueryResult | None, dict]:
        """Per reaction: how many of this drug's reports naming it were flagged serious, and how many report a
        death. Two openFDA counts (the drug's reactions among serious reports, among death reports), joined to the
        reaction counts in Zetaris. The flags belong to the whole report, not to one reaction. Each list holds the
        999 most frequent reactions; a reaction missing from a full list is below its cutoff (None), from a
        shorter list it has none (0). Empty if the query fails; the run goes on without it."""
        s = slug(drug)
        raws = {k: self._count_table(f"{drug_search(drug)}+AND+{flag}", REACTION_FIELD,
                                     f"register {k} reaction counts for {drug}", 999)
                for k, flag in SERIOUS_FLAGS.items()}
        flat = {k: f"(SELECT r.term AS reaction, r.`count` AS reports FROM openfda_rest.{raw} "
                   f"LATERAL VIEW explode(results) AS r)" for k, raw in raws.items()}
        sql = (f"SELECT dr.reaction, dr.reports AS a, se.reports AS serious, de.reports AS death, "
               f"(SELECT COUNT(*) FROM {flat['serious']} x) AS serious_terms, "
               f"(SELECT COUNT(*) FROM {flat['death']} y) AS death_terms\n"
               f"FROM openfda.faers_d2_{s}_reactions dr\n"
               f"LEFT JOIN {flat['serious']} se ON se.reaction = dr.reaction\n"
               f"LEFT JOIN {flat['death']} de ON de.reaction = dr.reaction")
        try:
            res = self.z.run(sql, f"serious and fatal reports per reaction for {drug}")
        except ZetarisError:
            return None, {}
        return res, seriousness_summary(res.records())

    def co_drugs(self, drug: str, reaction: str, limit: int = 100) -> tuple[QueryResult, list[tuple[str, int]]]:
        """Drugs named on the reports of this drug and reaction, by exact generic name and by active substance.
        A report can appear under both fields, so the counts only rank candidates."""
        search = f"{drug_search(drug)}+AND+{phrase(REACTION_FIELD, reaction)}"
        raws = [self._count_table(search, field, f"register co-reported drugs ({field.split('.')[-2]}) for {drug} "
                                                 f"and {reaction}", limit) for field in CO_DRUG_FIELDS]
        res = self.z.run(" UNION ALL ".join(f"SELECT r.term AS drug, r.`count` AS reports FROM openfda_rest.{raw} "
                                            f"LATERAL VIEW explode(results) AS r" for raw in raws),
                         f"co-reported drugs for {drug} and {reaction}", agent="skeptic")
        return res, [(rec["drug"], int(float(rec["reports"]))) for rec in res.records()]

    def pair_counts(self, drug: str, reaction: str, co_drug: str) -> tuple[QueryResult, dict]:
        """The eight report counts behind the co-drug checks, in one query: all reports (n), the reaction (r),
        this drug (x), the co-drug (y), and their overlaps. Totals use the serious-flag sum like the screen."""
        x, y, r = drug_search(drug), drug_search(co_drug), phrase(REACTION_FIELD, reaction)
        searches = {"n_y": y, "n_yr": f"{y}+AND+{r}", "n_xy": f"{x}+AND+{y}", "n_xyr": f"{x}+AND+{y}+AND+{r}"}
        raws = {k: self._count_table(v, "serious", f"register {k} for {drug}, {co_drug}, {reaction}")
                for k, v in searches.items()}
        s, rq = slug(drug), sql_str(reaction)
        cols = [f"(SELECT SUM(reports) FROM openfda.faers_total) AS n",
                f"(SELECT SUM(reports) FROM openfda.faers_reaction_totals WHERE reaction = {rq}) AS n_r",
                f"(SELECT SUM(reports) FROM openfda.faers_d2_{s}_total) AS n_x",
                f"(SELECT SUM(reports) FROM openfda.faers_d2_{s}_reactions WHERE reaction = {rq}) AS n_xr"]
        cols += [f"(SELECT SUM(r.`count`) FROM openfda_rest.{raw} LATERAL VIEW explode(results) AS r) AS {k}"
                 for k, raw in raws.items()]
        res = self.z.run("SELECT " + ",\n       ".join(cols), f"report counts for {drug} with {co_drug}, {reaction}",
                         agent="skeptic")
        rec = res.records()[0]
        return res, {k: int(float(rec.get(k) or 0)) for k in PAIR_COUNTS}

    def label(self, drug: str) -> tuple[str | None, dict]:
        """Sections of the label choose_label() picks from the newest ones. Fields vary between labels (and
        DESCRIBE truncates long schemas), so fetch whole label records as JSON and pick the sections present.
        Which label was chosen, and why, is kept in self.label_choice for the trace and the dossier."""
        raw = f"openfda_rest.label_d2_{slug(drug)}_raw"
        self.label_choice = None
        try:
            res = self.z.run(f"SELECT to_json(r) AS label FROM {raw} LATERAL VIEW explode(results) AS r",
                             f"label text for {drug}")
        except ZetarisError:
            return None, {}
        if not res.rows:
            return res.query_id, {}
        rec, self.label_choice = choose_label([json.loads(row[0]) for row in res.rows])
        out = {f: " ".join(rec[f]) for f in LABEL_FIELDS if rec.get(f)}
        for k, v in clinical_pharmacology_parts(" ".join(rec.get("clinical_pharmacology") or [])).items():
            out.setdefault(k, v)  # only where openFDA did not split the section itself
        out.update({k: rec[k] for k in ("effective_time", "set_id") if rec.get(k)})
        return res.query_id, out
