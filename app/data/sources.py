"""Report sources for review-next items, meaning where the reports come from and who sent them, against the drug's
usual mix. Code, not a model, and context only. The flags never drop, demote or rank an item.

Bryan's FAERS checks (03_Project_context/Data_exploration_notes.md, sections 5c and 5d) found that one source counted
many times inflates many top signals. The same patient is re-filed by many companies, mostly outside the US: 1,270
Canadian montelukast FULL BLOOD COUNT ABNORMAL reports come down to at most 638 patients. Lawyer reports come in
litigation waves, and they inflate known risks rather than invent them. There are three flags.
- One country holds 60% or more of the reports with a known country, 30 or more points above the drug's usual
  share from that country (some drugs are reported almost only from one country).
- Lawyers filed 20% or more of the reports that say who reported.
- Physicians, pharmacists and other health professionals filed under 50% of them.
Each needs 10 reports to be judged. The reporter checks are "unknown" when under half the item's reports say who
reported. Only about 28% of 2026 Q2 reports do, so a recent signal's reporter mix rests on a shrinking minority."""

from fractions import Fraction

# Thresholds are exact fractions and are compared with exact shares of the counts, so 0.7 - 0.4 is 30 points
# and 4,999 of 25,000 is under 20%. The rounded shares are for display only.
COUNTRY_SHARE = Fraction(6, 10)
COUNTRY_ABOVE_USUAL = Fraction(3, 10)
LAWYER_SHARE = Fraction(2, 10)
HEALTH_PROFESSIONAL_SHARE = Fraction(5, 10)
MIN_REPORTS = 10
MIN_KNOWN_REPORTER = Fraction(5, 10)
# Review-next items checked per run. Each costs two to four openFDA reads (registering a table fetches once, and each
# read of it fetches again), and the drug's usual mix as much again per run. The no-key limit is about 1,000 a day.
# 0 turns the check off.
SOURCE_ITEMS = 10
# openFDA primarysource.qualification codes.
QUALIFICATION = {"1": "physician", "2": "pharmacist", "3": "other health professional", "4": "lawyer",
                 "5": "consumer"}
HEALTH_PROFESSIONALS = ("1", "2", "3")
LAWYER = "4"


def share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None  # 4 places, so 96.54% still prints as 97%


def reporter_mix(counts: dict[str, int], reports: int) -> dict:
    """Who reported, as shares of the reports that say, and how many of all reports say."""
    known = sum(counts.values())
    return {"known": known, "known_share": share(known, reports),
            "lawyer_share": share(counts.get(LAWYER, 0), known),
            "health_professional_share": share(sum(counts.get(q, 0) for q in HEALTH_PROFESSIONALS), known),
            "by_type": {QUALIFICATION.get(q, q): n for q, n in sorted(counts.items(), key=lambda kv: -kv[1])}}


def country_check(item: dict[str, int], usual: dict[str, int] | None) -> dict:
    known = sum(item.values())
    if known < MIN_REPORTS:
        return {"known": known, "flag": "unknown", "why": f"fewer than {MIN_REPORTS} reports name a country"}
    top, n = max(item.items(), key=lambda kv: kv[1])
    out = {"known": known, "top": top, "top_reports": n, "share": share(n, known)}
    if not usual:
        return {**out, "usual_share": None, "flag": "unknown", "why": "the drug's usual country mix is not available"}
    usual_known = sum(usual.values())
    out["usual_share"] = share(usual.get(top, 0), usual_known)
    exact = Fraction(n, known)
    out["flag"] = bool(usual_known) and exact >= COUNTRY_SHARE and         exact - Fraction(usual.get(top, 0), usual_known) >= COUNTRY_ABOVE_USUAL
    return out


