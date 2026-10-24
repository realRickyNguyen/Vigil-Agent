"""One investigation: the Data Clerk gathers evidence in Zetaris, the Analyst classifies, the Reviewer
checks, the Analyst revises on rejection (bounded rounds), and the accepted findings become the dossier."""
import json
from dataclasses import asdict
from datetime import datetime, timezone

from app.adapters.meterless import NightshiftClient
from app.adapters.zetaris import ZetarisClient
from app.agents.analyst import Analyst, screen_table
from app.agents.reviewer import Reviewer
from app.agents.reviewer import failed as failed_checks
from app.config import Settings
from app.data.faers import DataClerk, validate_drug
from app.engines.world_model import WorldModel
from app.schemas import CAVEAT, STATUS, Finding, Verdict
from app.tracing import Tracer

# Passing rows shown to the Analyst, strongest evidence (chi2) first. 60 rows made the pick call run past
# Nightshift's deadline about half the time; for montelukast the top 30 by chi2 still include the
# neuropsychiatric terms that rank in the 40s by PRR.
SCREEN_ROWS = 30

NOT_YET_CHECKED = [
    "Confounding by indication beyond the Analyst's judgement (no stratified counts yet)",
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
    tracer.event("orchestrator", "run_start", request=request, analyst_model=settings.analyst_model,
                 reviewer_model=settings.reviewer_model)

    zetaris = ZetarisClient(settings, tracer)
    llm = NightshiftClient(settings, tracer)
    clerk = DataClerk(zetaris)
    analyst = Analyst(llm, settings.analyst_model, settings.parallel)
    reviewer = Reviewer(llm, settings.reviewer_model, clerk, settings.parallel)

    # Evidence, all through Zetaris.
    created = clerk.register_drug(drug)
    tracer.event("data_clerk", "sources_ready", drug=drug, created_now=created)
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
    tracer.event("data_clerk", "evidence_ready", screened=len(signals), passing=len(passing),
                 label_sections=[k for k in label if k not in ("effective_time", "set_id")],
                 label_effective=label.get("effective_time"), evidence_ids=sorted(ctx["evidence_ids"]))

    # Analyst <-> Reviewer loop. Accepted findings are settled and never re-done; each round only handles the
    # Reviewer's rejections and missing reactions nobody has attempted yet. A dispute that cannot be settled
    # ends as "unresolved" rather than being accepted when the rounds run out.
    names = {s.reaction for s in passing}
    findings, summary = analyst.run(ctx)
    tracer.event("analyst", "findings", round=1, findings=[f.to_dict() for f in findings], summary=summary)
    attempted = {f.reaction for f in findings} | set(ctx.get("unclassified", []))
    state: dict = {}  # reaction -> {"finding", "verdict", "status", "history"}
    rounds, new_missing = [], []
    for rnd in range(1, settings.reviewer_rounds + 2):
        verdicts, missing, reviewer_summary = reviewer.review(ctx, findings, attempted)
        by = {v.reaction: v for v in verdicts}
        retry = []
        for f in findings:
            v = by[f.reaction]
            entry = state.setdefault(f.reaction, {"history": []})
            status, note = settle(f, v, entry["history"])
            entry["history"].append({"round": rnd, "claim": dict(zip(("label_coverage", "context", "review_priority"),
                                                                       f.key())),
                                     "decision": v.decision, "reason": v.reason, "objection": v.objection})
            entry.update(finding=f, verdict=v, status=status, note=note)
            if status == "rejected":
                retry.append(f)
            elif status == "unresolved" and note:
                tracer.event("orchestrator", "dispute_unresolved", reaction=f.reaction, reason=note)
        new_missing = [m for m in missing if m["reaction"] in names and m["reaction"] not in attempted]
        tracer.event("reviewer", "verdicts", round=rnd, verdicts=[asdict(v) for v in verdicts], missing=new_missing,
                     ignored_missing=[m for m in missing if m not in new_missing], summary=reviewer_summary)
        rounds.append({"round": rnd, "reviewed": len(findings), "rejected": len(retry),
                       "unresolved": sum(by[f.reaction].decision == "unresolved" for f in findings),
                       "missing": len(new_missing)})
        if (not retry and not new_missing) or rnd > settings.reviewer_rounds:
            break
        feedback = {"rejected": [{"reaction": f.reaction, "reason": by[f.reaction].reason,
                                  "objection": by[f.reaction].objection} for f in retry],
                    "missing": new_missing}
        tracer.event("orchestrator", "retry", round=rnd + 1, reason="reviewer rejected or found missing items",
                     feedback=feedback)
        attempted |= {m["reaction"] for m in new_missing}
        new_missing = []
        findings, summary = analyst.revise(ctx, retry, feedback)
        attempted |= set(ctx.get("unclassified", []))
        tracer.event("analyst", "findings", round=rnd + 1, findings=[f.to_dict() for f in findings], summary=summary)

    for r, entry in state.items():
        if entry["status"] == "rejected":  # rounds ran out with the Reviewer's objection unanswered
            entry.update(status="unresolved", note="review rounds ran out before the Reviewer's objection was settled")
            tracer.event("orchestrator", "dispute_unresolved", reaction=r, reason=entry["note"])
    queue = review_queue(state, passing, new_missing, ctx.get("unclassified", []))
    # The namespace keeps the project's first name (Black Box) so earlier runs' state still loads.
    world = remember(WorldModel("black-box", settings.world_path), drug, label, queue, tracer.run_id,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"))
    tracer.event("world_model", "remembered", **world)
    counts = {"reactions_screened": len(signals), "passing_evans": len(passing),
              "shown_to_analyst": ctx["screen_shown"], "picked_by_analyst": len(ctx.get("picked", [])),
              "assessed": len(state), "decided_by_rule": sum(e["finding"].decided_by == "rule" for e in state.values()),
              **{s: sum(q["workflow_status"] == s for q in queue) for s in STATUS},
              "review_next": sum(q.get("review_priority") == "review_next" and q["workflow_status"] == "reviewed"
                                 for q in queue)}

    queries, degraded, setup_warnings = {}, [], []
    model_calls = {"total": 0, "with_memory_injected": 0, "with_reasoning_scaffold": 0, "without_receipt": 0,
                   "served_by_other_model": 0}
    with tracer.path.open(encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if e["event"] == "zetaris_query" and e["query_id"] in ctx["evidence_ids"]:
                queries[e["query_id"]] = {"purpose": e["purpose"], "sql": e["sql"]}
            if e["event"] == "degraded":
                degraded.append({"agent": e["agent"], "step": e["step"], "fallback": e["fallback"]})
            if e["event"] == "llm_call":
                ns = e.get("nightshift")
                model_calls["total"] += 1
                model_calls["without_receipt"] += ns is None
                model_calls["with_memory_injected"] += bool(ns and ns["hmem_injected"])
                model_calls["with_reasoning_scaffold"] += bool(ns and ns["scaffold_active"])
                model_calls["served_by_other_model"] += bool(e.get("served_by") and e["served_by"] != e.get("model"))
            if e["event"] == "nightshift_warning" and e["warning"] not in setup_warnings:
                setup_warnings.append(e["warning"])

    dossier = {
        "run_id": tracer.run_id,
        "drug": drug,
        "data": {"source": "openFDA FAERS and drug label via Zetaris", **{k: totals[k] for k in
                 ("drug_reports", "all_reports", "data_last_updated")},
                 "label_effective": label.get("effective_time"), "label_set_id": label.get("set_id")},
        "counts": counts,
        "review_queue": queue,
        "degraded_steps": degraded,
        # Nightshift steps our app did not ask for, counted from each call's receipt (see nightshift_steps).
        "model_calls": model_calls,
        # Empty when Nightshift is set up as the README says; see setup_problems in the adapter.
        "nightshift_warnings": setup_warnings,
        "analyst_summary": summary,
        "rounds": rounds,
        "world_model": world,
        "untested_factors": NOT_YET_CHECKED,
        "caveat": CAVEAT,
        "evidence_queries": queries,
        "trace": str(tracer.path.name),
    }
    out = settings.logs_dir / f"dossier-{tracer.run_id}.json"
    out.write_text(json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
    tracer.event("orchestrator", "run_end", counts=counts, dossier=out.name)
    return dossier


def settle(f: Finding, v: Verdict, history: list[dict]) -> tuple[str, str]:
    """Workflow status for a finding after the Reviewer's verdict, and a note when a dispute is closed.
    A rejection of a claim the Reviewer already rejected once means the two agents are going round in
    circles, so the dispute is closed as unresolved instead of being re-asked."""
    if v.decision == "accept":
        return "reviewed", ""
    if v.decision == "unreviewed":
        return "not_reviewed", ""
    if v.decision == "unresolved":
        return "unresolved", ""
    claim = dict(zip(("label_coverage", "context", "review_priority"), f.key()))
    if any(h["decision"] == "reject" and h["claim"] == claim for h in history):
        return "unresolved", "the Analyst returned to an answer the Reviewer had already rejected"
    return "rejected", ""


SETTLED = ("reviewed", "unresolved")


def remember(world: WorldModel, drug: str, label: dict, queue: list[dict], run_id: str, at: str) -> dict:
    """Record this run's label version and settled verdicts in the World Model. A label version that
    differs from the last run's supersedes it, which reopens every earlier verdict that rested on it:
    those come back in `reopened` so the analyst knows which past answers need a second look."""
    source = {"kind": "openfda-label-via-zetaris", "at": at, "runId": run_id}
    entity = world.upsert_entity(type="drug", name=drug, source=source)
    version = {"set_id": label.get("set_id"), "effective_time": label.get("effective_time")}
    before = {d["key"] for d in world.decisions(status="reopened", about=entity["id"])}
    fact = world.assert_fact(about=entity["id"], predicate="label_version", value=version, source=source)
    reopened = [{"reaction": d["value"]["reaction"], "earlier_run": d["value"]["run_id"],
                 "earlier_label_coverage": d["value"].get("label_coverage"),
                 "earlier_review_priority": d["value"].get("review_priority")}
                for d in world.decisions(status="reopened", about=entity["id"]) if d["key"] not in before]
    recorded = 0
    for q in queue:
        if q["workflow_status"] in SETTLED:
            world.record_decision(
                key=f"{entity['id']}|{q['reaction']}", about=entity["id"], depends_on=[fact["id"]], source=source,
                value={"reaction": q["reaction"], "run_id": run_id, "workflow_status": q["workflow_status"],
                       **{k: q.get(k) for k in ("label_coverage", "context", "review_priority")}})
            recorded += 1
    return {"label_fact": fact["id"], "label_version": version, "decisions_recorded": recorded,
            "reopened": reopened}


PRIORITY_ORDER = {"review_next": 0, "insufficient_evidence": 1, "lower_priority": 2, None: 3}
STATUS_ORDER = {"unresolved": 0, "reviewed": 1, "not_reviewed": 2, "pending": 3, "failed": 4}


def review_queue(state: dict, passing: list, pending: list[dict], failed: list[str]) -> list[dict]:
    """The analyst's queue: every assessed reaction with its priority, objection and next check, plus
    reactions that were named for review but never reached, ranked review_next first."""
    stats = {s.reaction: s for s in passing}
    queue = []
    for r, e in state.items():
        f, v = e["finding"], e["verdict"]
        item = {**f.to_dict(), "chi2": stats[r].chi2 if r in stats else None,
                "workflow_status": e["status"], "reviewer": v.reason, "status_note": e.get("note", ""),
                "strongest_objection": v.objection, "next_check": v.next_check or f.next_check,
                "history": e["history"]}
        bad = failed_checks(v.checks)
        if e["status"] == "unresolved" and bad and item["review_priority"] == "review_next":
            # A claim that code has shown to be wrong must not head the queue as "review next".
            item["review_priority"] = "insufficient_evidence"
            item["status_note"] = " ".join(x for x in (item["status_note"], "Ranked below review_next because the "
                                                       "Analyst's last claim failed code checks: " + "; ".join(bad)) if x)
        queue.append(item)
    for m in pending:
        s = stats.get(m["reaction"])
        queue.append({"reaction": m["reaction"], "a": s.a if s else None, "prr": s.prr if s else None,
                      "chi2": s.chi2 if s else None, "workflow_status": "pending", "review_priority": None,
                      "status_note": f"named by the Reviewer in the last round, not reached: {m.get('why', '')}"})
    for r in sorted(set(failed) - set(state)):
        s = stats.get(r)
        queue.append({"reaction": r, "a": s.a if s else None, "prr": s.prr if s else None,
                      "chi2": s.chi2 if s else None, "workflow_status": "failed", "review_priority": None,
                      "status_note": "the Analyst could not classify it: its model calls failed after every fallback, "
                                     "or its reply left this reaction out"})
    queue.sort(key=lambda q: (PRIORITY_ORDER.get(q.get("review_priority"), 3),
                              STATUS_ORDER.get(q["workflow_status"], 5), -(q.get("chi2") or 0)))
    return queue
