"""Offline tests for the serious-term safety net. Run: python -I -m pytest tests

Counts marked "recorded" were read through Zetaris on 25 Oct (openFDA data updated 2026-07-30), from each drug's own
table, the all-drugs top 999 and the direct counts the safety net registered. Other counts are made up and say so."""
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.data.faers import (COUNT_LIMIT, URL_LIMIT, DataClerk, any_reaction, count_url, drug_search,  # noqa: E402
                            safety_net_sql, term_chunks, REACTION_FIELD)
from app.data.safety_net import (DESIGNATED_MEDICAL_EVENTS, NOTE, PREGNANCY_NEWBORN, assemble, collect,  # noqa: E402
                                 pregnancy_or_newborn)
from app.schemas import QueryResult, Signal  # noqa: E402

ALL_CUTOFF = 9059  # recorded, the smallest count in the all-drugs top 999
# Recorded. Zuranolone's own list is complete (461 terms, smallest count 1). (reaction, reports, all-drugs reports)
ZURANOLONE = [("FEELING DRUNK", 77, None), ("PERINATAL DEPRESSION", 44, None), ("EXPOSURE VIA BREAST MILK", 22, None),
              ("BRADYPHRENIA", 16, None), ("DISSOCIATION", 11, None), ("SLOW SPEECH", 10, None),
              ("DYSPHEMIA", 8, None), ("INTRUSIVE THOUGHTS", 8, None), ("SOMNOLENCE NEONATAL", 8, None),
              ("TACHYPHRENIA", 8, None), ("SOMNAMBULISM", 7, None), ("MATERNAL EXPOSURE DURING PREGNANCY", 5, 87045),
              ("POOR FEEDING INFANT", 3, None), ("ACUTE KIDNEY INJURY", 1, 150299), ("PANCREATITIS", 1, 52223)]
# Recorded. Empagliflozin's own list is full (999 terms, smallest count 32). These are its 11 most-reported terms
# outside the all-drugs top 999, the 22 designated medical events in it and one pregnancy term.
EMPAGLIFLOZIN_DME_OWN = {
    "ACUTE KIDNEY INJURY": (1942, 150299), "PANCREATITIS": (662, 52223), "RENAL FAILURE": (575, 132016),
    "PANCREATITIS ACUTE": (254, 22022), "RHABDOMYOLYSIS": (184, 41077), "BLINDNESS": (167, 40183),
    "ANAPHYLACTIC REACTION": (148, 54207), "ANGIOEDEMA": (146, 43561), "PULMONARY HYPERTENSION": (118, 20628),
    "DRUG-INDUCED LIVER INJURY": (114, 30439), "FEBRILE NEUTROPENIA": (101, 65354), "PANCYTOPENIA": (77, 54995),
    "VENTRICULAR FIBRILLATION": (74, 10993), "DEAFNESS": (67, 25852),
    "DRUG REACTION WITH EOSINOPHILIA AND SYSTEMIC SYMPTOMS": (59, 25217), "HEPATIC FAILURE": (56, 29828),
    "ANAPHYLACTIC SHOCK": (49, 25287), "AGRANULOCYTOSIS": (47, 18242), "PULMONARY ARTERIAL HYPERTENSION": (43, 14378),
    "PULMONARY FIBROSIS": (41, 18864), "IMMUNE THROMBOCYTOPENIA": (37, None), "ACUTE HEPATIC FAILURE": (33, 13422)}
EMPAGLIFLOZIN = [("EUGLYCAEMIC DIABETIC KETOACIDOSIS", 2273, None), ("KETOACIDOSIS", 1713, None),
                 ("FOURNIER^S GANGRENE", 1207, None), ("NECROTISING FASCIITIS", 271, None),
                 ("ABNORMAL LOSS OF WEIGHT", 248, None), ("ACIDOSIS", 240, None), ("HYPOVOLAEMIA", 233, None),
                 ("POLYURIA", 228, None), ("VULVOVAGINAL PRURITUS", 220, None),
                 ("VULVOVAGINAL MYCOTIC INFECTION", 197, None), ("BRONCHIECTASIS", 190, None),
                 ("MATERNAL EXPOSURE DURING PREGNANCY", 39, 87045)] + [
    (r, n, a) for r, (n, a) in EMPAGLIFLOZIN_DME_OWN.items()]
# Recorded. Some designated medical events and some pregnancy and newborn terms from empagliflozin's direct counts.
EMPAGLIFLOZIN_DME = [("AUTOIMMUNE HEPATITIS", 27, None), ("OPTIC ISCHAEMIC NEUROPATHY", 25, None),
                     ("STEVENS-JOHNSON SYNDROME", 23, 21989), ("APLASIA PURE RED CELL", 2, None)]
