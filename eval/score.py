"""Score Vigil runs against the gold set, and measure agreement between repeated runs.

Reads only what the app wrote: logs/trace-<run>.jsonl (the Analyst's round-1 findings) and
logs/dossier-<run>.json (the final, Reviewer-reviewed findings). Ambiguous gold rows are excluded
from accuracy and counted separately.

  python -I eval/score.py <run_id> [<run_id> ...]
"""
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
# v2 (23 Oct) matches the two-field drug search and the label choice; v1 (22 Oct) is kept for comparison.
GOLD = Path(__file__).resolve().parent / "gold_v2.jsonl"


def load_gold(path: Path = GOLD) -> dict:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {(r["drug"], r["reaction"]): r for r in rows}


def load_run(run_id: str, logs: Path = LOGS) -> dict:
    """Round-1 Analyst classifications and the final outcome per reaction for one run."""
    dossier = json.loads((logs / f"dossier-{run_id}.json").read_text(encoding="utf-8"))
    round1 = {}
    for line in (logs / f"trace-{run_id}.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["event"] == "findings" and e.get("round") == 1:
            round1 = {f["reaction"]: f for f in e["findings"]}
    final, open_items = {}, Counter()
    if "review_queue" in dossier:  # decision contract v2: one queue with a workflow status per reaction
        status_map = {"reviewed": "accepted", "unresolved": "unresolved", "not_reviewed": "not_reviewed"}
        for q in dossier["review_queue"]:
            if q["workflow_status"] in status_map:
                final[q["reaction"]] = {**q, "status": status_map[q["workflow_status"]]}
            else:
                open_items[q["workflow_status"]] += 1  # pending or failed: never classified
    else:  # v1 dossiers
        for status, key in (("accepted", "findings"), ("excluded", "excluded_by_judge"),
                            ("not_reviewed", "not_reviewed_by_judge")):
            for f in dossier.get(key, []):
                final[f["reaction"]] = {**f, "status": status}
        open_items["failed"] = len(dossier.get("not_classified", []))
    return {"run_id": run_id, "drug": dossier["drug"], "round1": round1, "final": final,
            "open_items": dict(open_items), "rounds": dossier.get("rounds", [])}


def score_run(run: dict, gold: dict) -> dict:
    drug = run["drug"]
    g = {r: row for (d, r), row in gold.items() if d == drug}
    clear = {r for r, row in g.items() if not row["ambiguous"]}

    def acc(preds: dict) -> dict:
        scored = [r for r in preds if r in clear]
        right = [r for r in scored if preds[r] == g[r]["gold"]]
        return {"scored": len(scored), "correct": len(right),
                "accuracy": round(len(right) / len(scored), 3) if scored else None}

    r1 = {r: f["classification"] for r, f in run["round1"].items()}
    accepted = {r: f["classification"] for r, f in run["final"].items() if f["status"] == "accepted"}

    # What the Reviewer loop did to each clear gold item the Analyst classified in round 1.
    effect = Counter()
    for r in clear & set(r1):
        ok1 = r1[r] == g[r]["gold"]
        f = run["final"].get(r)
        if f is None:
            effect["dropped"] += 1
        elif f["status"] == "excluded":
            effect["caught_wrong" if not ok1 else "rejected_correct"] += 1
        elif f["status"] == "unresolved":
            effect["unresolved_was_wrong" if not ok1 else "unresolved_was_correct"] += 1
        elif f["status"] == "not_reviewed":
            effect["not_reviewed"] += 1
        else:
            ok2 = f["classification"] == g[r]["gold"]
            effect[{(True, True): "kept_correct", (False, True): "fixed", (True, False): "broken",
                    (False, False): "kept_wrong"}[(ok1, ok2)]] += 1
    added = [r for r in accepted if r not in r1]  # reactions the Reviewer asked for as "missing"

    by_who = defaultdict(Counter)
    for r, f in run["final"].items():
        if f["status"] == "accepted" and r in clear:
            # Runs before the 23 Oct rename say "hunter" for the Analyst.
            by_who[{"hunter": "analyst"}.get(f.get("decided_by", "analyst"), f.get("decided_by", "analyst"))]["correct" if f["classification"] == g[r]["gold"] else "wrong"] += 1

    new = [r for r, c in accepted.items() if c == "possible_new_signal" and r in clear]
    # Priority (v2 runs): what the gold set says about the reactions sent to the analyst as "review next".
    review_next = [r for r, f in run["final"].items()
                   if f["status"] == "accepted" and f.get("review_priority") == "review_next"]
    confusion = Counter((g[r]["gold"], c) for r, c in accepted.items() if r in clear)
    return {
        "run_id": run["run_id"], "drug": drug, "gold_rows": len(g), "gold_clear": len(clear),
        "round1": acc(r1), "final": acc(accepted),
        "reviewer_effect": dict(effect),
        "added_after_missing": {"count": len(added), **acc({r: accepted[r] for r in added})},
        "by_decider": {k: dict(v) for k, v in by_who.items()},
        "new_signal_precision": {"claimed": len(new), "gold_new": sum(g[r]["gold"] == "possible_new_signal" for r in new)},
        "review_next": {"count": len(review_next),
                        "gold": dict(Counter(g[r]["gold"] + (" (ambiguous)" if g[r]["ambiguous"] else "")
                                             if r in g else "not in gold" for r in review_next))},
        "unresolved": sorted(r for r, f in run["final"].items() if f["status"] == "unresolved"),
        "ambiguous_classified": sum(1 for r in accepted if r in g and g[r]["ambiguous"]),
        "not_in_gold": sorted(r for r in set(r1) | set(run["final"]) if r not in g),
        "open_items": run["open_items"],
        "confusion_final": {f"{a} -> {b}": n for (a, b), n in sorted(confusion.items())},
        "rounds": run["rounds"],
    }


def agreement(runs: list[dict]) -> dict:
    """Repeat-run agreement for runs of the same drug: overlap of reviewed reactions, and how often
    a reaction accepted in two runs got the same classification."""
    out = {"runs": [r["run_id"] for r in runs], "pairs": []}
    same = total = 0
    for a, b in combinations(runs, 2):
        ra, rb = set(a["final"]), set(b["final"])
        acc_a = {r: f["classification"] for r, f in a["final"].items() if f["status"] == "accepted"}
        acc_b = {r: f["classification"] for r, f in b["final"].items() if f["status"] == "accepted"}
        both = set(acc_a) & set(acc_b)
        agree = sum(acc_a[r] == acc_b[r] for r in both)
        same, total = same + agree, total + len(both)
        out["pairs"].append({"a": a["run_id"], "b": b["run_id"],
                             "reaction_overlap_jaccard": round(len(ra & rb) / len(ra | rb), 3) if ra | rb else None,
                             "accepted_in_both": len(both), "same_classification": agree,
                             "disagreements": sorted((r, acc_a[r], acc_b[r]) for r in both if acc_a[r] != acc_b[r])})
    out["classification_agreement"] = round(same / total, 3) if total else None
    return out


def summarise(scores: list[dict], agreements: list[dict], gold_name: str = GOLD.name) -> str:
    """Markdown report."""
    def tot(key):
        s = sum(x[key]["scored"] for x in scores)
        c = sum(x[key]["correct"] for x in scores)
        return f"{c}/{s} = {c / s:.0%}" if s else "n/a"

    eff = Counter()
    for x in scores:
        eff.update(x["reviewer_effect"])
    lines = ["# Vigil evaluation", "",
             f"Gold set: `eval/{gold_name}` (labelled by an AI assistant, not yet reviewed by a person; "
             f"ambiguous rows excluded from accuracy). Runs: {len(scores)}.", "",
             "| Run | Drug | Round-1 accuracy | Final accuracy | Reviewer effect | Added via 'missing' | New-signal claims (gold-confirmed) | Review next (gold) | Unresolved | Pending/failed |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for x in scores:
        r1, fi = x["round1"], x["final"]
        rn = x["review_next"]
        lines.append(f"| {x['run_id']} | {x['drug']} | {r1['correct']}/{r1['scored']} | {fi['correct']}/{fi['scored']} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(x['reviewer_effect'].items())) or '-'} | "
                     f"{x['added_after_missing']['count']} | {x['new_signal_precision']['claimed']} "
                     f"({x['new_signal_precision']['gold_new']}) | {rn['count']} "
                     f"({', '.join(f'{k} {v}' for k, v in rn['gold'].items()) or '-'}) | {len(x['unresolved'])} | "
                     f"{', '.join(f'{k} {v}' for k, v in x['open_items'].items() if v) or '-'} |")
    lines += ["", f"**Overall:** round-1 accuracy {tot('round1')}, final accuracy {tot('final')}.", "",
              "Reviewer effect across runs (clear gold items the Analyst classified in round 1): "
              + (", ".join(f"{k} {v}" for k, v in sorted(eff.items())) or "none"), "",
              "- `fixed`: wrong in round 1, right after revision. `broken`: the reverse.",
              "- `caught_wrong`: wrong in round 1 and excluded by the Reviewer. `rejected_correct`: right but excluded.",
              "- `kept_correct` / `kept_wrong`: unchanged. `dropped`: not in the final dossier.",
              "- `unresolved_was_wrong` / `unresolved_was_correct`: the dispute was closed as unresolved; "
              "this says whether the Analyst's round-1 answer had been right.",
              "- Review next (gold): reactions sent to the analyst as 'review next', by their gold category. "
              "Gold `possible_new_signal` is the supported case; other categories are unsupported escalations.", ""]
    for a in agreements:
        lines.append(f"**Repeat-run agreement** ({len(a['runs'])} runs): classification agreement "
                     f"{a['classification_agreement']}; pairs: "
                     + "; ".join(f"Jaccard {p['reaction_overlap_jaccard']}, {p['same_classification']}/{p['accepted_in_both']} same"
                                 for p in a["pairs"]))
    return "\n".join(lines) + "\n"


def main(run_ids: list[str]) -> None:
    gold = load_gold()
    runs = [load_run(r) for r in run_ids]
    scores = [score_run(r, gold) for r in runs]
    by_drug = defaultdict(list)
    for r in runs:
        by_drug[r["drug"]].append(r)
    agreements = [agreement(rs) for rs in by_drug.values() if len(rs) > 1]
    print(json.dumps({"scores": scores, "agreement": agreements}, indent=1))
    print(summarise(scores, agreements))


if __name__ == "__main__":
    main(sys.argv[1:])
