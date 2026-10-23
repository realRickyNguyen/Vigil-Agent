"""Skeptic: tests the strongest review_next findings against the drugs most often reported with them.
Code, not a model. For each of the top co-reported drugs it asks three questions, all from Zetaris counts:
- is the reaction also disproportionate for the co-drug itself?
- does this drug's PRR stay at 2 or above once the co-drug is adjusted for (Mantel-Haenszel, two strata)?
- do reports naming both drugs show more of the reaction than either drug alone predicts (the Omega
  interaction measure, Noren et al., Stat Med 2008)?
A challenged finding goes back to the Reviewer with this evidence. The Skeptic never changes a priority itself:
spontaneous reports show reporting patterns, and adjusting for one co-drug at a time is not full adjustment."""
import math
import re

from app.adapters.zetaris import ZetarisError
from app.data.faers import DRUG_RE, DataClerk

# Salt and ester words, so "ALBUTEROL SULFATE" and "ALBUTEROL" count as one co-drug.
SALTS = {"sodium", "disodium", "potassium", "calcium", "magnesium", "hydrochloride", "dihydrochloride", "hcl",
         "hydrobromide", "sulfate", "bisulfate", "maleate", "tartrate", "bitartrate", "besylate", "mesylate",
         "chloride", "citrate", "phosphate", "acetate", "succinate", "fumarate", "bromide", "dihydrate", "monohydrate",
         "trihydrate", "hemihydrate", "anhydrous", "propionate", "dipropionate", "furoate", "valerate",
         "xinafoate", "hyclate", "tromethamine", "benzoate", "lactate", "gluconate", "nitrate", "oxalate",
         "pamoate", "malate", "monosodium", "hemifumarate", "erbumine", "medoxomil"}
ALPHA = 0.5          # Omega shrinkage, as in Noren et al. 2008
Z975 = 1.959964      # 97.5th percentile of the standard normal, for Omega's lower 95% bound
PRR_THRESHOLD = 2.0  # the screen's PRR threshold (Evans)


def base_names(term: str) -> list[str]:
    """Ingredient names in one openFDA generic name, lower case, salt words removed. A combination
    product gives one name per ingredient. A name that is only salt words is kept whole."""
    out = []
    for part in re.split(r",| AND |/", term.upper()):
        words = part.lower().split()
        kept = [w for w in words if w not in SALTS]
        name = " ".join(kept or words)
        if name and name not in out:
            out.append(name)
    return out


def rank_co_drugs(rows: list[tuple[str, int]], drug: str, k: int) -> list[dict]:
    """The k co-drugs named on the most reports, merging salts and dropping the drug itself. The merged
    count can double-count a report that names two salts, so it only ranks; pair_counts has the real one."""
    own = set(base_names(drug)) | {drug.lower()}
    merged: dict[str, dict] = {}
    for term, reports in rows:
        for name in base_names(term):
            if name in own or any(o in name.split() or name in o.split() for o in own) or not DRUG_RE.match(name):
                continue
            m = merged.setdefault(name, {"co_drug": name, "names": [], "reports_ranked": 0})
            m["names"].append(term)
            m["reports_ranked"] += reports
    return sorted(merged.values(), key=lambda m: -m["reports_ranked"])[:k]