EMPAGLIFLOZIN_WORDS = [("EXPOSURE DURING PREGNANCY", 18, 61367), ("NORMAL NEWBORN", 4, None),
                       ("SEPSIS NEONATAL", 2, None), ("MATERNAL EXPOSURE DURING PREGNANCY", 39, 87045)]
# Made up. Reactions named on the same reports that are neither, which the safety net must leave out.
CO_REPORTED = [("NAUSEA", 40, 600000), ("DIARRHOEA", 12, 500000)]
# Recorded. Semaglutide's own list is full (999 terms, smallest count 34). These are the 17 designated medical events in
# it, and two of its most-reported terms outside the all-drugs top 999.
SEMAGLUTIDE_DME_OWN = {"PANCREATITIS": (1672, 52223), "ACUTE KIDNEY INJURY": (1080, 150299),
                       "OPTIC ISCHAEMIC NEUROPATHY": (869, None), "BLINDNESS": (471, 40183),
                       "PANCREATITIS ACUTE": (437, 22022), "RENAL FAILURE": (355, 132016),
                       "ANAPHYLACTIC REACTION": (212, 54207), "ANGIOEDEMA": (127, 43561),
                       "RHABDOMYOLYSIS": (126, 41077),
                       "DRUG-INDUCED LIVER INJURY": (110, 30439), "DEAFNESS": (100, 25852),
                       "INTESTINAL PERFORATION": (57, 11087), "ANAPHYLACTIC SHOCK": (56, 25287),
                       "PULMONARY HYPERTENSION": (49, 20628), "FEBRILE NEUTROPENIA": (46, 65354),
                       "HEPATIC FAILURE": (45, 29828), "ACUTE HEPATIC FAILURE": (37, 13422)}
SEMAGLUTIDE = [(r, n, a) for r, (n, a) in SEMAGLUTIDE_DME_OWN.items()] + [
    ("WEIGHT LOSS POOR", 1552, None), ("PRODUCT COMMUNICATION ISSUE", 1016, None)]
# Recorded. The 36 of the other 45 designated medical events that semaglutide's direct count named. That count came back
# full (999 terms); the other 9 had no reports with semaglutide.
SEMAGLUTIDE_DME_DIRECT = {
    "PULMONARY FIBROSIS": 33, "PANCYTOPENIA": 28, "PROGRESSIVE MULTIFOCAL LEUKOENCEPHALOPATHY": 28,
    "OEDEMATOUS PANCREATITIS": 26, "DEAFNESS NEUROSENSORY": 22, "AUTOIMMUNE HEPATITIS": 20, "HEPATIC NECROSIS": 18,
    "IMMUNE THROMBOCYTOPENIA": 18, "PULMONARY ARTERIAL HYPERTENSION": 17, "STEVENS-JOHNSON SYNDROME": 16,
    "DRUG REACTION WITH EOSINOPHILIA AND SYSTEMIC SYMPTOMS": 15, "VENTRICULAR FIBRILLATION": 13,
    "HAEMOLYTIC ANAEMIA": 12, "SUDDEN HEARING LOSS": 12, "AGRANULOCYTOSIS": 11, "ERYTHEMA MULTIFORME": 11,
    "AUTOIMMUNE PANCREATITIS": 8, "SUDDEN VISUAL LOSS": 7, "BONE MARROW FAILURE": 6, "AZOTAEMIA": 5,
    "NEUTROPENIC COLITIS": 5, "APLASTIC ANAEMIA": 4, "DEAFNESS PERMANENT": 4, "SUDDEN CARDIAC DEATH": 4,
    "THROMBOTIC THROMBOCYTOPENIC PURPURA": 4, "DERMATITIS EXFOLIATIVE": 3, "PRODUCT CONTAMINATION MICROBIAL": 3,
    "ANAPHYLACTOID REACTION": 2, "AUTOIMMUNE HAEMOLYTIC ANAEMIA": 2, "DERMATITIS EXFOLIATIVE GENERALISED": 2,
    "HAEMOLYSIS": 2, "TOXIC EPIDERMAL NECROLYSIS": 2, "ANAPHYLACTOID SHOCK": 1, "DEAFNESS TRANSITORY": 1,
    "HEPATITIS FULMINANT": 1, "TORSADE DE POINTES": 1}
