"""The serious-term safety net. It lists designated medical events, pregnancy and newborn terms, and the mostly serious
terms that the screen never reaches, each with whether the screen reached it, for a person to review. Code, not a model.

The screen inner-joins two openFDA top-999 lists, all drugs and the drug's own, and keeps reactions with 3 or more
reports, so a reaction below either cutoff is never screened. On 25 Oct the all-drugs list stopped at 9,059 reports.
These were all in the drug's own list that day but outside the all-drugs one. Zuranolone had EXPOSURE VIA BREAST MILK
(22 reports) and SOMNOLENCE NEONATAL (8). Empagliflozin had EUGLYCAEMIC DIABETIC KETOACIDOSIS (2,273) and FOURNIER^S
GANGRENE (1,207). Semaglutide had OPTIC ISCHAEMIC NEUROPATHY (869).

There are three sections, and a term sits in the first that takes it.
- EMA's designated medical events, a fixed list of 62 MedDRA terms.
- Pregnancy, breastfeeding and newborn terms, by whole words in the name, most-reported first, with no cap.
- Missed serious terms. Every clinical term outside the screen (outside the all-drugs top 999, or under 3 reports)
  where more than half of the drug's reports with it are flagged serious in FAERS, most-reported first, with no cap.
  Bryan chose this rule on 25 Oct, after the earlier "10 most-reported hidden terms" listed FOOD CRAVING and SENSITIVE
  SKIN for semaglutide and missed its medullary thyroid cancer and necrotising pancreatitis. The serious counts are the
  ones the run already fetches (DataClerk.seriousness).
The dossier lists the sections in SECTIONS order, with the missed serious terms second.
Each term gets its reports with the drug, its screen status and what the label search found. The counts come from the
Data Clerk's SQL (DataClerk.serious_terms). Nothing here is promoted. These terms never enter the review queue, its
ranking or any prompt."""
import re
from concurrent.futures import TimeoutError as FutureTimeout

from app.agents.rules import ADMINISTRATIVE, PREGNANCY_EXPOSURE, SOCIAL
from app.data.label import search, sections

NOTE = "This list sits outside the screen. It is shown for a person to review, and its terms are not signals."
DME_SOURCE = ("EMA designated medical events (DME) list, EMA/326038/2020, June 2020, 62 MedDRA preferred terms, in "
              "upper case as FAERS writes them (an apostrophe is ^)")
# EMA/326038/2020 (June 2020), in the list's own order.
DESIGNATED_MEDICAL_EVENTS = (
    "ACUTE HEPATIC FAILURE", "ACUTE KIDNEY INJURY", "AGRANULOCYTOSIS", "ANAPHYLACTIC REACTION", "ANAPHYLACTIC SHOCK",
    "ANAPHYLACTOID REACTION", "ANAPHYLACTOID SHOCK", "ANGIOEDEMA", "APLASIA PURE RED CELL", "APLASTIC ANAEMIA",
    "AUTOIMMUNE HAEMOLYTIC ANAEMIA", "AUTOIMMUNE HEPATITIS", "AUTOIMMUNE PANCREATITIS", "AZOTAEMIA", "BLINDNESS",
    "BONE MARROW FAILURE", "DEAFNESS", "DEAFNESS NEUROSENSORY", "DEAFNESS PERMANENT", "DEAFNESS TRANSITORY",
    "DERMATITIS EXFOLIATIVE", "DERMATITIS EXFOLIATIVE GENERALISED",
    "DRUG REACTION WITH EOSINOPHILIA AND SYSTEMIC SYMPTOMS", "DRUG-INDUCED LIVER INJURY", "ERYTHEMA MULTIFORME",
    "FEBRILE NEUTROPENIA", "GRANULOCYTOPENIA", "HAEMOLYSIS", "HAEMOLYTIC ANAEMIA", "HEPATIC FAILURE",
    "HEPATIC INFARCTION", "HEPATIC NECROSIS", "HEPATITIS FULMINANT", "IMMUNE THROMBOCYTOPENIA",
    "INTESTINAL PERFORATION", "ISCHAEMIC PANCREATITIS", "NEUTROPENIC COLITIS", "NEUTROPENIC INFECTION",
    "NEUTROPENIC SEPSIS", "OEDEMATOUS PANCREATITIS", "OPTIC ISCHAEMIC NEUROPATHY", "PANCREATITIS",
    "PANCREATITIS ACUTE", "PANCYTOPENIA", "PRODUCT CONTAMINATION MICROBIAL",
    "PROGRESSIVE MULTIFOCAL LEUKOENCEPHALOPATHY", "PULMONARY ARTERIAL HYPERTENSION", "PULMONARY FIBROSIS",
    "PULMONARY HYPERTENSION", "RENAL FAILURE", "REYE^S SYNDROME", "RHABDOMYOLYSIS", "STEVENS-JOHNSON SYNDROME",
    "SUDDEN CARDIAC DEATH", "SUDDEN HEARING LOSS", "SUDDEN VISUAL LOSS", "THROMBOTIC THROMBOCYTOPENIC PURPURA",
    "TORSADE DE POINTES", "TOXIC EPIDERMAL NECROLYSIS", "TOXIC OPTIC NEUROPATHY",
    "TRANSMISSION OF AN INFECTIOUS AGENT VIA PRODUCT", "VENTRICULAR FIBRILLATION")
