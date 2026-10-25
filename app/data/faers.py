"""The Data Clerk: registers openFDA sources in Zetaris for a drug and answers evidence queries with SQL.
Not an LLM agent. All numbers the agents see come from these queries.

Shared baseline (scripts/zetaris/openfda_baseline.sql, Part A):
  openfda.faers_reaction_totals  reports per reaction, all drugs, top 999
  openfda.faers_total            all reports, split by the serious flag
Per drug, created at runtime:
  openfda_rest.faers_d2_<slug>_reactions_raw / openfda.faers_d2_<slug>_reactions
  openfda_rest.faers_d2_<slug>_total_raw     / openfda.faers_d2_<slug>_total
  openfda_rest.label_d2_<slug>_raw          the 10 newest labels for the drug; choose_label() picks one
For the Skeptic, report sources and the safety net, created at runtime and shared across runs:
  openfda_rest.faers_q_<hash>               one openFDA count query each (co-reported drugs, pair counts)
The d2 tables use drug_search() (two fields). The older faers_d_<slug> tables used generic_name alone; they
stay in Zetaris because REST tables cannot be dropped through SQL, so the new search needed new names.
"""
import hashlib
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from app.adapters.zetaris import ZetarisClient, ZetarisError
from app.data.label import (INDICATION, NOT_COVERAGE, PATIENT, PHARMACOLOGY, POPULATIONS, SECTIONS,
                            clinical_pharmacology_parts)
from app.data.safety_net import (DESIGNATED_MEDICAL_EVENTS, KIND_NAMES, PREGNANCY_NEWBORN, PREGNANCY_NEWBORN_WORDS,
                                 SCREEN_FLOOR)
from app.schemas import QueryResult, Signal

OPENFDA = "https://api.fda.gov/drug"
DRUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{1,48}$")
# The first seven are the sections the app has always read. Since 25 Oct also the patient labelling, the pharmacology,
# the pregnancy sections and the sections that never count as coverage, so the code search can say where a reaction
# is named.
LABEL_FIELDS = tuple(dict.fromkeys(SECTIONS + (INDICATION,) + PATIENT + PHARMACOLOGY + POPULATIONS + NOT_COVERAGE))
# Both fields that name a co-drug, so the list matches what drug_search() finds.
CO_DRUG_FIELDS = ("patient.drug.openfda.generic_name.exact", "patient.drug.activesubstance.activesubstancename.exact")
REACTION_FIELD = "patient.reaction.reactionmeddrapt.exact"
# The same reaction names split into words, for the safety net's word search.
REACTION_WORDS_FIELD = "patient.reaction.reactionmeddrapt"
# Longest openFDA URL the safety net registers as one REST table; longer term lists are split. On 25 Oct openFDA
# answered a 5,094-character URL, and Zetaris registered one of 3,887 characters (semaglutide, 45 terms).
URL_LIMIT = 4000
# Direct counts of designated medical events in one run, at most, re-counts included.
DIRECT_COUNTS = 4
# Report sources (app/data/sources.py). Counting by occurcountry needs .exact (plain fails with HTTP 500, checked
# 25 Oct); primarysource.qualification is a code, 1 to 5, and comes back as a number.
SOURCE_FIELDS = {"country": "occurcountry.exact", "reporter": "primarysource.qualification"}
SERIOUS_FLAGS = {"serious": "serious:1", "death": "seriousnessdeath:1"}
COUNT_LIMIT = 999  # openFDA's largest count list without a key
PAIR_COUNTS = ("n", "n_r", "n_x", "n_xr", "n_y", "n_yr", "n_xy", "n_xyr")


class DrugNotFound(RuntimeError):
    pass


class NoCurrentLabel(DrugNotFound):
    """openFDA has reports for the drug but no label under that generic name, so no reaction can be checked against
    one. A DrugNotFound, so the API answers it as one (404) without a change to app/server.py."""


# The hint when nothing names the drug. It never names a drug picked from the input, as a near spelling would be a
# guess.
SPELLING_HINT = "Check the spelling, and give the generic name (for example semaglutide, not Ozempic)."
# How openFDA's "no match" reaches the app. openFDA answers a search that matches nothing with a 404. Zetaris reports a
# failed openFDA call as "HTTP 400: REST API call failed: " and the Java error. For a 5xx that is "Server returned HTTP
# response code: 500 for URL ..." (seen in traces). Java's HttpURLConnection reports a 404 differently, as a
# FileNotFoundException carrying only the URL, so both that form and a plain "response code: 404" count.
NO_MATCH = re.compile(r"response code: 404\b|REST API call failed: (?:java\.io\.FileNotFoundException: )?https?://")