SEMAGLUTIDE_ABSENT = ["APLASIA PURE RED CELL", "GRANULOCYTOPENIA", "HEPATIC INFARCTION", "ISCHAEMIC PANCREATITIS",
                      "NEUTROPENIC INFECTION", "NEUTROPENIC SEPSIS", "REYE^S SYNDROME", "TOXIC OPTIC NEUROPATHY",
                      "TRANSMISSION OF AN INFECTIOUS AGENT VIA PRODUCT"]


def sizes(own_terms, own_cutoff):
    return {"own_terms": str(own_terms), "own_cutoff": str(own_cutoff), "all_terms": "999",
            "all_cutoff": str(ALL_CUTOFF)}


class NetZetaris:
    """Answers the safety net's queries with fixed rows, by what the SQL reads. direct(url) gives a direct count's
    rows from the openFDA URL its REST table was registered with."""
    def __init__(self, own, size, direct=lambda url: [], fail=()):
        self.own, self.size, self.direct, self.fail = own, size, direct, fail
        self.tables, self.sql, self.purposes = {}, [], []

    def ensure(self, sql, purpose):
        self.tables[sql.split()[4]] = sql.split('endpoint "')[1].split('"')[0]
        return True

    def run(self, sql, purpose, **kw):
        self.sql.append(sql)
        self.purposes.append(purpose)
        if any(f in purpose for f in self.fail):
            raise ZetarisError("HTTP 400: REST API call failed")
        if "a.reaction IS NULL" in sql:
            rows, qid = self.own, "q-own"
        elif "own_terms" in sql:
            return QueryResult("q-size", sql, list(self.size), [list(self.size.values())])
        else:
            table = next(n for n in self.tables if f"openfda_rest.{n} " in sql)
            rows, qid = self.direct(urllib.parse.unquote(self.tables[table])), "q-" + table[-6:]
        return QueryResult(qid, sql, ["reaction", "reports", "all_reports"],
                           [[r, str(n), None if a is None else str(a)] for r, n, a in rows])


def section(z, drug, signals=(), passing=(), queue=(), label=None, severity=None):
    raw = DataClerk(z).serious_terms(drug)
    return raw, assemble(raw, list(signals), list(passing), list(queue), label or {}, severity)


SECTION_NAMES = ("designated_medical_events", "missed_serious_terms", "pregnancy_and_newborn")


def by_name(sec):
    return {i["reaction"]: i for name in SECTION_NAMES for i in sec[name]}


def where(sec, reaction):
    return [name for name in SECTION_NAMES if any(i["reaction"] == reaction for i in sec[name])]


def serious(counts: dict) -> dict:
    """Severity rows shaped like DataClerk.seriousness(), from {reaction: (serious, reports)}."""
    return {r: {"serious": s, "death": 0, "serious_share": round(s / n, 3), "death_share": 0.0}
            for r, (s, n) in counts.items()}


def test_zuranolone_breast_milk_and_neonatal_terms_are_caught_with_no_openfda_call():
    z = NetZetaris(ZURANOLONE, sizes(461, 1))
    raw, sec = section(z, "zuranolone")
    t = by_name(sec)
    milk, neonatal = t["EXPOSURE VIA BREAST MILK"], t["SOMNOLENCE NEONATAL"]
    assert (milk["reports"], milk["all_drug_reports"], milk["screen_status"]) == (22, None, "not_screened")
    assert (neonatal["reports"], neonatal["screen_status"]) == (8, "not_screened")
    assert "outside the all-drugs top 999 (smallest count 9,059)" in milk["screen_detail"]
    # Pregnancy and newborn terms have their own section, the exposure term included.
    assert where(sec, "EXPOSURE VIA BREAST MILK") == where(sec, "SOMNOLENCE NEONATAL") == ["pregnancy_and_newborn"]
    assert where(sec, "ACUTE KIDNEY INJURY") == ["designated_medical_events"]
    assert "fewer than 3 reports" in t["ACUTE KIDNEY INJURY"]["screen_detail"]
    # A complete own list holds every term, so nothing is registered and no openFDA call is made.
    assert z.tables == {} and raw["direct"] == [] and sec["openfda"]["requests"] == 0
    assert sec["lists"]["own_full"] is False and sec["note"] == NOTE
    assert where(sec, "POOR FEEDING INFANT") == ["pregnancy_and_newborn"]
    reports = [i["reports"] for i in sec["pregnancy_and_newborn"]]
    assert reports == sorted(reports, reverse=True)  # most-reported first
    # With no serious counts, no missed serious term is listed, and the section says why.
    assert sec["missed_serious_terms"] == [] and any("serious counts were not available" in x for x in sec["limits"])