# Pregnancy, breastfeeding and newborn terms are found by whole words in the name, not by a fixed list. MedDRA has
# dozens of such terms, and on 25 Oct zuranolone's own list alone had 17, among them SOMNOLENCE NEONATAL, INFANT
# SEDATION, POOR FEEDING INFANT and PLACENTA PRAEVIA. A fixed list would have to name every one in advance.
# Whole words, not stems, because openFDA's word search for a full list matches whole words, so both find the same
# terms. Stems also over-match. FOET finds FOETOR HEPATICUS, and PREMATURE alone finds PREMATURE EJACULATION.
PREGNANCY_NEWBORN_WORDS = (
    "PREGNANCY", "PREGNANT", "ABORTION", "STILLBIRTH", "PREMATURE DELIVERY", "PREMATURE LABOUR", "PREMATURE RUPTURE",
    "PLACENTA", "PLACENTAL", "FOETAL", "FOETUS", "FETAL", "FETUS", "CONGENITAL", "NEONATAL", "NEONATE", "NEWBORN",
    "INFANT", "BABY", "BREAST MILK", "BREAST FEEDING", "LACTATION")
# The same words as one regular expression, for Spark SQL's RLIKE (Java) and for Python. Both find it anywhere.
PREGNANCY_NEWBORN = r"\b(" + "|".join(PREGNANCY_NEWBORN_WORDS) + r")\b"
# A missed term is listed when more than this share of the drug's reports with it are flagged serious.
SERIOUS_SHARE = 0.5
SCREEN_FLOOR = 3  # signal_sql's min_a, so the screen keeps reactions with at least this many reports
GROUPS = {"designated_medical_event": DME_SOURCE,
          "missed_serious": f"clinical terms outside the screen with more than {SERIOUS_SHARE:.0%} of the drug's "
                            f"reports with them flagged serious in FAERS (death, life-threatening, hospitalisation, "
                            f"disability, congenital anomaly or another serious outcome), most-reported first",
          "pregnancy_or_newborn": "pregnancy, breastfeeding and newborn terms, by whole words in the name ("
                                  + ", ".join(PREGNANCY_NEWBORN_WORDS) + "), most-reported first"}
# The dossier's name for each group's section, in the dossier's order.
SECTIONS = {"designated_medical_event": "designated_medical_events", "missed_serious": "missed_serious_terms",
            "pregnancy_or_newborn": "pregnancy_and_newborn"}
KIND_NAMES = {"designated_medical_event": "designated medical events",
              "pregnancy_or_newborn": "pregnancy and newborn words"}
STATUS_ORDER = {"not_screened": 0, "passes_not_assessed": 1, "below_screen": 2, "in_review_queue": 3}
OWN = "drug's own list"


def pregnancy_or_newborn(reaction: str) -> bool:
    return re.search(PREGNANCY_NEWBORN, reaction) is not None