def reporter_check(item: dict[str, int], reports: int, usual: dict[str, int] | None, usual_reports: int | None) -> dict:
    mix = reporter_mix(item, reports)
    known = mix["known"]
    if known < MIN_REPORTS or not reports or Fraction(known, reports) < MIN_KNOWN_REPORTER:
        mix.update(lawyer_flag="unknown", health_professional_flag="unknown",
                   why=f"only {known} of {reports} reports say who reported")
    else:
        professionals = sum(item.get(q, 0) for q in HEALTH_PROFESSIONALS)
        mix.update(lawyer_flag=Fraction(item.get(LAWYER, 0), known) >= LAWYER_SHARE,
                   health_professional_flag=Fraction(professionals, known) < HEALTH_PROFESSIONAL_SHARE)
    if usual is not None and usual_reports:
        u = reporter_mix(usual, usual_reports)
        mix["usual"] = {k: u[k] for k in ("known_share", "lawyer_share", "health_professional_share")}
    return mix


def assess_sources(reports: int, item_country: dict | None, item_reporter: dict | None, usual_country: dict | None,
                   usual_reporter: dict | None, drug_reports: int | None) -> dict:
    """The three flags for one item. A part whose counts are missing (the query failed) is "unknown"."""
    country = country_check(item_country, usual_country) if item_country is not None else {
        "flag": "unknown", "why": "country counts are not available"}
    reporter = reporter_check(item_reporter, reports, usual_reporter, drug_reports) if item_reporter is not None else {
        "lawyer_flag": "unknown", "health_professional_flag": "unknown", "why": "reporter counts are not available"}
    flags = {"one_country": country["flag"], "lawyer_reports": reporter["lawyer_flag"],
             "few_health_professionals": reporter["health_professional_flag"]}
    out = {"reports": reports, "country": country, "reporter": reporter, "flags": flags,
           "raised": [k for k, v in flags.items() if v is True]}
    out["summary"] = summary(out)
    return out


def check(clerk, drug: str, reaction: str, usual, a: int | None = None) -> dict:
    """The check for one review-next item. usual is a Future of clerk.report_sources(drug), run once per drug and
    shared by every item. a, the item's report count from the screen, stands in if the total query fails."""
    qids, item = clerk.report_sources(drug, reaction)
    usual_qids, mix = usual.result()
    ev = assess_sources(item["reports"] or a or 0, item["country"], item["reporter"], mix["country"], mix["reporter"],
                        mix["reports"])
    return {"reaction": reaction, **ev, "query_ids": qids + usual_qids}


def compact(ev: dict) -> dict:
    """What the Reviewer sees, which is the flags, the plain summary and the query IDs behind them."""
    return {k: ev[k] for k in ("flags", "summary", "query_ids") if k in ev}


def pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def summary(ev: dict) -> str:
    """Plain sentences for the Reviewer's prompt and the dossier, from the numbers only."""
    c, r, parts = ev["country"], ev["reporter"], []
    if "top" in c:
        parts.append(f"{pct(c['share'])} of the {c['known']:,} reports with a known country come from {c['top']}"
                     + (f", against {pct(c['usual_share'])} of the drug's reports" if c.get("usual_share") is not None
                        else "") + (" (one country)." if c["flag"] is True else "."))
    else:
        parts.append(f"The country check is unknown, as {c['why']}.")
    if r["lawyer_flag"] == "unknown":
        parts.append(f"The reporter checks are unknown, as {r['why']}.")
    else:
        usual = r.get("usual") or {}
        parts.append(f"Of the {r['known']:,} reports that say who reported, {pct(r['lawyer_share'])} came from lawyers"
                     + (f" (drug's usual {pct(usual.get('lawyer_share'))})" if usual else "")
                     + f" and {pct(r['health_professional_share'])} from health professionals"
                     + (f" (usual {pct(usual.get('health_professional_share'))})" if usual else "") + ".")
    named = {"one_country": "one country holds most reports", "lawyer_reports": "lawyer-reported",
             "few_health_professionals": "few health-professional reports"}
    if ev["raised"]:
        parts.append(f"Flagged for {', '.join(named[k] for k in ev['raised'])}. This is context only. Re-filed copies "
                     f"of the same case, or litigation, can inflate the count, which does not make the pattern false.")
    return " ".join(parts)