def empagliflozin_direct(url):
    if f'{REACTION_FIELD}:"' in url:  # searched by exact name, so the designated medical events
        return EMPAGLIFLOZIN_DME + CO_REPORTED
    return EMPAGLIFLOZIN_WORDS + CO_REPORTED


def test_empagliflozin_ketoacidosis_and_fourniers_gangrene_are_missed_serious_terms():
    # Serious counts recorded read-only from Zetaris on 25 Oct (DataClerk.seriousness).
    severity = serious({"EUGLYCAEMIC DIABETIC KETOACIDOSIS": (2234, 2273), "FOURNIER^S GANGRENE": (1202, 1207)})
    z = NetZetaris(EMPAGLIFLOZIN, sizes(999, 32), empagliflozin_direct)
    raw, sec = section(z, "empagliflozin", severity=severity)
    t = by_name(sec)
    for r, n, share in (("EUGLYCAEMIC DIABETIC KETOACIDOSIS", 2273, 0.983), ("FOURNIER^S GANGRENE", 1207, 0.996)):
        assert r not in DESIGNATED_MEDICAL_EVENTS and where(sec, r) == ["missed_serious_terms"]
        assert (t[r]["reports"], t[r]["serious_share"], t[r]["screen_status"]) == (n, share, "not_screened")
    assert [i["reaction"] for i in sec["missed_serious_terms"]][:2] == ["EUGLYCAEMIC DIABETIC KETOACIDOSIS",
                                                                        "FOURNIER^S GANGRENE"]
    # Designated medical events below the drug's own cutoff come from the direct count, with their all-drugs count.
    sjs = t["STEVENS-JOHNSON SYNDROME"]
    assert (sjs["reports"], sjs["all_drug_reports"]) == (23, 21989) and sjs["count_from"].startswith("direct openFDA")
    assert "outside the drug's own top 999 (smallest count 32)" in sjs["screen_detail"]
    assert "outside the all-drugs" not in sjs["screen_detail"]
    assert where(sec, "SEPSIS NEONATAL") == ["pregnancy_and_newborn"]
    # The own list's count is kept for a term both lists have, and co-reported terms are left out.
    assert t["MATERNAL EXPOSURE DURING PREGNANCY"]["count_from"] == "drug's own list"
    assert "NAUSEA" not in t and "DIARRHOEA" not in t
    # One designated-medical-event count and one word search, both through the app's drug search.
    urls = [urllib.parse.unquote(u) for u in z.tables.values()]
    search = urllib.parse.unquote(drug_search("empagliflozin"))
    assert len(urls) == 2 and all(u.startswith(f"https://api.fda.gov/drug/event.json?search={search}+AND+(")
                                  and u.endswith(f"&count={REACTION_FIELD}&limit=999") for u in urls)
    dme_url, words_url = urls
    assert 'patient.reaction.reactionmeddrapt.exact:"STEVENS-JOHNSON SYNDROME"' in dme_url
    assert 'reactionmeddrapt.exact:"ACUTE KIDNEY INJURY"' not in dme_url  # in the own list already
    assert 'patient.reaction.reactionmeddrapt:"BREAST MILK"' in words_url
    assert sec["openfda"] == {**sec["openfda"], "requests": 4, "registered_now": 2, "direct_reads": 2}


def semaglutide_direct(url):
    """The 45-term count comes back full; the re-count of its 9 absent terms with its anchor names only the anchor's
    report."""
    filler = [(f"MADE UP TERM {i}", 1, None) for i in range(999)]
    if "ACUTE KIDNEY INJURY" in url:
        raise AssertionError("an own-list term was counted again")
    if "PULMONARY FIBROSIS" in url:
        named = [(r, n, None) for r, n in SEMAGLUTIDE_DME_DIRECT.items()]
        return (named + filler)[:COUNT_LIMIT]
    if "ANAPHYLACTOID SHOCK" in url:
        return [("ANAPHYLACTOID SHOCK", 1, None)] + filler[:14]
    return [("PREGNANCY", 21, 19965)]


def test_semaglutide_optic_ischaemic_neuropathy_is_caught_by_the_designated_medical_events():
    z = NetZetaris([(r, n, a) for r, n, a in SEMAGLUTIDE], sizes(999, 34), semaglutide_direct)
    raw, sec = section(z, "semaglutide")
    t = by_name(sec)
    ion = t["OPTIC ISCHAEMIC NEUROPATHY"]
    assert where(sec, "OPTIC ISCHAEMIC NEUROPATHY") == ["designated_medical_events"] and ion["reports"] == 869
    assert ion["screen_status"] == "not_screened" and ion["count_from"] == "drug's own list"
    assert "PRODUCT COMMUNICATION ISSUE" not in t  # administrative, and no serious counts here anyway