def non_clinical(reaction: str) -> bool:
    """The rules' non-clinical terms (app/agents/rules.py), left out of the missed serious terms only, and counted. In
    the other sections an exposure or a product term is the information, such as a breastfed infant or a contaminated
    product."""
    return any(p.search(reaction) for p in (ADMINISTRATIVE, SOCIAL, PREGNANCY_EXPOSURE))


def number(value) -> int | None:
    return None if value is None else int(float(value))


def outside_screen(rec: dict) -> bool:
    """Not in the all-drugs top 999, or under the screen's report floor, so the screen never reaches it."""
    return rec.get("all_reports") is None or number(rec["reports"]) < SCREEN_FLOOR


def terms(raw: dict, severity: dict | None = None, left_out: dict | None = None) -> dict:
    """{reaction: {"reports", "all_drug_reports", "count_from", "groups", "serious_share"}} from
    DataClerk.serious_terms() and the run's serious counts (DataClerk.seriousness). A term takes one group, the first
    of designated medical event, pregnancy or newborn, missed serious. left_out, if given, counts the terms outside the
    screen that the missed serious terms leave out, so nothing is dropped without a count."""
    out: dict[str, dict] = {}
    severity = severity or {}
    left_out = left_out if left_out is not None else {}

    def add(rec: dict, group: str, count_from: str) -> None:
        sev = severity.get(rec["reaction"]) or {}
        out.setdefault(rec["reaction"], {"reports": number(rec["reports"]),
                                         "all_drug_reports": number(rec.get("all_reports")),
                                         "count_from": count_from, "groups": [group],
                                         "serious_share": sev.get("serious_share")})

    own = raw["own"]
    dme = set(DESIGNATED_MEDICAL_EVENTS)
    for rec in own:
        r = rec["reaction"]
        if r in dme:
            add(rec, "designated_medical_event", OWN)
        elif pregnancy_or_newborn(r):
            add(rec, "pregnancy_or_newborn", OWN)
        elif outside_screen(rec):
            serious = (severity.get(r) or {}).get("serious")
            if serious is None:
                left_out["serious_share_unknown"] = left_out.get("serious_share_unknown", 0) + 1
            elif serious <= SERIOUS_SHARE * number(rec["reports"]):
                left_out["not_mostly_serious"] = left_out.get("not_mostly_serious", 0) + 1
            elif non_clinical(r):
                left_out["non_clinical"] = left_out.get("non_clinical", 0) + 1
            else:
                add(rec, "missed_serious", OWN)
    have = {r["reaction"] for r in own}
    for d in raw.get("direct", []):
        for rec in d.get("rows", []):
            r = rec["reaction"]
            if r in have:
                continue  # the drug's own list counts it, as the screen does
            if d["kind"] == "designated_medical_event" and r in d["values"]:
                add(rec, "designated_medical_event", f"direct openFDA count (query {d['query_id']})")
            elif d["kind"] == "pregnancy_or_newborn" and pregnancy_or_newborn(r):
                add(rec, "pregnancy_or_newborn", f"direct openFDA count (query {d['query_id']})")
    return out


def screen_status(reaction: str, t: dict, sizes: dict, screened: dict, passing: set, queued: dict) -> tuple[str, str]:
    """(status, plain sentence). A term the agents assessed only points to its queue item, so it is not repeated."""
    if reaction in queued:
        return "in_review_queue", f"In the review queue (workflow status {queued[reaction]}); see that item."
    if reaction in passing:
        return "passes_not_assessed", "Passes the Evans screen, but was not among the rows the agents assessed."
    if reaction in screened:
        s = screened[reaction]
        return "below_screen", (f"Screened, below the Evans screen (PRR {s.prr}, chi-squared {s.chi2}; it needs PRR 2 "
                                f"and chi-squared 4).")
    why = []
    if t["all_drug_reports"] is None:
        why.append(f"it is outside the all-drugs top 999 (smallest count {sizes['all_cutoff']:,})")
    if t["count_from"] != OWN:
        why.append(f"it is outside the drug's own top 999 (smallest count {sizes['own_cutoff']:,})")
    if t["reports"] < SCREEN_FLOOR:
        why.append(f"it has fewer than {SCREEN_FLOOR} reports with the drug")
    if not why:
        why.append("the screen's rows leave it out, as they need some reports of it for other drugs")
    return "not_screened", "Not screened, because " + " and ".join(why) + "."


