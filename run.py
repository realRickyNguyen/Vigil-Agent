"""Black Box: run one drug-safety investigation.

  python -I run.py --input input_examples/example_1.json
  python -I run.py --drug montelukast

Needs Zetaris (with scripts/zetaris/openfda_baseline.sql Part A loaded) and Meterless Nightshift running.
Writes logs/trace-<run_id>.jsonl and logs/dossier-<run_id>.json."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings  # noqa: E402
from app.orchestration.pipeline import investigate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="JSON file with {\"drug\": ...}")
    src.add_argument("--drug")
    args = ap.parse_args()

    settings = get_settings()
    if settings.sample_mode:
        print("SAMPLE_MODE is not implemented yet; set SAMPLE_MODE=false.", file=sys.stderr)
        return 2
    request = json.loads(Path(args.input).read_text()) if args.input else {"drug": args.drug}
    d = investigate(request, settings)

    print(f"\n{d['drug']}: {d['data']['drug_reports']} reports, {d['screen']['passing_evans']} reactions pass the screen")
    for f in d["findings"]:
        print(f"  [{f['classification']}] {f['reaction']}  a={f['a']} PRR={f['prr']}")
    for f in d["excluded_by_judge"]:
        print(f"  [excluded] {f['reaction']}: {f['judge'][:100]}")
    for f in d["not_reviewed_by_judge"]:
        print(f"  [not reviewed] [{f['classification']}] {f['reaction']}")
    print(f"\nRounds: {d['rounds']}")
    print(f"Dossier: logs/dossier-{d['run_id']}.json   Trace: logs/{d['trace']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