def test_a_full_direct_count_recounts_only_its_absent_terms_with_an_anchor():
    z = NetZetaris([(r, n, a) for r, n, a in SEMAGLUTIDE], sizes(999, 34), semaglutide_direct)
    raw, sec = section(z, "semaglutide")
    first, again, words = raw["direct"]
    assert len(first["values"]) == 45 and len(first["rows"]) == COUNT_LIMIT
    assert again["values"] == SEMAGLUTIDE_ABSENT and again["anchor"] == "ANAPHYLACTOID SHOCK"
    url = urllib.parse.unquote(list(z.tables.values())[1])
    assert 'reactionmeddrapt.exact:"ANAPHYLACTOID SHOCK"' in url and "PULMONARY FIBROSIS" not in url
    # openFDA rejects the ^, so REYE^S SYNDROME is searched as a phrase of its words.
    assert 'patient.reaction.reactionmeddrapt:"REYE S SYNDROME"' in url and "^" not in url
    t = by_name(sec)
    assert t["ANAPHYLACTOID SHOCK"]["reports"] == 1 and "made up" not in " ".join(t).lower()
    assert not any(r in t for r in SEMAGLUTIDE_ABSENT)
    # Every absent term was settled by the re-count, so no limit says a count may be missing.
    assert not any("still have" in x or "no count this run" in x for x in sec["limits"])
    assert sec["openfda"]["direct_reads"] == 3


def test_an_unsettled_full_count_says_which_terms_may_be_missing():
    def direct(url):
        if "ANAPHYLACTOID SHOCK" in url and "PULMONARY FIBROSIS" not in url:
            raise AssertionError("not reached")
        return semaglutide_direct(url)
    z = NetZetaris([(r, n, a) for r, n, a in SEMAGLUTIDE], sizes(999, 34), direct, fail=("9 designated",))
    raw, sec = section(z, "semaglutide")
    assert "error" in raw["direct"][1]
    assert any("have no count this run" in x and "TOXIC OPTIC NEUROPATHY" in x for x in sec["limits"])
    assert any("may each still have 1 or fewer reports" in x and "REYE^S SYNDROME" in x for x in sec["limits"])


def test_a_term_the_agents_assessed_points_to_its_queue_item_and_is_not_repeated():
    z = NetZetaris(ZURANOLONE, sizes(461, 1))
    signals = [Signal("MATERNAL EXPOSURE DURING PREGNANCY", a=5, b=1, c=87040, d=1, prr=0.77, chi2=0.2)]
    queue = [{"reaction": "SOMNOLENCE NEONATAL", "workflow_status": "reviewed"}]
    label = {"adverse_reactions": "Somnolence was common.", "effective_time": "20260101"}  # made up
    _, sec = section(z, "zuranolone", signals, [], queue, label)
    t = by_name(sec)
    assert [i["reaction"] for name in SECTION_NAMES for i in sec[name]].count("SOMNOLENCE NEONATAL") == 1
    item = t["SOMNOLENCE NEONATAL"]
    assert item["screen_status"] == "in_review_queue" and "workflow status reviewed" in item["screen_detail"]
    assert "label_status" not in item
    below = t["MATERNAL EXPOSURE DURING PREGNANCY"]
    assert below["screen_status"] == "below_screen" and "PRR 0.77, chi-squared 0.2" in below["screen_detail"]
    assert t["EXPOSURE VIA BREAST MILK"]["label_status"].startswith("Not named in any section searched.")
    assert where(sec, "SOMNOLENCE NEONATAL") == ["pregnancy_and_newborn"]  # still listed, pointing to the queue


def test_a_caret_name_is_found_on_a_label_that_writes_an_apostrophe():
    # Empagliflozin's chosen label writes "Fournier's gangrene" (recorded 25 Oct); this sentence is made up around it.
    from app.data.safety_net import label_status
    label = {"warnings_and_cautions": "Necrotizing fasciitis of the perineum (Fournier\u2019s gangrene) has occurred.",
             "effective_time": "20260101"}
    assert label_status("FOURNIER^S GANGRENE", label).startswith("Named in sections that can support coverage")
    assert label_status("FOURNIER^S GANGRENE", {**label, "warnings_and_cautions": "Fournier's gangrene."}).startswith(
        "Named in sections")
    assert label_status("REYE^S SYNDROME", label).startswith("Not named in any section searched.")
    assert label_status("REYE^S SYNDROME", {}) == "No current label was found."


