"""One investigation: Clerk gathers evidence in Zetaris, Hunter classifies, Judge checks,
Hunter revises on rejection (bounded rounds), and the accepted findings become the dossier."""
import json
from dataclasses import asdict

from app.adapters.meterless import NightshiftClient
from app.adapters.zetaris import ZetarisClient
from app.agents.hunter import Hunter, screen_table
from app.agents.judge import Judge
from app.config import Settings
from app.data.faers import Clerk, validate_drug
from app.schemas import CAVEAT
from app.tracing import Tracer

# Passing rows shown to the Hunter, strongest evidence (chi2) first. 60 rows made the pick call run past
# Nightshift's deadline about half the time; for montelukast the top 30 by chi2 still include the
# neuropsychiatric terms that rank in the 40s by PRR.
SCREEN_ROWS = 30

NOT_YET_CHECKED = [
    "Confounding by indication beyond the Hunter's judgement (no stratified counts yet)",
    "Reporter type, e.g. lawyer-driven reporting",
    "Reporting spikes over time (notoriety bias)",
    "Co-reported drugs",
    "Recalls and contaminated batches",
    "Only reports naming the drug by generic name are counted, whether or not it was the suspect drug",
    "The baseline holds the 999 most-reported reactions; rarer reactions are not screened",
]


def investigate(request: dict, settings: Settings, tracer: Tracer | None = None) -> dict:
    tracer = tracer or Tracer(settings.logs_dir)
    drug = validate_drug(request.get("drug", ""))
    tracer.event("orchestrator", "run_start", request=request, hunter_model=settings.hunter_model,
                 judge_model=settings.judge_model)

    zetaris = ZetarisClient(settings, tracer)
    llm = NightshiftClient(settings, tracer)
    clerk = Clerk(zetaris)
    hunter = Hunter(llm, settings.hunter_model, settings.parallel)
    judge = Judge(llm, settings.judge_model, clerk, settings.parallel)

    # Evidence, all through Zetaris.
    created = clerk.register_drug(drug)
    tracer.event("clerk", "sources_ready", drug=drug, created_now=created)
    totals = clerk.totals(drug)
    screen_res, signals = clerk.signals(drug)
    passing = sorted((s for s in signals if s.prr >= 2 and s.chi2 >= 4), key=lambda s: -s.chi2)
    label_qid, label = clerk.label(drug)
    ctx = {
        "drug": drug, "totals": totals, "label": label, "label_qid": label_qid, "passing": passing,
        "screen_qid": screen_res.query_id, "screen_passing": len(passing),
        "screen_shown": min(SCREEN_ROWS, len(passing)),
        "screen_table": screen_table(passing, SCREEN_ROWS),
        "evidence_ids": {totals["query_id"], screen_res.query_id} | ({label_qid} if label_qid else set()),
    }
    tracer.event("clerk", "evidence_ready", screened=len(signals), passing=len(passing),
                 label_sections=[k for k in label if k not in ("effective_time", "set_id")],
                 label_effective=label.get("effective_time"), evidence_ids=sorted(ctx["evidence_ids"]))

    # Hunter <-> Judge loop. Accepted findings are settled and never re-classified; each round only
    # handles the Judge's rejections and missing reactions nobody has attempted yet.
    names = {s.reaction for s in passing}
    findings, summary = hunter.run(ctx)
    tracer.event("hunter", "findings", round=1, findings=[f.to_dict() for f in findings], summary=summary)
    attempted = {f.reaction for f in findings} | set(ctx.get("unclassified", []))
    settled: dict = {}
    excluded_now: dict = {}
    unreviewed: dict = {}  # passed code checks, but every model review attempt failed
    rounds = []
    for rnd in range(1, settings.judge_rounds + 2):
        verdicts, missing, judge_summary = judge.review(ctx, findings, attempted)
        by = {v.reaction: v for v in verdicts}
        rejected = [f for f in findings if by[f.reaction].decision == "reject"]
        for f in findings:
            v = by[f.reaction]
            for d in (settled, excluded_now, unreviewed):
                d.pop(f.reaction, None)
            {"accept": settled, "reject": excluded_now}.get(v.decision, unreviewed)[f.reaction] = (f, v)
        new_missing = [m for m in missing if m["reaction"] in names and m["reaction"] not in attempted]
        tracer.event("judge", "verdicts", round=rnd, verdicts=[asdict(v) for v in verdicts], missing=new_missing,
                     ignored_missing=[m for m in missing if m not in new_missing], summary=judge_summary)
        rounds.append({"round": rnd, "reviewed": len(findings), "rejected": len(rejected),
                       "missing": len(new_missing)})
        if (not rejected and not new_missing) or rnd > settings.judge_rounds:
            break
        feedback = {"rejected": [{"reaction": f.reaction, "reason": by[f.reaction].reason} for f in rejected],
                    "missing": new_missing}
        tracer.event("orchestrator", "retry", round=rnd + 1, reason="judge rejected or found missing items",
                     feedback=feedback)
        attempted |= {m["reaction"] for m in new_missing}
        findings, summary = hunter.revise(ctx, rejected, feedback)
        attempted |= set(ctx.get("unclassified", []))
        tracer.event("hunter", "findings", round=rnd + 1, findings=[f.to_dict() for f in findings], summary=summary)

    accepted = [{**f.to_dict(), "judge": v.reason} for f, v in settled.values()]
    excluded = [{**f.to_dict(), "judge": v.reason} for f, v in excluded_now.values()]
    not_reviewed = [{**f.to_dict(), "judge": v.reason} for f, v in unreviewed.values()]
    findings = [f for d in (settled, excluded_now, unreviewed) for f, _ in d.values()]

    queries, degraded = {}, []
    with tracer.path.open(encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if e["event"] == "zetaris_query" and e["query_id"] in ctx["evidence_ids"]:
                queries[e["query_id"]] = {"purpose": e["purpose"], "sql": e["sql"]}
            if e["event"] == "degraded":
                degraded.append({"agent": e["agent"], "step": e["step"], "fallback": e["fallback"]})

    dossier = {
        "run_id": tracer.run_id,
        "drug": drug,
        "data": {"source": "openFDA FAERS and drug label via Zetaris", **{k: totals[k] for k in
                 ("drug_reports", "all_reports", "data_last_updated")},
                 "label_effective": label.get("effective_time"), "label_set_id": label.get("set_id")},
        "screen": {"reactions_screened": len(signals), "passing_evans": len(passing)},
        "findings": accepted,
        "excluded_by_judge": excluded,
        "not_reviewed_by_judge": not_reviewed,
        "not_classified": sorted(set(ctx.get("unclassified", [])) - {f.reaction for f in findings}),
        "degraded_steps": degraded,
        "hunter_summary": summary,
        "rounds": rounds,
        "untested_factors": NOT_YET_CHECKED,
        "caveat": CAVEAT,
        "evidence_queries": queries,
        "trace": str(tracer.path.name),
    }
    out = settings.logs_dir / f"dossier-{tracer.run_id}.json"
    out.write_text(json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
    tracer.event("orchestrator", "run_end", accepted=len(accepted), excluded=len(excluded), dossier=out.name)
    return dossier
