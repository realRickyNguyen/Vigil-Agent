"""Vigil: start the API, or run one drug-safety investigation.

  python -I run.py                                      # API on PORT (default 8000): POST /run, GET /health
  python -I run.py --input input_examples/example_1.json
  python -I run.py --drug montelukast

Needs Zetaris (with scripts/zetaris/openfda_baseline.sql Part A loaded) and Meterless Nightshift running.
Writes logs/trace-<run_id>.jsonl and logs/dossier-<run_id>.json."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings  # noqa: E402
from app.orchestration.pipeline import investigate  # noqa: E402
from app.server import serve, summary  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--input", help="JSON file with {\"drug\": ...}")
    src.add_argument("--drug")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")),
                    help="API port when no --input or --drug is given")
    args = ap.parse_args()

    settings = get_settings()
    if not (args.input or args.drug):
        serve(args.port, settings)
        return 0
    if settings.sample_mode:
        print("SAMPLE_MODE is not implemented yet; set SAMPLE_MODE=false.", file=sys.stderr)
        return 2
    request = json.loads(Path(args.input).read_text()) if args.input else {"drug": args.drug}
    d = investigate(request, settings)

    print("\n" + summary(d))
    for q in d["review_queue"]:
        prio = q.get("review_priority") or "-"
        print(f"  {prio:22s} {q['workflow_status']:12s} {q['reaction']}  a={q['a']} PRR={q['prr']}"
              + (f"  [{q['label_coverage']}, {q['context']}]" if q.get("label_coverage") else ""))
        if q.get("review_priority") == "review_next" or q["workflow_status"] == "unresolved":
            print(f"      objection: {(q.get('strongest_objection') or q.get('status_note') or '-')[:140]}")
            print(f"      next check: {(q.get('next_check') or '-')[:140]}")
    for warning in d.get("nightshift_warnings") or []:
        print(f"\nNightshift setup warning. {warning}")
    print(f"\nRounds: {d['rounds']}")
    print(f"Dossier: logs/dossier-{d['run_id']}.json   Trace: logs/{d['trace']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
