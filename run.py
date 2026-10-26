"""Vigil: start the API, or run one drug-safety investigation.

  python -I run.py                                      # API on PORT (default 8000): POST /run, GET /health
  python -I run.py --input input_examples/example_1.json
  python -I run.py --drug montelukast
  python -I run.py --drug montelukast --sample           # replay the recorded run (also SAMPLE_MODE=true)
  python -I run.py --drug montelukast --record           # live run, recorded for sample mode

Needs Zetaris (with scripts/zetaris/openfda_baseline.sql Part A loaded) and Meterless Nightshift running, except in
sample mode, which replays samples/<drug>.json.gz with no service and no network (app/sample_mode.py).
Writes logs/trace-<run_id>.jsonl and logs/dossier-<run_id>.json. --record also writes samples/<drug>.json.gz and
copies the run's dossier, trace and API response, unedited, to output_examples/<drug>/."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import sample_mode  # noqa: E402
from app.config import ROOT, for_sample_mode, get_settings  # noqa: E402
from app.orchestration.pipeline import investigate  # noqa: E402
from app.server import serve, success_body, summary  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--input", help="JSON file with {\"drug\": ...}")
    src.add_argument("--drug")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")),
                    help="API port when no --input or --drug is given")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true", help="replay the drug's recorded run (sample mode)")
    mode.add_argument("--record", action="store_true", help="record this live run for sample mode")
    args = ap.parse_args()

    settings = get_settings()
    if args.sample:
        settings = for_sample_mode(settings)
    if not (args.input or args.drug):
        serve(args.port, settings)
        return 0
    request = json.loads(Path(args.input).read_text()) if args.input else {"drug": args.drug}
    if args.record:
        if settings.sample_mode:
            print("--record needs a live run; unset SAMPLE_MODE.", file=sys.stderr)
            return 2
        with sample_mode.recording(settings, request["drug"]) as rec:
            d = investigate(request, settings)
        out = ROOT / "output_examples" / sample_mode.slug(request["drug"])
        out.mkdir(parents=True, exist_ok=True)
        for name in (f"dossier-{d['run_id']}.json", d["trace"]):  # copies, never edited
            shutil.copy2(settings.logs_dir / name, out / name)
        (out / "response.json").write_text(json.dumps(success_body(d, settings, d["run_time"]["seconds"]), indent=2,
                                                      ensure_ascii=False), encoding="utf-8")
        print(f"Recorded {rec.summary['queries']} queries and {rec.summary['model_calls']} model calls to "
              f"{rec.summary['path']}; outputs in {out}")
        if d["run_time"]["skipped_for_time"]:
            print(f"Note: this run skipped {d['run_time']['skipped_for_time']} for time, so a replay may reach steps "
                  f"the recording does not have. Record again for a complete sample.")
    else:
        d = investigate(request, settings)

    print("\n" + summary(d))
    for q in d["review_queue"]:
        prio = q.get("review_priority") or "-"
        print(f"  {prio:22s} {q['workflow_status']:12s} {q['reaction']}  a={q['a']} PRR={q['prr']}"
              + (f"  [{q['label_coverage']}, {q['context']}]" if q.get("label_coverage") else ""))
        if q.get("review_priority") == "review_next" or q["workflow_status"] == "unresolved":
            print(f"      objection: {(q.get('strongest_objection') or q.get('status_note') or '-')[:140]}")
            print(f"      next check: {(q.get('next_check') or '-')[:140]}")
        cluster = q.get("reporting_cluster") or {}
        if cluster.get("needed"):
            print(f"      check the reporting cluster first: {'; '.join(cluster['reasons'])[:200]}")
        slr = q.get("since_last_run") or {}
        if slr.get("status") in ("changed", "not_settled_now") or slr.get("label_changed"):
            print(f"      since last run: {slr['status']}; {slr['why'][:160]}")
    for warning in d.get("nightshift_warnings") or []:
        print(f"\nNightshift setup warning. {warning}")
    s = (d.get("world_model") or {}).get("since_last_run") or {}
    if s.get("compared_with_runs"):
        print(f"\nWorld Model, against earlier runs: {s['changed']} changed, {s['unchanged']} unchanged, {s['new']} new, "
              f"{s['not_settled_now']} not settled now" + ("; label version changed" if s.get("label_version_changed") else ""))
        for x in s.get("earlier_review_next_not_assessed") or []:
            print(f"  earlier review next, not assessed this run: {x['reaction']} (run {x['earlier_run']})")
    print(f"\nRounds: {d['rounds']}")
    print(f"Dossier: logs/dossier-{d['run_id']}.json   Trace: logs/{d['trace']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