def test_a_failed_direct_count_degrades_and_keeps_the_own_list_terms():
    class Tracer:
        def __init__(self):
            self.events = []

        def event(self, agent, kind, **data):
            self.events.append((kind, data))
    from concurrent.futures import Future
    z = NetZetaris(EMPAGLIFLOZIN, sizes(999, 32), empagliflozin_direct, fail=("pregnancy and newborn words",))
    job, tracer = Future(), Tracer()
    job.set_result(DataClerk(z).serious_terms("empagliflozin"))
    sec = collect(job, 1, tracer, [], [], [], {}, serious({"FOURNIER^S GANGRENE": (1202, 1207)}))
    assert sec["status"] == "done" and where(sec, "FOURNIER^S GANGRENE") == ["missed_serious_terms"]
    assert "SEPSIS NEONATAL" not in by_name(sec)
    assert any("failed" in x and "pregnancy and newborn words" in x for x in sec["limits"])
    assert [d["step"] for k, d in tracer.events if k == "degraded"] == ["safety net direct count"]


def test_a_failed_or_unfinished_safety_net_never_stops_the_run():
    from concurrent.futures import Future

    class Tracer:
        def __init__(self):
            self.events = []

        def event(self, agent, kind, **data):
            self.events.append((kind, data))
    failing, tracer = Future(), Tracer()
    failing.set_exception(ZetarisError("HTTP 500"))
    sec = collect(failing, 1, tracer, [], [], [], {})
    assert sec["status"].startswith("failed") and sec["term_count"] == 0 and sec["note"] == NOTE
    assert all(sec[name] == [] for name in SECTION_NAMES)
    assert collect(Future(), 0.01, tracer, [], [], [], {})["status"] == "not finished"
    assert [d["step"] for k, d in tracer.events if k == "degraded"] == ["safety net", "safety net"]


def test_the_term_lists_and_patterns():
    assert len(DESIGNATED_MEDICAL_EVENTS) == 62 == len(set(DESIGNATED_MEDICAL_EVENTS))
    assert all(t == t.upper() and "'" not in t for t in DESIGNATED_MEDICAL_EVENTS)
    assert "REYE^S SYNDROME" in DESIGNATED_MEDICAL_EVENTS
    for r in ("SOMNOLENCE NEONATAL", "EXPOSURE VIA BREAST MILK", "POOR FEEDING INFANT", "PLACENTA PRAEVIA",
              "PREMATURE LABOUR", "FOETAL DISTRESS SYNDROME", "LOW BIRTH WEIGHT BABY"):
        assert pregnancy_or_newborn(r), r
    for r in ("FOETOR HEPATICUS", "PREMATURE EJACULATION", "PERINATAL DEPRESSION", "INFANTILE SPASMS"):
        assert not pregnancy_or_newborn(r), r
    # The SQL uses the same pattern, escaped as a Spark string, and the designated medical events by exact name.
    sql = safety_net_sql("zuranolone")
    assert "RLIKE '\\\\b(PREGNANCY|" in sql and "'REYE^S SYNDROME'" in sql and "a.reaction IS NULL" in sql
    assert re.search(PREGNANCY_NEWBORN, "RASH NEONATAL")


def test_direct_count_urls_are_encoded_and_chunked_within_the_limit():
    clause = urllib.parse.unquote(any_reaction(["REYE^S SYNDROME", "STEVENS-JOHNSON SYNDROME"]))
    assert clause == ('(patient.reaction.reactionmeddrapt:"REYE S SYNDROME" OR '
                      'patient.reaction.reactionmeddrapt.exact:"STEVENS-JOHNSON SYNDROME")')
    assert all(c not in any_reaction(list(DESIGNATED_MEDICAL_EVENTS)) for c in "\"' ^()")
    chunks = term_chunks("semaglutide", list(DESIGNATED_MEDICAL_EVENTS))
    assert [t for c in chunks for t in c] == list(DESIGNATED_MEDICAL_EVENTS) and len(chunks) == 2
    assert all(len(count_url(f"{drug_search('semaglutide')}+AND+{any_reaction(c)}", REACTION_FIELD, COUNT_LIMIT))
               <= URL_LIMIT for c in chunks)