def no_match(e: Exception) -> bool:
    """True when a ZetarisError is openFDA saying no record matched, the same whether it came from creating a REST
    table or reading one. A 5xx is openFDA failing, not a missing drug, so it stays a ZetarisError."""
    return isinstance(e, ZetarisError) and NO_MATCH.search(str(e)) is not None


def runnable(name: str) -> bool:
    try:
        validate_drug(name)
        return True
    except ValueError:
        return False


def brand_hint(drug: str, generics: list[str]) -> str:
    """What to try instead, from DataClerk.brand_generics(). Vigil never swaps the name itself, so it says so, and it
    only says "run it again as" for a name it accepts. openFDA writes some generics with commas or over 49 characters
    (BICTEGRAVIR, EMTRICITABINE, AND TENOFOVIR ALAFENAMIDE)."""
    if not generics:
        return SPELLING_HINT
    quoted = lambda names: " or ".join(f"'{g.lower()}'" for g in names)  # noqa: E731
    ok = [g for g in generics if runnable(g)][:3]
    out = (f"openFDA's drug labels give '{drug}' as a brand name of {quoted((ok or generics)[:3])}. Vigil searches by "
           f"generic name and doesn't swap a brand for its generic itself")
    if ok:
        return out + f", so run it again as {quoted(ok)}."
    return out + (". That generic name has characters or a length Vigil doesn't accept, so this drug can't be run by "
                  "name yet.")


def validate_drug(drug: str) -> str:
    """The drug name ends up in a URL and in table names, so only plain names are allowed. Runs of spaces inside the
    name become one, as openFDA reads the words the same way and the table names already did (slug)."""
    drug = " ".join((drug or "").split())
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
    Used for reactions; drugs and co-drugs go through drug_search() so they match the per-drug tables.
    openFDA rejects the ^ that FAERS writes for an apostrophe ("Search not supported"), so a ^ name is searched as its
    words on the word-split field, as any_reaction() does (FOURNIER^S GANGRENE gave its 1,207 reports that way)."""
    if "^" in value and field == REACTION_FIELD:
        field, value = REACTION_WORDS_FIELD, value.replace("^", " ")
    return f"{field}:" + urllib.parse.quote(f'"{value}"', safe="")


def any_of(field: str, values: list[str]) -> str:
    """One openFDA clause matching any of the values in a field, fully URL-encoded like drug_search(), with the field
    repeated for each value."""
    return urllib.parse.quote("(" + " OR ".join(f'{field}:"{v}"' for v in values) + ")", safe="")


def any_reaction(names: list[str]) -> str:
    """One openFDA clause matching reports that name any of these reactions. openFDA rejects the ^ that FAERS writes
    for an apostrophe ("Search not supported") and finds nothing for the apostrophe itself, so such a name is searched
    as a phrase of its words on REACTION_WORDS_FIELD. Checked 25 Oct with empagliflozin, where FOURNIER S GANGRENE
    that way, counted by exact reaction, gave FOURNIER^S GANGRENE 1,207 reports, as in the drug's own list."""
    clauses = [f'{REACTION_FIELD}:"{n}"' if "^" not in n else f'{REACTION_WORDS_FIELD}:"{n.replace("^", " ")}"'
               for n in names]
    return urllib.parse.quote("(" + " OR ".join(clauses) + ")", safe="")


def count_url(search: str, count: str, limit: int | None = None) -> str:
    return f"{OPENFDA}/event.json?search={search}&count={count}" + (f"&limit={limit}" if limit else "")


def term_chunks(drug: str, names: list[str], limit: int = URL_LIMIT) -> list[list[str]]:
    """The reaction names in order, split so that each direct count's URL stays within `limit` characters."""
    out, chunk = [], []
    for n in names:
        if chunk and len(count_url(f"{drug_search(drug)}+AND+{any_reaction(chunk + [n])}", REACTION_FIELD,
                                   COUNT_LIMIT)) > limit:
            out.append(chunk)
            chunk = []
        chunk.append(n)
    return out + ([chunk] if chunk else [])


