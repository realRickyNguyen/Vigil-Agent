"""One investigation: the Data Clerk gathers evidence in Zetaris, the Analyst classifies, the Reviewer
checks, the Analyst revises on rejection (bounded rounds). The Skeptic then tests the strongest
review_next findings against co-reported drugs, and challenged ones go back through the Reviewer.
The result is the dossier."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone

from app.adapters.meterless import NightshiftClient
from app.adapters.zetaris import ZetarisClient
from app.agents.analyst import Analyst, screen_table
from app.agents.reviewer import Reviewer
from app.agents.skeptic import Skeptic, compact
from app.config import Settings
from app.data.faers import DataClerk, validate_drug
from app.engines.world_model import WorldModel
from app.schemas import CAVEAT, STATUS, Finding, Verdict
from app.tracing import Tracer

# Passing rows shown to the Analyst, strongest evidence (chi2) first. 60 rows made the pick call run past
# Nightshift's deadline about half the time; for montelukast the top 30 by chi2 still include the
# neuropsychiatric terms that rank in the 40s by PRR.
SCREEN_ROWS = 30
# Seconds a step needs, at least, to start within the run budget (one round of single-reaction calls, or one
# review of the Skeptic's challenges). Below that the step is skipped and says so.
REVISION_NEEDS = 120
CHALLENGE_NEEDS = 90

NOT_YET_CHECKED = [
    "Confounding by indication beyond the Analyst's judgement (no stratified counts yet)",
    "Reporter type, e.g. lawyer-driven reporting",
    "Reporting spikes over time (notoriety bias)",
    "Co-reported drugs beyond the Skeptic's top co-drugs, items beyond its top review_next items, and "
    "interactions among three or more drugs. Adjustment is for one co-drug at a time",
    "Recalls and contaminated batches",
    "Every report naming the drug (generic name or active substance) is counted, whether or not it was the "
    "suspect drug",
    "The baseline holds the 999 most-reported reactions; rarer reactions are not screened",
]


def investigate(request: dict, settings: Settings, tracer: Tracer | None = None) -> dict:
    tracer = tracer or Tracer(settings.logs_dir)
    started = time.monotonic()
    left = lambda: settings.run_budget - (time.monotonic() - started)  # noqa: E731
    skipped = []  # steps the run budget did not leave time for
    drug = validate_drug(request.get("drug", ""))
    tracer.event("orchestrator", "run_start", request=request, analyst_model=settings.analyst_model,
                 reviewer_model=settings.reviewer_model)

    zetaris = ZetarisClient(settings, tracer)
    llm = NightshiftClient(settings, tracer)
    clerk = DataClerk(zetaris)
    analyst = Analyst(llm, settings.analyst_model, settings.parallel, settings.analyst_top, settings.analyst_extra)
    reviewer = Reviewer(llm, settings.reviewer_model, clerk, settings.parallel)
    skeptic = Skeptic(clerk, settings.skeptic_co_drugs)

    # Evidence, all through Zetaris.
    created = clerk.register_drug(drug)
    tracer.event("data_clerk", "sources_ready", drug=drug, created_now=created)
    totals = clerk.totals(drug)
    # Independent Zetaris queries side by side; the Zetaris client keeps no state between calls.
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(clerk.signals, drug), pool.submit(clerk.label, drug),
                pool.submit(clerk.combination_products, drug, totals["drug_reports"]),
                pool.submit(clerk.seriousness, drug)]
        (screen_res, signals), (label_qid, label), (combo_res, combination), (severity_res, severity) = \
            [j.result() for j in jobs]
    passing = sorted((s for s in signals if s.prr >= 2 and s.chi2 >= 4), key=lambda s: -s.chi2)
    ctx = {
        "drug": drug, "totals": totals, "label": label, "label_qid": label_qid, "passing": passing,
        "label_choice": clerk.label_choice, "combination": combination, "seriousness": severity,
        "screen_qid": screen_res.query_id, "screen_passing": len(passing),
        "screen_shown": min(SCREEN_ROWS, len(passing)),
        "screen_table": screen_table(passing, SCREEN_ROWS),
        "evidence_ids": {totals["query_id"], screen_res.query_id} | ({label_qid} if label_qid else set())
                        | ({combo_res.query_id} if combo_res else set())
                        | ({severity_res.query_id} if severity_res else set()),
    }
    if severity_res is None:
        tracer.event("data_clerk", "degraded", step="seriousness", fallback="no serious or death shares this run")
    tracer.event("data_clerk", "evidence_ready", screened=len(signals), passing=len(passing),
                 label_sections=[k for k in label if k not in ("effective_time", "set_id")],
                 label_effective=label.get("effective_time"), label_choice=clerk.label_choice,
                 combination=combination, evidence_ids=sorted(ctx["evidence_ids"]))

    # Analyst <-> Reviewer loop. Accepted findings are settled and never re-done; each round only handles the
    # Reviewer's rejections and missing reactions nobody has attempted yet. A dispute that cannot be settled
    # ends as "unresolved" rather than being accepted when the rounds run out.
    names = {s.reaction for s in passing}
    findings, summary = analyst.run(ctx)
    tracer.event("analyst", "findings", round=1, findings=[f.to_dict() for f in findings], summary=summary)
    attempted = {f.reaction for f in findings} | set(ctx.get("unclassified", []))
    state: dict = {}  # reaction -> {"finding", "verdict", "status", "history"}
    rounds, new_missing = [], []
    background, prefetch = ThreadPoolExecutor(max_workers=1), None
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
        if rnd == 1 and settings.skeptic_items:
            # The Skeptic's targets are findings the Reviewer has just accepted, which the revision round does
            # not touch, so its Zetaris checks run while the Analyst revises the rejected ones.
            targets = skeptic_targets(ctx, state, settings.skeptic_items)
            prefetch = background.submit(lambda t=targets: (t, skeptic_checks(ctx, skeptic, t)))
        if (not retry and not new_missing) or rnd > settings.reviewer_rounds:
            break
        if left() < REVISION_NEEDS:
            skipped.append(f"revision round {rnd + 1}")
            tracer.event("orchestrator", "budget_stop", step=f"revision round {rnd + 1}", seconds_left=round(left()),
                         rejected=[f.reaction for f in retry], missing=[m["reaction"] for m in new_missing])
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
        if entry["status"] == "rejected":  # rounds or time ran out with the Reviewer's objection unanswered
            entry.update(status="unresolved", note=(
                "the run's time budget ran out before the Analyst could answer the Reviewer's objection" if skipped
                else "review rounds ran out before the Reviewer's objection was settled"))
            tracer.event("orchestrator", "dispute_unresolved", reaction=r, reason=entry["note"])
    skeptic_counts = {"checked": 0, "challenged": 0, "challenge_not_reviewed": 0, "priority_changed": 0}
    if prefetch is not None:
        prefetched = prefetch.result()  # skeptic.check catches its own Zetaris errors
        review = left() >= CHALLENGE_NEEDS
        if not review:
            skipped.append("skeptic challenge review")
            tracer.event("orchestrator", "budget_stop", step="skeptic challenge review", seconds_left=round(left()))
        skeptic_counts = skeptic_round(ctx, state, skeptic, reviewer, analyst, tracer, settings.skeptic_items,
                                       prefetched=prefetched, review=review)
    background.shutdown()
    if skeptic_counts["challenged"]:
        rounds.append({"round": "skeptic", **skeptic_counts})
    queue = review_queue(state, passing, new_missing, ctx.get("unclassified", []), ctx.get("skeptic"), severity)
    # The namespace keeps the project's first name (Black Box) so earlier runs' state still loads.
    world = remember(WorldModel("black-box", settings.world_path), drug, label, queue, tracer.run_id,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"))
    tracer.event("world_model", "remembered", **world)
    counts = {"reactions_screened": len(signals), "passing_evans": len(passing),
              "shown_to_analyst": ctx["screen_shown"], "picked_by_analyst": len(ctx.get("picked", [])),
              "chosen_by_analyst": len((ctx.get("selection") or {}).get("chosen", [])),
              "assessed": len(state), "decided_by_rule": sum(e["finding"].decided_by == "rule" for e in state.values()),
              **{s: sum(q["workflow_status"] == s for q in queue) for s in STATUS},
              "review_next": sum(q.get("review_priority") == "review_next" and q["workflow_status"] == "reviewed"
                                 for q in queue),
              **{f"skeptic_{k}": v for k, v in skeptic_counts.items()}}

    queries, degraded = {}, []
    model_calls = {"total": 0, "with_memory_injected": 0, "with_reasoning_scaffold": 0, "without_receipt": 0}
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

    dossier = {
        "run_id": tracer.run_id,
        "drug": drug,
        "data": {"source": "openFDA FAERS and drug label via Zetaris", **{k: totals[k] for k in
                 ("drug_reports", "all_reports", "data_last_updated")},
                 "label_effective": label.get("effective_time"), "label_set_id": label.get("set_id"),
                 "label_choice": clerk.label_choice, "combination_products": combination,
                 "seriousness_query": severity_res.query_id if severity_res else None,
                 "seriousness_note": "serious and death shares are of each reaction's reports; the flags describe "
                                     "the whole report, which may list other reactions"},
        "counts": counts,
        "review_queue": queue,
        "degraded_steps": degraded,
        # Nightshift steps our app did not ask for, counted from each call's receipt (see nightshift_steps).
        "model_calls": model_calls,
        "analyst_summary": summary,
        "rounds": rounds,
        "run_time": {"seconds": round(time.monotonic() - started), "budget_seconds": settings.run_budget,
                     "skipped_for_time": skipped},
        "world_model": world,
        "untested_factors": NOT_YET_CHECKED,
        "caveat": CAVEAT,
        "evidence_queries": queries,
        "trace": str(tracer.path.name),
    }
    out = settings.logs_dir / f"dossier-{tracer.run_id}.json"
    out.write_text(json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
    tracer.event("orchestrator", "run_end", counts=counts, dossier=out.name, seconds=dossier["run_time"]["seconds"],
                 skipped_for_time=skipped)
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


def skeptic_targets(ctx: dict, state: dict, top: int) -> list[str]:
    """The strongest (by chi2) review_next findings the Reviewer has accepted."""
    stats = {s.reaction: s for s in ctx["passing"]}
    return sorted((r for r, e in state.items()
                   if e["status"] == "reviewed" and e["finding"].review_priority == "review_next"),
                  key=lambda r: -(stats[r].chi2 if r in stats else 0))[:top]


def skeptic_checks(ctx: dict, skeptic: Skeptic, picked: list[str]) -> list[dict]:
    """The Skeptic's Zetaris checks for each target. The items are independent, so they run side by side
    (about 80 s each on 23 Oct). No model calls, so this can overlap the revision round."""
    stats = {s.reaction: s for s in ctx["passing"]}
    with ThreadPoolExecutor(max_workers=max(1, len(picked))) as pool:
        return list(pool.map(lambda r: skeptic.check(ctx["drug"], r, stats[r].prr if r in stats else None), picked))


def skeptic_round(ctx: dict, state: dict, skeptic: Skeptic, reviewer: Reviewer, analyst: Analyst, tracer: Tracer,
                  top: int, prefetched: tuple[list[str], list[dict]] | None = None, review: bool = True) -> dict:
    """The Skeptic checks the strongest accepted review_next findings against their co-reported drugs.
    A challenged finding goes back to the Reviewer with that evidence. If the Reviewer rejects it, the Analyst
    gets one revision and the Reviewer one more look; a dispute still open after that ends as unresolved.
    If the Reviewer's look at the challenge itself fails (model call failed), the round-1 verdict stands and the
    item says the challenge was not reviewed, rather than losing its earlier review.
    prefetched: (targets, checks) already run, from the end of the first review round. review=False when the
    run's time budget leaves no room for the challenge review: the evidence is still recorded."""
    picked, checks = prefetched if prefetched is not None else (None, None)
    if picked is None:
        picked = skeptic_targets(ctx, state, top)
        checks = skeptic_checks(ctx, skeptic, picked)
    ctx["skeptic"] = {}
    for r, ev in zip(picked, checks):
        ctx["skeptic"][r] = ev
        ctx["evidence_ids"] |= set(ev["query_ids"])
        tracer.event("skeptic", "co_drug_check", reaction=r, outcome=ev["outcome"],
                     challenge_reasons=ev.get("challenge_reasons", []), summary=ev.get("summary"),
                     pairs=ev["pairs"], query_ids=ev["query_ids"], error=ev.get("error"))
    # Only items still accepted as review_next: a prefetched target could have changed since round 1.
    challenged = [state[r]["finding"] for r in picked if ctx["skeptic"][r]["outcome"] == "challenged"
                  and state[r]["status"] == "reviewed" and state[r]["finding"].review_priority == "review_next"]
    counts = {"checked": len(picked), "challenged": len(challenged), "challenge_not_reviewed": 0,
              "priority_changed": 0}
    if not challenged:
        return counts
    if not review:
        for f in challenged:
            state[f.reaction]["note"] = ("the Skeptic challenged it, but the run's time budget ran out before the "
                                         "Reviewer could look at the challenge; the round-1 verdict stands")
            tracer.event("orchestrator", "challenge_not_reviewed", reaction=f.reaction, reason=state[f.reaction]["note"])
        counts["challenge_not_reviewed"] = len(challenged)
        return counts

    before = {f.reaction: f.key() for f in challenged}
    everyone = {s.reaction for s in ctx["passing"]}  # the Reviewer names no missing reactions in this round
    findings = challenged
    for step in ("skeptic", "skeptic_revision"):
        verdicts, _, reviewer_summary = reviewer.review(ctx, findings, everyone)
        by = {v.reaction: v for v in verdicts}
        retry = []
        for f in findings:
            v, entry = by[f.reaction], state[f.reaction]
            entry["history"].append({"round": step, "claim": dict(zip(("label_coverage", "context", "review_priority"),
                                                                        f.key())),
                                     "decision": v.decision, "reason": v.reason, "objection": v.objection})
            if step == "skeptic" and v.decision == "unreviewed":
                entry["note"] = ("the Skeptic's challenge could not be reviewed (model call failed); "
                                 "the round-1 verdict stands")
                counts["challenge_not_reviewed"] += 1
                tracer.event("orchestrator", "challenge_not_reviewed", reaction=f.reaction, reason=entry["note"])
                continue
            status, note = settle(f, v, entry["history"][:-1])
            entry.update(finding=f, verdict=v, status=status, note=note)
            if status == "rejected":
                retry.append(f)
        tracer.event("reviewer", "verdicts", round=step, verdicts=[asdict(v) for v in verdicts], missing=[],
                     summary=reviewer_summary)
        if not retry or step == "skeptic_revision":
            break
        feedback = {"rejected": [{"reaction": f.reaction, "reason": by[f.reaction].reason,
                                  "objection": by[f.reaction].objection} for f in retry], "missing": []}
        tracer.event("orchestrator", "retry", round="skeptic_revision",
                     reason="the Reviewer rejected a finding after the Skeptic's co-drug check", feedback=feedback)
        findings, analyst_summary = analyst.revise(ctx, retry, feedback)
        tracer.event("analyst", "findings", round="skeptic_revision", findings=[f.to_dict() for f in findings],
                     summary=analyst_summary)
        if not findings:
            break
    for r in before:
        if state[r]["status"] == "rejected":
            state[r].update(status="unresolved", note="the Reviewer's objection after the Skeptic's check was not settled")
            tracer.event("orchestrator", "dispute_unresolved", reaction=r, reason=state[r]["note"])
    counts["priority_changed"] = sum(state[r]["finding"].key() != k for r, k in before.items())
    return counts


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