# A whole run with a fake Data Clerk and model, to show the safety net never reaches the queue, its ranking or a prompt.
class RunClerk:
    label_choice = {"rule": "test label"}

    def __init__(self, net=None):
        self.net = net
        self.rows = [Signal("FULL BLOOD COUNT ABNORMAL", a=1754, b=174950, c=20000, d=19800000, prr=9.9, chi2=9000.0),
                     Signal("PANCREATITIS", a=800, b=175904, c=10000, d=19800000, prr=9.0, chi2=6000.0)]

    def register_drug(self, drug):
        return {}

    def totals(self, drug):
        return {"drug_reports": 176704, "all_reports": 20000000, "data_last_updated": "2026-07-30", "query_id": "q-t"}

    def signals(self, drug):
        return QueryResult("q-s", "", [], []), self.rows

    def label(self, drug):
        return "q-l", {"adverse_reactions": "Pancreatitis was reported.", "effective_time": "20260804"}  # made up

    def combination_products(self, drug, reports):
        return None, None

    def seriousness(self, drug):
        return None, {}

    def scope(self, drug):
        return QueryResult("q-sc", "", [], []), {"drug_terms": 461, "drug_cutoff": 1, "all_terms": 999,
                                                 "all_cutoff": 9059}

    def recheck(self, drug, reactions, agent="reviewer"):
        return QueryResult("q-r", "", [], []), {s.reaction: s for s in self.rows if s.reaction in reactions}

    def co_drugs(self, drug, reaction, limit=100):
        raise ZetarisError("not in this test")

    def serious_terms(self, drug):
        if self.net is None:
            raise ZetarisError("HTTP 500: Zetaris is down")
        return self.net


class RunLLM:
    """Classifies every table row as review_next and accepts every finding; keeps every prompt."""
    def __init__(self, tracer):
        self.tracer, self.prompts = tracer, []

    def chat_json(self, agent, model, messages, **kw):
        user = messages[-1]["content"]
        self.prompts += [m["content"] for m in messages]
        if agent == "reviewer":
            names = [s.reaction for s in RunClerk().rows if f'"reaction": "{s.reaction}"' in user]
            return {"verdicts": [{"reaction": r, "decision": "accept", "reason": "ok"} for r in names], "missing": []}
        if "picked" in messages[0]["content"]:
            return {"picked": []}
        rows = [line.split(" | ") for line in user.splitlines() if line.count(" | ") == 7
                and not line.startswith("reaction")]
        return {"findings": [{"reaction": r[0], "a": int(r[1]), "prr": float(r[2]), "context": "clinical_event",
                              "label_coverage": "not_found", "review_priority": "review_next", "reasoning": "x",
                              "next_check": "y", "evidence": ["q-s"]} for r in rows], "summary": ""}


def run(tmp_path, monkeypatch, net):
    from app.config import Settings
    from app.orchestration import pipeline
    llms = []
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda settings, tracer: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: RunClerk(net))
    monkeypatch.setattr(pipeline, "NightshiftClient", lambda settings, tracer: llms.append(RunLLM(tracer)) or llms[-1])
    monkeypatch.setattr(pipeline, "SOURCE_ITEMS", 0)
    settings = Settings(zetaris_url="z", zetaris_key="k", zetaris_org="1", meterless_url="m", meterless_token="t",
                        meterless_app="vigil", analyst_model="a", reviewer_model="r", source_timeout=20,
                        model_timeout=90, model_stream=True, max_retries=0, reviewer_rounds=1, parallel=2,
                        run_budget=600, sample_mode=False, logs_dir=tmp_path, world_path=tmp_path / "world.json")
    dossier = pipeline.investigate({"drug": "zuranolone"}, settings, pipeline.Tracer(tmp_path, echo=False))
    return dossier, [p for llm in llms for p in llm.prompts]


def net_raw():
    """The safety net's raw counts for the run, with terms outside the screen and PANCREATITIS, which is in it (its
    count here is made up to match the fake screen)."""
    z = NetZetaris(ZURANOLONE[:9] + [("PANCREATITIS", 800, 10800)], sizes(461, 1))
    return DataClerk(z).serious_terms("zuranolone")