def two_by_two(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """PRR and Yates-corrected chi-squared, the same formulas as the screen's SQL."""
    n = a + b + c + d
    prr = (a / (a + b)) / (c / (c + d)) if a + b and c and c + d else 0.0
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    chi2 = n * max(abs(a * d - b * c) - n / 2, 0) ** 2 / denom if denom else 0.0
    return round(prr, 2), round(chi2, 1)


def pair_stats(c: dict) -> dict:
    """All three checks for one co-drug from the eight counts (see DataClerk.pair_counts)."""
    # Reports split by exposure: both drugs (11), this drug only (10), co-drug only (01), neither (00).
    cells = {"11": (c["n_xyr"], c["n_xy"]),
             "10": (c["n_xr"] - c["n_xyr"], c["n_x"] - c["n_xy"]),
             "01": (c["n_yr"] - c["n_xyr"], c["n_y"] - c["n_xy"]),
             "00": (c["n_r"] - c["n_xr"] - c["n_yr"] + c["n_xyr"], c["n"] - c["n_x"] - c["n_y"] + c["n_xy"])}
    if any(r < 0 or total <= r for r, total in cells.values()) or c["n_xyr"] == 0:
        return {"error": "counts are inconsistent or empty, so no statistic was computed"}
    (r11, n11), (r10, n10), (r01, n01), (r00, n00) = (cells[k] for k in ("11", "10", "01", "00"))

    co_prr, co_chi2 = two_by_two(c["n_yr"], c["n_y"] - c["n_yr"], c["n_r"] - c["n_yr"],
                                 c["n"] - c["n_y"] - c["n_r"] + c["n_yr"])
    # Mantel-Haenszel PRR for this drug, with reports split by whether they name the co-drug.
    num = r11 * n01 / (n11 + n01) + r10 * n00 / (n10 + n00)
    den = r01 * n11 / (n11 + n01) + r00 * n10 / (n10 + n00)
    # Omega: the rate expected with both drugs if their effects on the odds add up (no interaction).
    odds = {k: r / (total - r) for k, (r, total) in cells.items()}
    s11 = 1 - 1 / (max(odds["00"], odds["10"]) + max(odds["00"], odds["01"]) - odds["00"] + 1)
    expected = s11 * n11
    omega = math.log2((r11 + ALPHA) / (expected + ALPHA))
    omega025 = omega - Z975 / (math.log(2) * math.sqrt(r11))
    return {"share": round(r11 / c["n_xr"], 3),
            "co_drug_prr": co_prr, "co_drug_chi2": co_chi2,
            "co_drug_passes_screen": c["n_yr"] >= 3 and co_prr >= PRR_THRESHOLD and co_chi2 >= 4,
            "adjusted_prr": round(num / den, 2) if den else None,
            "rates": {k: round(r / total, 5) for k, (r, total) in cells.items()},
            "observed_both": r11, "expected_both": round(expected, 1),
            "omega": round(omega, 2), "omega025": round(omega025, 2), "possible_interaction": omega025 > 0}


def assess(pairs: list[dict]) -> dict:
    ok = [p for p in pairs if "error" not in p]
    adjusted_below = [p["co_drug"] for p in ok if p["adjusted_prr"] is not None and p["adjusted_prr"] < PRR_THRESHOLD]
    interactions = [p["co_drug"] for p in ok if p["possible_interaction"]]
    outcome = "not_checked" if not ok else "challenged" if adjusted_below or interactions else "holds"
    return {"outcome": outcome, "adjusted_below_threshold": adjusted_below, "possible_interactions": interactions}


def summary(ev: dict, drug: str, prr: float | None) -> str:
    """Plain sentences for the agents' prompts and the dossier, built from the numbers only."""
    if ev["outcome"] in ("failed", "not_checked"):
        return f"Co-reported drug check could not be completed for {ev['reaction']}."
    parts = []
    for p in ev["pairs"]:
        if "error" in p:
            parts.append(f"{p['co_drug']}: not computed ({p['error']}).")
            continue
        parts.append(
            f"{p['co_drug']} is named on {p['share']:.0%} of these reports; adjusted for it, the PRR of {drug} is "
            f"{p['adjusted_prr']} (unadjusted {prr}); {p['co_drug']}'s own PRR for this reaction is "
            f"{p['co_drug_prr']}{' and passes the screen' if p['co_drug_passes_screen'] else ''}; reports with both "
            f"drugs: {p['observed_both']} observed vs {p['expected_both']} expected without interaction "
            f"(Omega lower bound {p['omega025']}{', a possible interaction' if p['possible_interaction'] else ''}).")
    return " ".join(parts)


def compact(ev: dict) -> dict:
    """What the Reviewer and Analyst see: the outcome, the key numbers per co-drug, and the query IDs."""
    keys = ("co_drug", "query_id", "share", "co_drug_prr", "adjusted_prr", "observed_both", "expected_both",
            "omega025", "possible_interaction", "error")
    return {"outcome": ev["outcome"], "summary": ev.get("summary", ""),
            "co_drugs": [{k: p[k] for k in keys if k in p} for p in ev.get("pairs", [])]}


class Skeptic:
    name = "skeptic"

    def __init__(self, clerk: DataClerk, co_drugs: int = 3):
        self.clerk = clerk
        self.k = co_drugs

    def check(self, drug: str, reaction: str, prr: float | None) -> dict:
        ev = {"reaction": reaction, "pairs": [], "query_ids": []}
        try:
            res, rows = self.clerk.co_drugs(drug, reaction)
        except ZetarisError as e:
            return {**ev, "outcome": "failed", "error": str(e)[:200]}
        ev["query_ids"].append(res.query_id)
        ev["co_drug_query"] = res.query_id
        ev["top_co_drugs"] = rank_co_drugs(rows, drug, self.k)
        for cand in ev["top_co_drugs"]:
            try:
                res, counts = self.clerk.pair_counts(drug, reaction, cand["co_drug"])
            except ZetarisError as e:
                ev["pairs"].append({"co_drug": cand["co_drug"], "error": str(e)[:200]})
                continue
            ev["query_ids"].append(res.query_id)
            ev["pairs"].append({"co_drug": cand["co_drug"], "query_id": res.query_id, "counts": counts,
                                **pair_stats(counts)})
        ev.update(assess(ev["pairs"]))
        ev["summary"] = summary(ev, drug, prr)
        return ev