def safety_net_sql(s: str) -> str:
    """The drug's own reactions, with the all-drugs count where the all-drugs top 999 has one, that are designated
    medical events, name a pregnancy or newborn word, or that the screen never reaches, being outside the all-drugs
    top 999 or under its report floor."""
    dme = ", ".join(sql_str(t) for t in DESIGNATED_MEDICAL_EVENTS)
    return (f"SELECT o.reaction, o.reports, a.reports AS all_reports\n"
            f"FROM openfda.faers_d2_{s}_reactions o\n"
            f"LEFT JOIN openfda.faers_reaction_totals a ON a.reaction = o.reaction\n"
            f"WHERE a.reaction IS NULL OR o.reports < {SCREEN_FLOOR} OR o.reaction IN ({dme})\n"
            f"   OR o.reaction RLIKE {sql_str(PREGNANCY_NEWBORN)}\n"
            f"ORDER BY o.reports DESC")


def list_sizes_sql(s: str) -> str:
    """Size and smallest count of the drug's own list and the all-drugs list. Each view is read once, as two scalar
    subqueries over one view fail in Zetaris (MISSING_ATTRIBUTES on its exploded results, 25 Oct)."""
    return (f"SELECT o.own_terms, o.own_cutoff, a.all_terms, a.all_cutoff\n"
            f"FROM (SELECT COUNT(*) AS own_terms, MIN(reports) AS own_cutoff FROM openfda.faers_d2_{s}_reactions) o\n"
            f"CROSS JOIN (SELECT COUNT(*) AS all_terms, MIN(reports) AS all_cutoff "
            f"FROM openfda.faers_reaction_totals) a")


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


def scope_sql(s: str) -> str:
    """How many reactions each count list behind the screen holds, and the smallest count in it. One aggregate per
    view, because Spark rejects two scalar subqueries over the same exploded REST table (checked 25 Oct)."""
    return (f"SELECT d.terms AS drug_terms, d.cutoff AS drug_cutoff, t.terms AS all_terms, t.cutoff AS all_cutoff\n"
            f"FROM (SELECT COUNT(*) AS terms, MIN(reports) AS cutoff FROM openfda.faers_d2_{s}_reactions) d\n"
            f"CROSS JOIN (SELECT COUNT(*) AS terms, MIN(reports) AS cutoff FROM openfda.faers_reaction_totals) t")


def scope_summary(drug: str, rec: dict | None, screened: int, data_date, query_id: str | None = None,
                  min_a: int = 3) -> dict:
    """What the screen could see, for the dossier. A reaction is screened only if it is in openFDA's top 999 for all
    drugs and in the drug's own top 999, with at least min_a reports. A list shorter than 999 holds every reaction
    openFDA has for it; a full one leaves out everything below its cutoff. rec comes from scope_sql(), or None if
    that query failed."""
    def n(v):
        return None if v is None else int(float(v))
    lists = {k: ({"reactions": n(rec.get(f"{k}_terms")), "smallest_count": n(rec.get(f"{k}_cutoff"))} if rec else
                 {"reactions": None, "smallest_count": None}) for k in ("all", "drug")}
    for v in lists.values():
        v["full"] = None if v["reactions"] is None else v["reactions"] >= COUNT_LIMIT
    out = [f"A reaction is screened only if it is among openFDA's {COUNT_LIMIT} most-reported reactions for all "
           f"drugs and among the {COUNT_LIMIT} most-reported with {drug}, with at least {min_a} reports with {drug}."]
    for k, who, where in (("all", "The all-drugs list", "across all drugs"), ("drug", f"The {drug} list", f"with {drug}")):
        v = lists[k]
        if v["reactions"] is None:
            out.append(f"{who} could not be counted this run.")
            continue
        size = (f"{v['reactions']:,} reactions, the smallest with {v['smallest_count']:,} "
                f"report{'' if v['smallest_count'] == 1 else 's'}")
        out.append(f"{who} is full ({size}), so reactions reported fewer times {where} are not screened." if v["full"]
                   else f"{who} is not full ({size}), so it holds every reaction reported {where}.")
    out.append(f"{screened:,} reactions met all three conditions and were screened.")
    out.append(f"Reports are counted whenever they name {drug} (generic name or active substance), whether or not "
               f"it was the suspect drug.")
    out.append(f"openFDA data last updated {data_date}.")
    return {"statement": " ".join(out), "cap": COUNT_LIMIT, "min_reports": min_a,
            "all_drugs_list": lists["all"], "drug_list": lists["drug"], "screened": screened,
            "drug_role": "any (suspect, concomitant or interacting)", "data_last_updated": data_date,
            "query_id": query_id}


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
    approximate.
    A product counts only if it has an ingredient beyond the drug's own. For a single-ingredient drug that is any
    combination. When the drug itself is a combination (sitagliptin and metformin), its own product isn't one, so its
    ingredients aren't named to the agents as partner drugs of itself."""
    word = re.compile(rf"\b{re.escape(drug.upper())}\b")
    own = [re.compile(rf"\b{re.escape(p)}\b") for p in ingredient_parts(drug)] or [word]
    other = lambda part: not any(w.search(part) for w in own)  # noqa: E731
    by_field: dict[str, dict[str, int]] = {}
    for field, name, reports in rows:
        if word.search(name.upper()) and any(other(p) for p in ingredient_parts(name)):
            by_field.setdefault(field, {})[name] = by_field.get(field, {}).get(name, 0) + reports
    if not by_field:
        return {"share": 0.0, "reports": 0, "top_products": [], "partners": []}
    field, products = max(by_field.items(), key=lambda kv: sum(kv[1].values()))
    total = sum(products.values())
    partners: dict[str, int] = {}
    for name, reports in products.items():
        for part in ingredient_parts(name):
            if other(part):
                partners[part] = partners.get(part, 0) + reports
    top = sorted(products.items(), key=lambda kv: -kv[1])[:5]
    return {"share": round(min(total / drug_reports, 1.0), 3) if drug_reports else 0.0, "reports": total,
            "field": field, "top_products": [{"name": n, "reports": r} for n, r in top],
            "partners": [p for p, _ in sorted(partners.items(), key=lambda kv: -kv[1])[:5]]}