def review_queue(state: dict, passing: list, pending: list[dict], failed: list[str],
                 skeptic: dict | None = None, severity: dict | None = None) -> list[dict]:
    """The analyst's queue: every assessed reaction with its priority, objection and next check, plus
    reactions that were named for review but never reached, ranked review_next first. The serious and death
    shares are shown, not used for ranking: they describe whole reports, not the reaction."""
    stats = {s.reaction: s for s in passing}
    sev = lambda r: {"seriousness": severity[r]} if severity and r in severity else {}
    queue = []
    for r, e in state.items():
        f, v = e["finding"], e["verdict"]
        queue.append({**f.to_dict(), "chi2": stats[r].chi2 if r in stats else None, **sev(r),
                      "workflow_status": e["status"], "reviewer": v.reason, "status_note": e.get("note", ""),
                      "strongest_objection": v.objection, "next_check": v.next_check or f.next_check,
                      "history": e["history"],
                      **({"co_reported_drugs": skeptic[r]} if skeptic and r in skeptic else {})})
    for m in pending:
        s = stats.get(m["reaction"])
        queue.append({"reaction": m["reaction"], "a": s.a if s else None, "prr": s.prr if s else None,
                      "chi2": s.chi2 if s else None, **sev(m["reaction"]), "workflow_status": "pending",
                      "review_priority": None,
                      "status_note": f"named by the Reviewer in the last round, not reached: {m.get('why', '')}"})
    for r in sorted(set(failed) - set(state)):
        s = stats.get(r)
        queue.append({"reaction": r, "a": s.a if s else None, "prr": s.prr if s else None,
                      "chi2": s.chi2 if s else None, **sev(r), "workflow_status": "failed", "review_priority": None,
                      "status_note": "the Analyst's model gave no classification for it after every fallback"})
    queue.sort(key=lambda q: (PRIORITY_ORDER.get(q.get("review_priority"), 3),
                              STATUS_ORDER.get(q["workflow_status"], 5), -(q.get("chi2") or 0)))
    return queue
