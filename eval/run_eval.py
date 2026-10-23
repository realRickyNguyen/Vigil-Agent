"""Run Vigil on the gold-set drugs, then score the runs and write a report to eval/reports/.

  python -I eval/run_eval.py                                  # each gold drug once, montelukast 3 times
  python -I eval/run_eval.py --drugs metformin --repeats 2
  python -I eval/run_eval.py --score-only <run_id> [...]      # re-score existing runs, no model calls

Needs Zetaris and Nightshift running. Each run takes several minutes."""
import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.orchestration.pipeline import investigate  # noqa: E402
from eval.score import agreement, load_gold, load_run, score_run, summarise  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"


def main() -> int:
    gold = load_gold()
    drugs = sorted({d for d, _ in gold})
    ap = argparse.ArgumentParser()
    ap.add_argument("--drugs", nargs="*", default=drugs)
    ap.add_argument("--repeats", type=int, default=1, help="runs per drug")
    ap.add_argument("--repeat-drug", default="montelukast", help="extra repeats for this drug (stability)")
    ap.add_argument("--repeat-extra", type=int, default=2)
    ap.add_argument("--score-only", nargs="*")
    args = ap.parse_args()

    run_ids = list(args.score_only or [])
    if not args.score_only:
        plan = [d for d in args.drugs for _ in range(args.repeats)]
        if args.repeat_drug in args.drugs:
            plan += [args.repeat_drug] * args.repeat_extra
        settings = get_settings()
        for i, drug in enumerate(plan, 1):
            t0 = time.time()
            try:
                d = investigate({"drug": drug}, settings)
                run_ids.append(d["run_id"])
                print(f"[{i}/{len(plan)}] {drug}: {d['run_id']} in {time.time() - t0:.0f}s", flush=True)
            except Exception as e:  # one failed run must not stop the evaluation
                print(f"[{i}/{len(plan)}] {drug}: FAILED after {time.time() - t0:.0f}s: {e}", flush=True)

    runs = [load_run(r) for r in run_ids]
    scores = [score_run(r, gold) for r in runs]
    by_drug = defaultdict(list)
    for r in runs:
        by_drug[r["drug"]].append(r)
    agreements = [agreement(rs) for rs in by_drug.values() if len(rs) > 1]

    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (REPORTS / f"eval-{stamp}.json").write_text(json.dumps({"scores": scores, "agreement": agreements}, indent=1),
                                               encoding="utf-8")
    report = summarise(scores, agreements)
    (REPORTS / f"eval-{stamp}.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Report: eval/reports/eval-{stamp}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