class DataClerk:
    def __init__(self, zetaris: ZetarisClient):
        self.z = zetaris
        self.label_choice = None
        # Why label() found nothing. label_missing means openFDA has no label under the name, label_error that the
        # label query failed for another reason.
        self.label_missing, self.label_error = False, None

    def register_drug(self, drug: str) -> dict:
        """Create the per-drug REST tables and views if they do not exist yet. Each statement is a round trip of
        2 to 2.5 s even when the table already exists, and eight in a row took a median of 22 s (24 and 25 Oct
        traces). So they run side by side, in two steps: the raw tables first, then the views and caches that
        read them."""
        s = slug(drug)
        q = urllib.parse.quote(f'"{drug}"')
        search = f"search={drug_search(drug)}"
        raws = {
            "reactions_raw": (rest_table(
                f"faers_d2_{s}_reactions_raw",
                f"{OPENFDA}/event.json?{search}&count=patient.reaction.reactionmeddrapt.exact&limit=999"),
                f"register FAERS reaction counts for {drug}"),
            "total_raw": (rest_table(
                f"faers_d2_{s}_total_raw", f"{OPENFDA}/event.json?{search}&count=serious"),
                f"register FAERS report total for {drug}"),
            "label_raw": (rest_table(
                f"label_d2_{s}_raw", f"{OPENFDA}/label.json?search=openfda.generic_name:{q}"
                                     f"&sort=effective_time:desc&limit={LABEL_CANDIDATES}"),
                f"register the newest labels for {drug}"),
        }
        views = {
            "reactions": (count_view(f"faers_d2_{s}_reactions", f"faers_d2_{s}_reactions_raw", "reaction"),
                          f"flatten reaction counts for {drug}"),
            "total": (count_view(f"faers_d2_{s}_total", f"faers_d2_{s}_total_raw", "serious_flag"),
                      f"flatten report total for {drug}"),
        }
        def kept(step, *args):
            """step(*args), with openFDA's "no match" (no_match) returned instead of raised."""
            try:
                return step(*args)
            except ZetarisError as e:
                if no_match(e):
                    return e
                raise

        def cache(raw):
            return kept(lambda: self.z.run(f"CACHE TABLE openfda_rest.{raw}", f"cache {raw}", ddl=True))

        with ThreadPoolExecutor(max_workers=5) as pool:
            created = dict(zip(raws, pool.map(lambda a: kept(self.z.ensure, *a), raws.values())))
            # No reaction counts or no total means no report names the drug, so stop here with a message, before
            # the views, the caches and every later query fail on the same missing search.
            if any(isinstance(created[k], ZetarisError) for k in ("reactions_raw", "total_raw")):
                raise DrugNotFound(self.not_found_message(drug))
            self.label_missing = isinstance(created["label_raw"], ZetarisError)
            if self.label_missing:
                created["label_raw"] = None  # not created, as no label matched
            view_jobs = [pool.submit(kept, self.z.ensure, *a) for a in views.values()]
            # Cache every run: CACHE TABLE is cheap once cached, and the cache does not survive a Zetaris restart.
            to_cache = [f"faers_d2_{s}_reactions_raw", f"faers_d2_{s}_total_raw"]
            to_cache += [] if self.label_missing else [f"label_d2_{s}_raw"]
            cache_jobs = {raw: pool.submit(cache, raw) for raw in to_cache}
            created.update(zip(views, [j.result() for j in view_jobs]))
            # If Zetaris only calls openFDA when a table is read, the no-match shows up here instead.
            missing_drug = any(isinstance(created[k], ZetarisError) for k in views)
            for raw, j in cache_jobs.items():
                if isinstance(j.result(), ZetarisError):
                    if raw.startswith("label_"):
                        self.label_missing = True
                    else:
                        missing_drug = True
            if missing_drug:
                raise DrugNotFound(self.not_found_message(drug))
        return created

    def brand_generics(self, drug: str) -> list[str]:
        """The generic names openFDA's drug labels give for a brand name equal to the input (ignoring case), from the
        labels' own openfda.brand_name and openfda.generic_name fields, most labels first. Only for a message: the run
        never swaps a brand for its generic itself. Empty when no label has that brand name or the lookup fails. Costs
        one or two openFDA reads, and only runs when a run is about to stop."""
        q = urllib.parse.quote(f'"{drug}"')
        url = f"{OPENFDA}/label.json?search=openfda.brand_name:{q}&limit=100"
        name = "label_brand_" + hashlib.sha1(url.encode()).hexdigest()[:12]
        try:
            self.z.ensure(rest_table(name, url), f"look up '{drug}' as a brand name")
            res = self.z.run(f"SELECT to_json(r.openfda) AS o FROM openfda_rest.{name} LATERAL VIEW explode(results) "
                             f"AS r", f"generic names for the brand name '{drug}'")
        except ZetarisError:
            return []
        counts: dict[str, int] = {}
        for row in res.rows:
            o = json.loads(row[0] or "{}")
            if any(" ".join(b.split()).lower() == drug for b in o.get("brand_name") or []):
                for g in o.get("generic_name") or []:
                    counts[" ".join(g.split())] = counts.get(" ".join(g.split()), 0) + 1
        return [g for g, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def not_found_message(self, drug: str) -> str:
        return (f"No FAERS reports in openFDA name '{drug}' as a generic name or active substance, so there is "
                f"nothing to assess. {brand_hint(drug, self.brand_generics(drug))}")

    def no_label_message(self, drug: str, reports: int) -> str:
        """Why a run with reports stops before any model call. Either no label matched the name (label_missing), or
        the chosen label has none of the sections the app reads."""
        if not self.label_missing:
            return (f"openFDA has {reports:,} adverse event reports naming '{drug}', but the label Vigil picked for it "
                    f"has none of the sections Vigil reads (warnings, adverse reactions, patient information and "
                    f"others), so no reaction can be checked against it. The run stopped before any model call.")
        generics = self.brand_generics(drug)
        why = brand_hint(drug, generics) if generics else (
            "openFDA holds no label for some drugs, such as one withdrawn long ago, and a misspelt or brand name can "
            f"still match a few reports. {SPELLING_HINT}")
        return (f"openFDA has {reports:,} adverse event reports naming '{drug}' but no drug label under that generic "
                f"name, so no reaction can be checked against a label. The run stopped before any model call. {why}")

    def totals(self, drug: str) -> dict:
        s = slug(drug)
        try:
            res = self.z.run(
                f"SELECT (SELECT SUM(reports) FROM openfda.faers_d2_{s}_total) AS drug_reports, "
                f"(SELECT SUM(reports) FROM openfda.faers_total) AS all_reports, "
                f"(SELECT meta.last_updated FROM openfda_rest.faers_total_raw) AS data_last_updated",
                f"report totals for {drug}")
        except ZetarisError as e:
            if not no_match(e):
                raise  # openFDA or Zetaris failing, not a missing drug
            raise DrugNotFound(self.not_found_message(drug)) from e
        rec = res.records()[0]
        if not rec.get("drug_reports"):
            raise DrugNotFound(self.not_found_message(drug))
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

    def _count_table(self, search: str, count: str, purpose: str, limit: int | None = None,
                     created: list | None = None) -> str:
        """A REST table for one openFDA count query, named by a hash of its URL so that runs and drugs
        asking the same question share one table (they cannot be deleted through SQL). created, if given, gets the
        name when the table is registered now, which costs one more openFDA call."""
        url = count_url(search, count, limit)
        name = "faers_q_" + hashlib.sha1(url.encode()).hexdigest()[:12]
        if self.z.ensure(rest_table(name, url), purpose) and created is not None:
            created.append(name)
        return name

    def serious_terms(self, drug: str) -> dict:
        """Counts for the safety net (app/data/safety_net.py), all from Zetaris SQL. One query reads the drug's own
        reactions joined to the all-drugs ones (safety_net_sql), and one the size and smallest count of each list. The
        screen reads both tables too, and they cost no openFDA call while Zetaris holds them in its cache (the drug's
        own list is cached every run, the all-drugs one by openfda_baseline.sql). A full own list (999 terms) misses
        terms below its cutoff. Then the designated medical events missing from it are counted directly in openFDA, in
        chunks that keep each URL short, and the pregnancy and newborn words by an openFDA word search. Each is a REST
        table read once.
        A direct count names every reaction on the matching reports, so it can come back full too. The terms it does
        name have exact counts, as every report naming one of them matches, so only the chunk's absent terms are counted
        again, in a smaller search (on 25 Oct semaglutide's 45 came back full, smallest count 1), up to DIRECT_COUNTS
        in all. openFDA answers a search that matches nothing with a 404, which Zetaris reports as "HTTP 400: REST API
        call failed" (checked 25 Oct on semaglutide's 9 absent terms). So the re-count also searches the chunk's
        least-reported term it found, an anchor that always matches, and an absent term it still lacks has no reports.
        A direct count that fails is recorded with its error; a failure of the first two queries raises ZetarisError."""
        s = slug(drug)
        own = self.z.run(safety_net_sql(s), f"serious-term safety net for {drug}")
        sizes = self.z.run(list_sizes_sql(s), f"reaction list sizes and cutoffs for {drug}")
        out = {"own": own.records(), "sizes": sizes.records()[0], "direct": [],
               "query_ids": [own.query_id, sizes.query_id]}
        created: list[str] = []
        if int(float(out["sizes"]["own_terms"])) >= COUNT_LIMIT:
            have = {r["reaction"] for r in out["own"]}
            todo = [(c, None) for c in term_chunks(drug, [t for t in DESIGNATED_MEDICAL_EVENTS if t not in have])]
            while todo and len(out["direct"]) < DIRECT_COUNTS:
                chunk, anchor = todo.pop(0)
                clause = any_reaction(chunk + ([anchor] if anchor else []))
                d = self._direct_count(drug, "designated_medical_event", clause, chunk, created)
                if anchor:
                    d["anchor"] = anchor
                out["direct"].append(d)
                rows = d.get("rows", [])
                named = {r["reaction"]: int(float(r["reports"])) for r in rows if r["reaction"] in chunk}
                absent = [t for t in chunk if t not in named]
                if len(rows) >= COUNT_LIMIT and absent and named:
                    # absent and the anchor are part of one chunk, so the re-count's URL is no longer than its own.
                    todo.append((absent, min(named, key=lambda t: (named[t], t))))
            out["not_counted"] = [t for c, _ in todo for t in c]
            out["direct"].append(self._direct_count(drug, "pregnancy_or_newborn",
                                                    any_of(REACTION_WORDS_FIELD, list(PREGNANCY_NEWBORN_WORDS)),
                                                    list(PREGNANCY_NEWBORN_WORDS), created))
        out["query_ids"] += [d["query_id"] for d in out["direct"] if "query_id" in d]
        out["registered_now"] = len(created)
        return out

    def _direct_count(self, drug: str, kind: str, clause: str, values: list[str], created: list) -> dict:
        """One direct openFDA count for the safety net, every reaction on the drug's reports that match the clause,
        with the all-drugs count where Zetaris has it. A failure is recorded, not raised."""
        d, what = {"kind": kind, "values": values}, KIND_NAMES[kind]
        try:
            raw = self._count_table(f"{drug_search(drug)}+AND+{clause}", REACTION_FIELD,
                                    f"register direct counts of {len(values)} {what} for {drug}", COUNT_LIMIT, created)
            res = self.z.run(f"SELECT d.reaction, d.reports, a.reports AS all_reports FROM (SELECT r.term AS reaction, "
                             f"r.`count` AS reports FROM openfda_rest.{raw} LATERAL VIEW explode(results) AS r) d "
                             f"LEFT JOIN openfda.faers_reaction_totals a ON a.reaction = d.reaction",
                             f"direct counts of {len(values)} {what} for {drug}")
        except ZetarisError as e:
            d["error"] = str(e)[:300]
        else:
            d.update(query_id=res.query_id, rows=res.records())
        return d

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

    def scope(self, drug: str) -> tuple[QueryResult | None, dict | None]:
        """Size and cutoff of the two count lists the screen joins (scope_sql), for scope_summary(). None if the
        query fails; the run goes on without it."""
        try:
            res = self.z.run(scope_sql(slug(drug)), f"size of the reaction count lists for {drug}")
        except ZetarisError:
            return None, None
        recs = res.records()
        return res, (recs[0] if recs else None)

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

    def report_sources(self, drug: str, reaction: str | None = None) -> tuple[list[str], dict]:
        """The drug's reports, or those of one of its reactions, by country of the event and by who reported, from two
        openFDA counts registered in Zetaris, with the report total from the drug's own tables. Reports that leave a
        field blank are not counted, so the total minus the counts is the unknown share. A part whose query fails is
        None, and its check says "unknown"; the run goes on."""
        s = slug(drug)
        search, what = drug_search(drug), drug
        total = f"SELECT SUM(reports) FROM openfda.faers_d2_{s}_total"
        if reaction:
            search, what = f"{search}+AND+{phrase(REACTION_FIELD, reaction)}", f"{drug} and {reaction}"
            total = f"SELECT SUM(reports) FROM openfda.faers_d2_{s}_reactions WHERE reaction = {sql_str(reaction)}"
        out, qids = {"country": None, "reporter": None, "reports": None}, []
        for part, field in SOURCE_FIELDS.items():
            try:
                raw = self._count_table(search, field, f"register reports by {part} for {what}", COUNT_LIMIT)
                res = self.z.run(f"SELECT CAST(r.term AS STRING) AS term, r.`count` AS reports, ({total}) AS total "
                                 f"FROM openfda_rest.{raw} LATERAL VIEW explode(results) AS r",
                                 f"reports by {part} for {what}")
            except ZetarisError:
                continue
            qids.append(res.query_id)
            recs = res.records()
            # "1.0" and "1" are the same qualification code, whichever type Zetaris gives the term.
            out[part] = {(str(int(float(t))) if re.fullmatch(r"\d+(\.0+)?", t) else t): int(float(rec["reports"]))
                         for rec in recs for t in [str(rec["term"])]}
            if recs and recs[0].get("total") is not None:
                out["reports"] = int(float(recs[0]["total"]))
        return qids, out

    def label(self, drug: str) -> tuple[str | None, dict]:
        """Sections of the label choose_label() picks from the newest ones. Fields vary between labels (and
        DESCRIBE truncates long schemas), so fetch whole label records as JSON and pick the sections present.
        Which label was chosen, and why, is kept in self.label_choice for the trace and the dossier."""
        raw = f"openfda_rest.label_d2_{slug(drug)}_raw"
        self.label_choice = None
        if self.label_missing:  # register_drug() found no label under the name
            return None, {}
        try:
            res = self.z.run(f"SELECT to_json(r) AS label FROM {raw} LATERAL VIEW explode(results) AS r",
                             f"label text for {drug}")
        except ZetarisError as e:
            if no_match(e):
                self.label_missing = True
            else:
                self.label_error = str(e)[:300]
            return None, {}
        if not res.rows:
            self.label_missing = True
            return res.query_id, {}
        rec, self.label_choice = choose_label([json.loads(row[0]) for row in res.rows])
        out = {f: " ".join(rec[f]) for f in LABEL_FIELDS if rec.get(f)}
        for k, v in clinical_pharmacology_parts(" ".join(rec.get("clinical_pharmacology") or [])).items():
            out.setdefault(k, v)  # only where openFDA did not split the section itself
        out.update({k: rec[k] for k in ("effective_time", "set_id") if rec.get(k)})
        return res.query_id, out