def label_status(reaction: str, label: dict) -> str:
    """The label search's summary. The search reads FAERS's ^ as an apostrophe (label.norm)."""
    if not sections(label or {}):
        return "No current label was found."
    return search(reaction, label)["summary"]


def limits(raw: dict, sizes: dict, left_out: dict | None = None, have_severity: bool = True) -> list[str]:
    left_out = left_out or {}
    out = ["Designated medical events are matched by exact name, and pregnancy, breastfeeding and newborn terms by "
           "whole words in the name, so a related term that uses none of those words is missed.",
           f"Missed serious terms come from the drug's own list, where the run's serious counts cover them. The serious "
           f"flag is for the whole report, which may list other reactions."]
    if not have_severity:
        out.append("The run's serious counts were not available, so no missed serious terms are listed this run.")
    elif left_out.get("serious_share_unknown"):
        out.append(f"{left_out['serious_share_unknown']:,} terms outside the screen have no serious count (they are "
                   f"below the cutoff of the drug's serious-report list), so they could not be judged and are not "
                   f"listed.")
    if left_out.get("not_mostly_serious"):
        out.append(f"{left_out['not_mostly_serious']:,} terms outside the screen have {SERIOUS_SHARE:.0%} or fewer of "
                   f"their reports flagged serious, so they are not listed.")
    if left_out.get("non_clinical"):
        out.append(f"{left_out['non_clinical']:,} serious terms outside the screen are left out as non-clinical by the "
                   f"app's rules (administrative, social or pregnancy-exposure terms).")
    if not sizes["own_full"]:
        out.append(f"The drug's own list is complete ({sizes['own_terms']:,} terms), so it holds every reaction "
                   f"reported with the drug and no direct openFDA count was needed.")
        return out
    out.append(f"The drug's own list is full ({sizes['own_terms']:,} terms, smallest count {sizes['own_cutoff']:,}). "
               f"Designated medical events missing from it were counted directly in openFDA, and pregnancy and newborn "
               f"terms by an openFDA word search. Missed serious terms below its cutoff are not seen.")
    direct = raw.get("direct", [])
    dme = [d for d in direct if d["kind"] == "designated_medical_event"]
    named = {r["reaction"] for d in dme for r in d.get("rows", [])}
    # A term is settled once a direct count names it, or a count that came back below openFDA's largest list held it.
    settled = named | {t for d in dme if "rows" in d and len(d["rows"]) < 999 for t in d["values"]}
    for d in direct:
        what = f"{len(d['values'])} {KIND_NAMES[d['kind']]}"
        if "error" in d:
            out.append(f"The direct count for {what} failed ({d['error'][:200]}). openFDA also answers with an error "
                       f"when no report matches.")
        elif len(d["rows"]) >= 999:
            cutoff = min(number(r["reports"]) for r in d["rows"])
            if d["kind"] != "designated_medical_event":
                out.append(f"The word search came back as openFDA's largest list (999 terms, smallest count "
                           f"{cutoff:,}), so a pregnancy or newborn term with {cutoff:,} or fewer reports may be "
                           f"missing.")
            elif [t for t in d["values"] if t not in settled]:
                out.append(f"The direct count for {what} came back as openFDA's largest list (999 terms, smallest "
                           f"count {cutoff:,}), so these may each still have {cutoff:,} or fewer reports ("
                           f"{', '.join(t for t in d['values'] if t not in settled)}).")
    unsettled = [t for d in dme if "error" in d for t in d["values"] if t not in settled]
    if unsettled:
        out.append(f"These designated medical events below the drug's own cutoff have no count this run "
                   f"({', '.join(unsettled)}).")
    if raw.get("not_counted"):
        out.append(f"The run's direct counts ran out before these were counted ({', '.join(raw['not_counted'])}).")
    return out


