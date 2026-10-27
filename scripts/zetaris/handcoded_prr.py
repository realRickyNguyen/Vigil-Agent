"""The disproportionality screen hand-coded, with no Zetaris: fetch the four openFDA count lists in Python, join them in
dicts and compute the same 2x2 table, PRR and Yates chi-squared as signal_sql() in app/data/faers.py. Then compare
the result with the Zetaris screen recorded in samples/<drug>.json.gz.

Written on 27 Oct for docs/ZETARIS_USL.md (criterion 2a, the hand-coded comparison). Not used by the app.
It imports nothing from app/, so it is an independent check of the SQL, not a copy of it.

Run:  python -I scripts/zetaris/handcoded_prr.py montelukast
Needs a network. Makes four openFDA calls with no key (the no-key limit is about 1,000 a day).
"""
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OPENFDA = "https://api.fda.gov/drug/event.json"
REACTION = "patient.reaction.reactionmeddrapt.exact"


def get(url: str, tries: int = 3) -> dict:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1:
                raise
            print(f"retry after {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


LAST_UPDATED = set()


def counts(url: str) -> dict[str, int]:
    j = get(url)
    LAST_UPDATED.add(j["meta"]["last_updated"])
    return {r["term"]: r["count"] for r in j["results"]}


def screen(drug: str, min_a: int = 3) -> tuple[dict, dict]:
    search = urllib.parse.quote(f'(patient.drug.openfda.generic_name:"{drug}" OR '
                                f'patient.drug.activesubstance.activesubstancename:"{drug}")', safe="")
    all_reactions = counts(f"{OPENFDA}?count={REACTION}&limit=999")
    all_total = sum(counts(f"{OPENFDA}?count=serious").values())
    drug_reactions = counts(f"{OPENFDA}?search={search}&count={REACTION}&limit=999")
    drug_total = sum(counts(f"{OPENFDA}?search={search}&count=serious").values())
    out = {}
    for reaction, a in drug_reactions.items():
        if a < min_a or reaction not in all_reactions:  # the SQL's inner join drops these
            continue
        b, c = drug_total - a, all_reactions[reaction] - a
        d = all_total - drug_total - all_reactions[reaction] + a
        if c <= 0:
            continue
        n = a + b + c + d
        chi2 = n * max(abs(a * d - b * c) - n / 2, 0) ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))
        out[reaction] = {"a": a, "prr": round((a / (a + b)) / (c / (c + d)), 2), "chi2": round(chi2, 1)}
    outside = sorted(r for r in drug_reactions if r not in all_reactions)
    return out, {"drug_reactions": len(drug_reactions), "outside_all_drugs_top_999": len(outside),
                 "outside_examples": outside[:5], "drug_total": drug_total, "all_total": all_total}


def recorded(drug: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "samples" / f"{drug}.json.gz"
    doc = json.load(gzip.open(path, "rt", encoding="utf-8"))
    for q in doc["zetaris"].values():
        if q["purpose"] == f"disproportionality screen for {drug}":
            o = q["outcomes"][0]
            i = {h: n for n, h in enumerate(o["headers"])}
            first = o["rows"][0]
            return {"recorded_at": doc["recorded_at"],
                    "drug_total": int(float(first[i["a"]]) + float(first[i["b"]])),
                    "all_total": int(sum(float(first[i[k]]) for k in "abcd")),
                    "rows": {r[i["reaction"]]: {"a": int(float(r[i["a"]])), "prr": float(r[i["prr"]]),
                                                "chi2": float(r[i["chi2"]])} for r in o["rows"]}}
    raise SystemExit(f"no recorded screen for {drug}")


def main():
    drug = (sys.argv[1] if len(sys.argv) > 1 else "montelukast").lower()
    t0 = time.time()
    mine, info = screen(drug)
    secs = time.time() - t0
    rec = recorded(drug)
    z = rec["rows"]
    both = sorted(set(mine) & set(z))
    same_a = [r for r in both if mine[r]["a"] == z[r]["a"]]
    same = [r for r in same_a if mine[r]["prr"] == z[r]["prr"] and mine[r]["chi2"] == z[r]["chi2"]]
    a_diff = [abs(mine[r]["a"] - z[r]["a"]) for r in both if r not in same_a]
    prr_diff = [abs(mine[r]["prr"] - z[r]["prr"]) for r in both]
    print(json.dumps({
        "drug": drug, "hand_coded_seconds": round(secs, 1), "openfda_last_updated": sorted(LAST_UPDATED), **info,
        "zetaris_recorded_at": rec["recorded_at"], "zetaris_drug_total": rec["drug_total"],
        "zetaris_all_total": rec["all_total"],
        "hand_coded_rows": len(mine), "zetaris_rows": len(z),
        "in_both": len(both), "only_hand_coded": sorted(set(mine) - set(z))[:10],
        "only_zetaris": sorted(set(z) - set(mine))[:10],
        "same_a": len(same_a), "same_a_prr_chi2": len(same),
        "a_differs_by_at_most": max(a_diff, default=0), "prr_differs_by_at_most": round(max(prr_diff, default=0), 2),
        "differ_with_same_a": [{"reaction": r, "hand": mine[r], "zetaris": z[r]} for r in same_a if r not in same][:3],
    }, indent=2))


if __name__ == "__main__":
    main()