def test_a_whole_run_never_promotes_safety_net_terms(tmp_path, monkeypatch):
    dossier, prompts = run(tmp_path / "with", monkeypatch, net_raw())
    baseline, _ = run(tmp_path / "without", monkeypatch, {"own": [], "sizes": sizes(461, 1), "direct": [],
                                                          "query_ids": []})
    net, queue = dossier["safety_net"], dossier["review_queue"]
    names = {q["reaction"] for q in queue}
    assert names == {"FULL BLOOD COUNT ABNORMAL", "PANCREATITIS"}
    assert "SOMNOLENCE NEONATAL" not in names and "EXPOSURE VIA BREAST MILK" not in names
    assert not any("SOMNOLENCE NEONATAL" in p or "BREAST MILK" in p or "FEELING DRUNK" in p for p in prompts)
    # Same queue, in the same order, with the same priorities, as a run whose safety net is empty.
    strip = lambda q: [(i["reaction"], i["review_priority"], i["workflow_status"]) for i in q]  # noqa: E731
    assert strip(queue) == strip(baseline["review_queue"])
    t = by_name(net)
    assert t["SOMNOLENCE NEONATAL"]["screen_status"] == "not_screened"
    assert t["PANCREATITIS"]["screen_status"] == "in_review_queue" and "label_status" not in t["PANCREATITIS"]
    assert dossier["counts"]["safety_net_terms"] == net["term_count"] == len(by_name(net)) > 0
    assert dossier["counts"]["review_next"] == baseline["counts"]["review_next"]
    assert set(net["query_ids"]) <= set(dossier["evidence_queries"]) | {"q-own", "q-size"}


def test_a_whole_run_degrades_when_the_safety_net_query_fails(tmp_path, monkeypatch):
    dossier, _ = run(tmp_path, monkeypatch, None)
    assert dossier["safety_net"]["status"].startswith("failed: HTTP 500")
    assert any(d["step"] == "safety net" for d in dossier["degraded_steps"])
    assert dossier["counts"]["safety_net_terms"] == 0 and len(dossier["review_queue"]) == 2


def test_missed_serious_terms_are_those_mostly_serious_outside_the_screen_most_reported_first():
    # Bryan's rule of 25 Oct. Made-up rows (reaction, reports with the drug, all-drug reports or None if outside the
    # all-drugs top 999), and made-up serious counts.
    own = [("GASTROINTESTINAL HYPOMOTILITY", 100, None), ("FOOD CRAVING", 750, None), ("HALF SERIOUS TERM", 200, None),
           ("SMALL SERIOUS TERM", 50, None), ("SCREENED SERIOUS TERM", 300, 50000), ("THIN SERIOUS TERM", 2, 50000),
           ("PRODUCT DOSE OMISSION ISSUE", 100, None), ("NO SERIOUS COUNT TERM", 80, None),
           ("PANCREATITIS", 400, None), ("SOMNOLENCE NEONATAL", 8, None)]
    severity = serious({"GASTROINTESTINAL HYPOMOTILITY": (99, 100), "FOOD CRAVING": (108, 750),
                        "HALF SERIOUS TERM": (100, 200), "SMALL SERIOUS TERM": (50, 50),
                        "SCREENED SERIOUS TERM": (300, 300), "THIN SERIOUS TERM": (2, 2),
                        "PRODUCT DOSE OMISSION ISSUE": (90, 100), "PANCREATITIS": (390, 400),
                        "SOMNOLENCE NEONATAL": (1, 8)})
    _, sec = section(NetZetaris(own, sizes(461, 1)), "zuranolone", severity=severity)
    missed = [i["reaction"] for i in sec["missed_serious_terms"]]
    # More than half serious and outside the screen (by a cap or the 3-report floor), most-reported first, no cap.
    assert missed == ["GASTROINTESTINAL HYPOMOTILITY", "SMALL SERIOUS TERM", "THIN SERIOUS TERM"]
    assert by_name(sec)["GASTROINTESTINAL HYPOMOTILITY"]["serious_share"] == 0.99
    # Exactly half is not more than half, a screened term is not missed, and a mostly non-serious term is out.
    assert "HALF SERIOUS TERM" not in missed and "SCREENED SERIOUS TERM" not in missed and "FOOD CRAVING" not in missed
    # Designated medical events and pregnancy terms keep their own sections, whatever their serious share.
    assert where(sec, "PANCREATITIS") == ["designated_medical_events"]
    assert where(sec, "SOMNOLENCE NEONATAL") == ["pregnancy_and_newborn"]
    # Nothing is dropped without a count, and the threshold is shown.
    assert sec["left_out"] == {"non_clinical": 1, "serious_share_unknown": 1}
    assert any("1 serious terms outside the screen are left out as non-clinical" in x for x in sec["limits"])
    assert any("1 terms outside the screen have no serious count" in x for x in sec["limits"])
    assert sec["serious_threshold"] == 0.5 and "more than 50%" in sec["groups"]["missed_serious"]