def assemble(raw: dict, signals: list, passing: list, queue: list[dict], label: dict,
             severity: dict | None = None) -> dict:
    """The dossier section from DataClerk.serious_terms(), the run's serious counts, screen and queue. Its three
    sections are listed in SECTIONS. Designated medical events keep their order (not screened first, then by reports),
    and the other two are most-reported first."""
    s = raw["sizes"]
    sizes = {"own_terms": number(s["own_terms"]), "own_cutoff": number(s["own_cutoff"]),
             "all_terms": number(s["all_terms"]), "all_cutoff": number(s["all_cutoff"])}
    sizes["own_full"] = sizes["own_terms"] >= 999
    screened = {x.reaction: x for x in signals}
    queued = {q["reaction"]: q["workflow_status"] for q in queue}
    left_out: dict = {}
    sections_out = {name: [] for name in SECTIONS.values()}
    for r, t in terms(raw, severity, left_out).items():
        status, detail = screen_status(r, t, sizes, screened, {x.reaction for x in passing}, queued)
        item = {"reaction": r, "reports": t["reports"], "all_drug_reports": t["all_drug_reports"],
                "serious_share": t["serious_share"], "count_from": t["count_from"], "screen_status": status,
                "screen_detail": detail}
        if status != "in_review_queue":
            item["label_status"] = label_status(r, label)
        sections_out[SECTIONS[t["groups"][0]]].append(item)
    sections_out["designated_medical_events"].sort(
        key=lambda i: (STATUS_ORDER[i["screen_status"]], -i["reports"], i["reaction"]))
    for name in ("missed_serious_terms", "pregnancy_and_newborn"):
        sections_out[name].sort(key=lambda i: (-i["reports"], i["reaction"]))
    reads, registered = sum("query_id" in d for d in raw.get("direct", [])), raw.get("registered_now", 0)
    return {"status": "done", "note": NOTE, "groups": GROUPS, "serious_threshold": SERIOUS_SHARE, "lists": sizes,
            **sections_out, "term_count": sum(len(v) for v in sections_out.values()), "left_out": left_out,
            "openfda": {"requests": registered + reads, "registered_now": registered, "direct_reads": reads,
                        "note": "Each read of a direct count's REST table fetches openFDA once, and registering a new "
                                "one costs one more the first time. The drug's own list and the all-drugs list are "
                                "the screen's tables, read from Zetaris's cache."},
            "limits": limits(raw, sizes, left_out, bool(severity)), "query_ids": raw["query_ids"]}


def collect(job, wait: float, tracer, signals: list, passing: list, queue: list[dict], label: dict,
            severity: dict | None = None) -> dict:
    """The section, waiting at most `wait` seconds for the background job. A job that is not back, or failed, gives a
    section that says so and a degraded trace event. It never stops the run."""
    try:
        raw = job.result(timeout=max(0.0, wait))
        section = assemble(raw, signals, passing, queue, label, severity)
    except Exception as e:  # shown for a person to review, so no failure here may stop the run
        status = "not finished" if isinstance(e, FutureTimeout) else f"failed: {str(e)[:200]}"
        tracer.event("data_clerk", "degraded", step="safety net", error=status,
                     fallback="no serious-term safety net this run")
        return {"status": status, "note": NOTE, **{name: [] for name in SECTIONS.values()}, "term_count": 0,
                "query_ids": []}
    for d in raw.get("direct", []):
        if "error" in d:
            tracer.event("data_clerk", "degraded", step="safety net direct count", error=d["error"][:200],
                         fallback=f"no counts below the drug's own cutoff for {len(d['values'])} "
                                  f"{KIND_NAMES[d['kind']]}")
    items = [i for name in SECTIONS.values() for i in section[name]]
    tracer.event("data_clerk", "safety_net", terms=len(items), by_section={n: len(section[n]) for n in SECTIONS.values()},
                 not_screened=sum(i["screen_status"] == "not_screened" for i in items),
                 openfda_requests=section["openfda"]["requests"], query_ids=section["query_ids"])
    return section
