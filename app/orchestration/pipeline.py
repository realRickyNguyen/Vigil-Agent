"""One investigation: the Data Clerk gathers evidence in Zetaris, the Analyst classifies, the Reviewer
checks, the Analyst revises on rejection (bounded rounds). The Skeptic then tests the strongest
review_next findings against co-reported drugs, and challenged ones go back through the Reviewer.
The result is the dossier."""
import copy
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

from app.adapters.meterless import NightshiftClient, Slots
from app.adapters.zetaris import ZetarisClient, ZetarisError
from app.agents.analyst import Analyst, screen_table
from app.agents.reviewer import Reviewer
from app.agents.reviewer import failed as failed_checks
from app.agents.skeptic import Skeptic, compact
from app.config import Settings
from app.data import uncertainty
from app.data.faers import DataClerk, DrugNotFound, NoCurrentLabel, scope_summary, validate_drug
from app.data.label import search, sections
from app.data.safety_net import collect as collect_safety_net
from app.data.sources import SOURCE_ITEMS
from app.data.sources import check as check_report_sources
from app.data.sources import cluster_check
from app.engines.world_model import WorldModel
from app.orchestration.manual_review import manual_review
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
# Seconds the dossier waits, at most, for report-source checks still running at the end of a run.
SOURCE_WAIT = 30
# Extra review_next findings the Skeptic checks early, in case the Reviewer turns one of its top ones down.
EARLY_EXTRA = 1
# Seconds a Skeptic check of a target the early checks missed needs to start (the checks took a median of 82 s, 24 and
# 25 Oct traces). With less left it is not run, so the Skeptic no longer carries a run past its budget.
SKEPTIC_CHECK_NEEDS = 90

NOT_YET_CHECKED = [
    "Confounding by indication beyond the Analyst's judgement (no stratified counts yet)",
    "Reporter type and country only for review-next items, as context flags. Copies of one case re-filed by many "
    "companies are not collapsed into patients",
    "Reporting spikes over time (notoriety bias)",
    "Co-reported drugs beyond the Skeptic's top co-drugs, items beyond its top review_next items, and "
    "interactions among three or more drugs. Adjustment is for one co-drug at a time",
    "Recalls and contaminated batches",
    "Every report naming the drug (generic name or active substance) is counted, whether or not it was the "
    "suspect drug",
    "Only reactions in openFDA's 999 most-reported for all drugs and in the drug's own 999 most-reported are "
    "screened (sizes and cutoffs in data.scope), and only with 3 or more reports. The safety net lists designated "
    "medical events, pregnancy and newborn terms, and the unscreened terms with mostly serious reports, for a person "
    "to review, not as signals",
]


def investigate(request: dict, settings: Settings, tracer: Tracer | None = None) -> dict:
    """One run. The background pools (report sources, the re-check, the Skeptic's checks, and its challenge reviews
    that overlap the Reviewer's rounds) are shut down however the run ends, so a run that stops on an error (a
    rejected Nightshift token) does not leave queued Zetaris and openFDA calls behind it. A challenge review already
    under way is told to stop, so it makes no further model calls."""
    items = max(1, settings.skeptic_items)
    pools = SimpleNamespace(sources=ThreadPoolExecutor(max_workers=4), background=ThreadPoolExecutor(max_workers=2),
                            # The early checks, plus late checks for targets the early ones did not cover.
                            skeptic=ThreadPoolExecutor(max_workers=2 * items + EARLY_EXTRA),
                            # One worker per target, so the targets' reviews run side by side as they did in one
                            # step before; their model calls take low-priority slots (Slots), so the Reviewer's
                            # rounds come first.
                            challenges=ThreadPoolExecutor(max_workers=items), cancelled=threading.Event())
    try:
        return run_investigation(request, settings, tracer, pools)
    except BaseException:
        pools.cancelled.set()
        raise
    finally:
        for pool in (pools.sources, pools.background, pools.skeptic, pools.challenges):
            pool.shutdown(wait=False, cancel_futures=True)


def run_investigation(request: dict, settings: Settings, tracer: Tracer | None, pools: SimpleNamespace) -> dict:
    sources_pool, background = pools.sources, pools.background
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

    # Evidence, all through Zetaris. With no label, no reaction can be checked against one, so the run stops before
    # any model call. It stops at registration when no label matched the name, so the other evidence queries don't
    # run either, or after the evidence when the label read found nothing usable.
    try:
        created = clerk.register_drug(drug)
        tracer.event("data_clerk", "sources_ready", drug=drug, created_now=created)
        if clerk.label_missing:
            stop_without_label(tracer, clerk, drug, clerk.totals(drug))
        totals, (screen_res, signals), (label_qid, label), (combo_res, combination), (severity_res, severity), \
            (scope_res, scope_rec) = gather_evidence(clerk, drug)
    except DrugNotFound as e:
        if not isinstance(e, NoCurrentLabel):
            tracer.event("data_clerk", "drug_not_found", drug=drug, message=str(e))
        raise
    if not sections(label):
        stop_without_label(tracer, clerk, drug, totals)
    passing = sorted((s for s in signals if s.prr >= 2 and s.chi2 >= 4), key=lambda s: -s.chi2)
    # The serious-term safety net (app/data/safety_net.py) is Zetaris and openFDA only, so it runs in the background
    # from here. Its terms never go into ctx, so no prompt, review item or ranking sees them.
    net_job = sources_pool.submit(lambda: clerk.serious_terms(drug))
    ctx = {
        "drug": drug, "totals": totals, "label": label, "label_qid": label_qid, "passing": passing,
        "label_choice": clerk.label_choice, "combination": combination, "seriousness": severity,
        "screen_qid": screen_res.query_id, "screen_passing": len(passing), "run_ends": started + settings.run_budget,
        "screen_shown": min(SCREEN_ROWS, len(passing)),
        "screen_table": screen_table(passing, SCREEN_ROWS),
        "evidence_ids": {totals["query_id"], screen_res.query_id} | ({label_qid} if label_qid else set())
                        | ({combo_res.query_id} if combo_res else set())
                        | ({severity_res.query_id} if severity_res else set())
                        | ({scope_res.query_id} if scope_res else set()),
    }
    if severity_res is None:
        tracer.event("data_clerk", "degraded", step="seriousness", fallback="no serious or death shares this run")
    if scope_res is None:
        tracer.event("data_clerk", "degraded", step="scope", fallback="the scope statement gives no list sizes")
    tracer.event("data_clerk", "evidence_ready", screened=len(signals), passing=len(passing),
                 label_sections=[k for k in label if k not in ("effective_time", "set_id")],
                 label_effective=label.get("effective_time"), label_choice=clerk.label_choice,
                 combination=combination, evidence_ids=sorted(ctx["evidence_ids"]))

    # Analyst <-> Reviewer loop. Accepted findings are settled and never re-done; each round only handles the
    # Reviewer's rejections and missing reactions nobody has attempted yet. A dispute that cannot be settled
    # ends as "unresolved" rather than being accepted when the rounds run out.
    names = {s.reaction for s in passing}
    # Where each review-next item's reports come from (app/data/sources.py), context for the Reviewer. Zetaris and
    # openFDA only, so it runs in the background. The drug's usual mix starts now, and each item's check as soon as a
    # round's findings mark it review_next. The Reviewer waits for an item's result only when it reaches that item.
    usual_sources = sources_pool.submit(clerk.report_sources, drug) if SOURCE_ITEMS else None
    ctx["sources"] = {}
    stats = {s.reaction: s for s in passing}

    def check_sources(fs: list[Finding]) -> None:
        for r in source_targets(fs, set(ctx["sources"]), SOURCE_ITEMS):
            ctx["sources"][r] = sources_pool.submit(check_report_sources, clerk, drug, r, usual_sources,
                                                    stats[r].a if r in stats else None)

    # Zetaris work that needs no model runs in the background while the model calls go on.
    rechecking, challenges = {}, None
    llm.cancelled = pools.cancelled

    def start_recheck(picked: list[str]) -> None:
        # The Reviewer's re-check needs only the reaction names, which are fixed once the pick is in, so it runs
        # while the Analyst classifies the extra picks (11.5 s median on its own, 24 and 25 Oct traces).
        rechecking["names"] = list(picked)
        rechecking["job"] = background.submit(clerk.recheck, drug, list(picked), "reviewer")

    findings, summary = analyst.run(ctx, on_selection=start_recheck)
    tracer.event("analyst", "findings", round=1, findings=[f.to_dict() for f in findings], summary=summary)
    attempted = {f.reaction for f in findings} | set(ctx.get("unclassified", []))
    if settings.skeptic_items:
        # The Skeptic's checks are Zetaris only, so they run while the Reviewer reviews round 1. Run after it,
        # they took a median of 82 s with nothing else running (24 and 25 Oct traces). Its targets are only known
        # once the Reviewer has accepted them, so it checks one more of the Analyst's review_next findings than it
        # needs: in those 18 runs the Analyst's top 4 held all 51 targets. Each check is its own job, so a
        # target's challenge review can start as soon as its own check is back.
        candidates = early_skeptic_targets(ctx, findings, settings.skeptic_items + EARLY_EXTRA)
        tracer.event("skeptic", "early_checks", candidates=candidates)
        early = {r: pools.skeptic.submit(skeptic_checks, ctx, skeptic, [r]) for r in candidates}
        # Each target's challenge review starts as soon as the target is certain and its check is back, alongside
        # the rest of the Reviewer's first round and the revision round. Started after the revision round, it was
        # reached once in 23 runs at the code defaults on 25 Oct. While challenge reviews may run, every model call
        # takes one of MODEL_PARALLEL shared slots, the Reviewer's rounds first, so the reviews use slots the rounds
        # are not using. The cost: a round's call can wait behind a review call already in flight, so round 1 and
        # the revision round can run a little longer than before, and the revision round's start gate sees that.
        low = llm.low_priority() if hasattr(llm, "low_priority") else llm  # stand-in clients in tests have no slots
        slots = Slots(settings.parallel) if candidates else None
        challenges = ChallengeQueue(ctx, candidates, settings.skeptic_items, early, skeptic,
                                    Reviewer(low, settings.reviewer_model, clerk, settings.parallel),
                                    Analyst(low, settings.analyst_model, settings.parallel, settings.analyst_top,
                                            settings.analyst_extra),
                                    tracer, left, pools.challenges, pools.cancelled, pools.skeptic, slots)
        llm.slots = slots
    state: dict = {}  # reaction -> {"finding", "verdict", "status", "history"}
    rounds, new_missing, revised = [], [], set()  # revised: reactions the revision rounds handled
    for rnd in range(1, settings.reviewer_rounds + 2):
        check_sources(findings)
        verdicts, missing, reviewer_summary = reviewer.review(
            ctx, findings, attempted, recheck=early_recheck(rechecking) if rnd == 1 else None,
            on_verdict=challenges.on_verdict if challenges and rnd == 1 else None)
        by = {v.reaction: v for v in verdicts}
        retry = []
        for f in findings:
            v = by[f.reaction]
            status, note = record(state.setdefault(f.reaction, {"history": []}), f, v, rnd)
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
        if rnd == 1 and challenges:
            # The Skeptic's targets are findings the Reviewer has just accepted, which the revision round does
            # not touch: it handles only rejected findings and reactions nobody has tried yet. Targets the queue
            # could not be sure of during the round start now.
            challenges.finish_round(state, skeptic_targets(ctx, state, settings.skeptic_items))
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
        revised |= {f.reaction for f in retry} | {m["reaction"] for m in new_missing}
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
    if challenges:
        try:
            results = challenges.join()  # each waits for its check only until the run's deadline
        finally:
            llm.slots = None
        skeptic_counts, skips = merge_challenges(ctx, state, results, revised, tracer)
        # As before, the challenge review counts as skipped when the budget stopped it, or, with nothing challenged,
        # when too little time was left for it at this point.
        if "skeptic challenge review" in skips or (not skeptic_counts["challenged"] and left() < CHALLENGE_NEEDS):
            skips.append("skeptic challenge review")
        skipped.extend(dict.fromkeys(skips))
    if skeptic_counts["challenged"]:
        rounds.append({"round": "skeptic", **skeptic_counts})
    sources = collect_sources(ctx, tracer, min(SOURCE_WAIT, max(0.0, left())))
    queue = review_queue(state, passing, new_missing, ctx.get("unclassified", []), ctx.get("skeptic"), severity, label,
                         sources)
    # Only now, with every model call done and the queue ranked, is the safety net read.
    net = collect_safety_net(net_job, min(SOURCE_WAIT, max(0.0, left())), tracer, signals, passing, queue, label,
                             severity)
    ctx["evidence_ids"] |= set(net["query_ids"])
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
              **{f"skeptic_{k}": v for k, v in skeptic_counts.items()},
              "report_sources_checked": sum("flags" in ev for ev in sources.values()),
              "report_sources_flagged": sum(bool(ev.get("raised")) for ev in sources.values()),
              "review_next_check_cluster_first": sum(
                  q["workflow_status"] == "reviewed" and (q.get("reporting_cluster") or {}).get("needed", False)
                  for q in queue),
              "thin_evidence": sum(bool((q.get("uncertainty") or {}).get("thin_evidence")) for q in queue),
              "manual_review": sum(q["manual_review"]["needed"] for q in queue),
              "safety_net_terms": net["term_count"]}

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
                 "label_effective": label.get("effective_time"), "label_set_id": label.get("set_id"),
                 "label_choice": clerk.label_choice, "combination_products": combination,
                 "seriousness_query": severity_res.query_id if severity_res else None,
                 "seriousness_note": "serious and death shares are of each reaction's reports; the flags describe "
                                     "the whole report, which may list other reactions",
                 "scope": scope_summary(drug, scope_rec, len(signals), totals["data_last_updated"],
                                        scope_res.query_id if scope_res else None)},
        "counts": counts,
        "review_queue": queue,
        # Outside the screen and the queue, for a person to review (app/data/safety_net.py).
        "safety_net": net,
        "degraded_steps": degraded,
        # Nightshift steps our app did not ask for, counted from each call's receipt (see nightshift_steps).
        "model_calls": model_calls,
        # Empty when Nightshift is set up as the README says; see setup_problems in the adapter.
        "nightshift_warnings": setup_warnings,
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


def source_targets(findings: list[Finding], have: set[str], cap: int) -> list[str]:
    """review_next findings whose report sources are not being checked yet, keeping the run's total at cap."""
    new = [f.reaction for f in findings if f.review_priority == "review_next" and f.reaction not in have]
    return list(dict.fromkeys(new))[:max(0, cap - len(have))]


def collect_sources(ctx: dict, tracer: Tracer, wait: float) -> dict:
    """Each item's report-source check, waiting at most `wait` seconds in all for any still running. A check that
    is not back by then, or failed, is recorded as such rather than holding up the dossier."""
    deadline, out = time.monotonic() + wait, {}
    for r, fut in ctx.get("sources", {}).items():
        try:
            ev = fut.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception as e:  # context only, so no failure of this check may stop the run
            ev = {"status": "not finished" if isinstance(e, FutureTimeout) else f"failed: {str(e)[:200]}"}
            tracer.event("data_clerk", "degraded", step="report sources", reaction=r, error=ev["status"],
                         fallback="no report-source flags for this item")
        out[r] = ev
        ctx["evidence_ids"] |= set(ev.get("query_ids", []))
        if "flags" in ev:
            tracer.event("data_clerk", "report_sources", reaction=r, flags=ev["flags"], summary=ev["summary"],
                         query_ids=ev["query_ids"])
    return out


def stop_without_label(tracer: Tracer, clerk: DataClerk, drug: str, totals: dict) -> None:
    """Raise for a run with no label to check reactions against, before any model call. A label query that failed
    for another reason is a ZetarisError, which the API marks recoverable. Otherwise it is NoCurrentLabel."""
    if clerk.label_error:
        tracer.event("data_clerk", "degraded", step="label", error=clerk.label_error, fallback="run stopped")
        raise ZetarisError(f"the label query for '{drug}' failed, so the run stopped before any model call "
                           f"({clerk.label_error})")
    message = clerk.no_label_message(drug, int(float(totals["drug_reports"])))
    tracer.event("data_clerk", "no_current_label", drug=drug, message=message)
    raise NoCurrentLabel(message)


def gather_evidence(clerk: DataClerk, drug: str) -> tuple:
    """The Data Clerk's evidence queries side by side; the Zetaris client keeps no state between calls. Only the
    combination query needs the totals (its share is of the drug's reports), so the others no longer wait for the
    totals query (8.8 s median, 24 and 25 Oct traces). A drug with no reports still fails at the totals."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [pool.submit(clerk.signals, drug), pool.submit(clerk.label, drug), pool.submit(clerk.seriousness, drug),
                pool.submit(clerk.scope, drug)]
        totals = clerk.totals(drug)
        combo = pool.submit(clerk.combination_products, drug, totals["drug_reports"])
        screen, label, severity, scope = [j.result() for j in jobs]
        return totals, screen, label, combo.result(), severity, scope


def early_recheck(rechecking: dict) -> tuple[list[str], tuple] | None:
    """The re-check started at the Analyst's selection, as (reactions, (QueryResult, {reaction: Signal})). None if
    it never started or failed, so the Reviewer runs it itself and handles a second failure as before."""
    if "job" not in rechecking:
        return None
    try:
        return rechecking["names"], rechecking["job"].result()
    except ZetarisError:
        return None


def early_skeptic_targets(ctx: dict, findings: list[Finding], top: int) -> list[str]:
    """The Analyst's strongest (by chi2) round-1 review_next findings, before the Reviewer has seen them."""
    stats = {s.reaction: s for s in ctx["passing"]}
    return sorted((f.reaction for f in findings if f.review_priority == "review_next"),
                  key=lambda r: -(stats[r].chi2 if r in stats else 0))[:top]


def skeptic_evidence(ctx: dict, skeptic: Skeptic, targets: list[str], early: dict) -> list[dict]:
    """Each target's checks, in target order: from the early checks where they covered it, otherwise run now."""
    late = [r for r in targets if r not in early]
    now = dict(zip(late, skeptic_checks(ctx, skeptic, late))) if late else {}
    return [early[r] if r in early else now[r] for r in targets]


def skeptic_targets(ctx: dict, state: dict, top: int) -> list[str]:
    """The strongest (by chi2) review_next findings the Reviewer has accepted."""
    stats = {s.reaction: s for s in ctx["passing"]}
    return sorted((r for r, e in state.items()
                   if e["status"] == "reviewed" and e["finding"].review_priority == "review_next"),
                  key=lambda r: -(stats[r].chi2 if r in stats else 0))[:top]


def skeptic_checks(ctx: dict, skeptic: Skeptic, picked: list[str]) -> list[dict]:
    """The Skeptic's Zetaris checks for each target. The items are independent, so they run side by side
    (about 80 s each on 23 Oct). No model calls, so this can overlap the Reviewer's first round."""
    stats = {s.reaction: s for s in ctx["passing"]}
    with ThreadPoolExecutor(max_workers=max(1, len(picked))) as pool:
        return list(pool.map(lambda r: skeptic.check(ctx["drug"], r, stats[r].prr if r in stats else None), picked))


def record(entry: dict, f: Finding, v: Verdict, rnd) -> tuple[str, str]:
    """Settle one finding's verdict for a round into its state entry, and return its status and note."""
    status, note = settle(f, v, entry["history"])
    claim = dict(zip(("label_coverage", "context", "review_priority"), f.key()))
    entry["history"].append({"round": rnd, "claim": claim, "decision": v.decision, "reason": v.reason,
                             "objection": v.objection})
    entry.update(finding=f, verdict=v, status=status, note=note)
    return status, note


def skipped_check(reaction: str) -> dict:
    """A target the Skeptic did not check because the run's time budget had run out. Never a challenge."""
    return {"reaction": reaction, "pairs": [], "query_ids": [], "outcome": "not_checked", "challenge_reasons": [],
            "skipped_for_time": True, "error": "not run: the run's time budget ran out first",
            "summary": f"Co-reported drug check not run for {reaction}: the run's time budget ran out first."}


class ChallengeQueue:
    """The Skeptic's challenge reviews, each started as soon as its target is certain and its check is back, in its
    own thread, while the Reviewer's first round and the revision round go on.

    Which targets: the same rule as skeptic_targets(), the top `top` review_next findings the Reviewer accepted in
    round 1, by chi2. Every review_next finding ranked above a candidate is itself a candidate, so a candidate the
    Reviewer has accepted is certain to be a target once fewer than `top` higher candidates are accepted or still
    waiting for their verdict. Those start from the round-1 verdicts (on_verdict); any target still unstarted when
    round 1 is settled starts then (finish_round).

    No shared state: each review works on its own copy of its target's entry and of ctx, taken in the main thread.
    The revision round handles only rejected findings and reactions nobody has tried, never an accepted target, so
    the two never touch the same reaction; merge_challenges() folds the copies back after both are done.

    Budget, checked when each step is due: the wait for a target's check ends at the run's deadline, a target the
    early checks did not cover is checked only with SKEPTIC_CHECK_NEEDS seconds left, and its review starts only with
    CHALLENGE_NEEDS left. A review that has started runs to its end, as before.

    Timing: the targets' reviews run side by side, one thread each, as the single review step did before. Their
    model calls go through the low-priority client (reviewer and analyst here are built on llm.low_priority()), so
    they take only slots the Reviewer's rounds are not asking for."""

    def __init__(self, ctx: dict, candidates: list[str], top: int, early: dict, skeptic: Skeptic, reviewer: Reviewer,
                 analyst: Analyst, tracer: Tracer, left, pool: ThreadPoolExecutor, cancelled: threading.Event,
                 checks_pool: ThreadPoolExecutor, slots: Slots | None = None):
        self.ctx, self.candidates, self.top, self.early = ctx, candidates, top, dict(early)
        self.skeptic, self.reviewer, self.analyst, self.tracer, self.left = skeptic, reviewer, analyst, tracer, left
        self.pool, self.cancelled, self.checks_pool, self.slots = pool, cancelled, checks_pool, slots
        self.verdicts: dict[str, dict] = {}  # candidate -> its round-1 entry, once the Reviewer has decided
        self.started: dict = {}  # target -> Future of its review
        self.targets: list[str] | None = None
        self.late: set[str] = set()  # targets checked after round 1 because the early checks did not cover them
        self.no_time: set[str] = set()  # such targets left unchecked because the budget had run out

    def on_verdict(self, f: Finding, v: Verdict) -> None:
        """A round-1 verdict, as it lands (called in the main thread by Reviewer.review)."""
        if f.reaction not in self.candidates:
            return
        entry = {"history": []}
        record(entry, copy.copy(f), copy.copy(v), 1)
        self.verdicts[f.reaction] = entry
        ahead = 0  # higher-ranked candidates that are accepted or still waiting for their verdict
        for r in self.candidates:
            if ahead >= self.top:
                break
            e = self.verdicts.get(r)
            if e is None:
                ahead += 1
            elif e["status"] == "reviewed" and e["finding"].review_priority == "review_next":
                if r not in self.started:
                    self._start(r, e)
                ahead += 1

    def finish_round(self, state: dict, targets: list[str]) -> None:
        """Round 1 is settled: start every target not started yet (main thread)."""
        self.targets = targets
        stray = [r for r in self.started if r not in targets]
        if stray:  # cannot happen (see the class docstring); kept out of the dossier if it ever does
            self.tracer.event("orchestrator", "challenge_target_mismatch", reactions=stray, targets=targets)
        for r in targets:
            if r in self.started:
                continue
            if r not in self.early:  # the early checks did not cover it: check it now, if there is time
                if self.left() >= SKEPTIC_CHECK_NEEDS:
                    self.early[r] = self.checks_pool.submit(skeptic_checks, self.ctx, self.skeptic, [r])
                    self.late.add(r)
                else:
                    self.no_time.add(r)
                    self.tracer.event("orchestrator", "budget_stop", step="skeptic late checks", reaction=r,
                                      seconds_left=round(self.left()))
            e = state[r]
            self._start(r, {**e, "finding": copy.copy(e["finding"]), "verdict": copy.copy(e["verdict"]),
                            "history": list(e["history"])})

    def _start(self, r: str, entry: dict) -> None:
        ctx = {**self.ctx, "evidence_ids": set(self.ctx["evidence_ids"]), "sources": dict(self.ctx["sources"]),
               "unclassified": list(self.ctx.get("unclassified", []))}
        self.tracer.event("skeptic", "challenge_queued", reaction=r, seconds_left=round(self.left()))
        self.started[r] = self.pool.submit(self._review, r, entry, ctx)

    def _review(self, r: str, entry: dict, ctx: dict) -> dict:
        """One target: its check, then (if challenged) its challenge review, in this queue's thread."""
        late = r in self.late
        out = {"reaction": r, "entry": entry, "ctx": ctx, "review": True, "from_early": False, "checked_now": late}
        if self.cancelled.is_set():  # the run is already stopping on an error, so this result is never merged
            return {**out, "cancelled": True}
        job, ev = self.early.get(r), None
        if job is not None:
            try:
                ev = job.result(timeout=max(0.0, self.left()))[0]  # skeptic.check catches its own Zetaris errors
                out["from_early"] = not late
            except FutureTimeout:
                self.tracer.event("orchestrator", "budget_stop", step="skeptic checks", reaction=r,
                                  seconds_left=round(self.left()))
        if ev is None:  # not back by the deadline, or (no_time) never started
            ev, out["checked_now"] = skipped_check(r), False
        out["review"] = self.left() >= CHALLENGE_NEEDS
        if ev["outcome"] == "challenged" and out["review"] and self.slots is not None:
            # The review's calls take only slots the Reviewer's rounds leave free, so in a long round 1 they can wait
            # a long time. The gate must hold when they can start: wait for a free slot only until CHALLENGE_NEEDS
            # seconds before the deadline, and skip the review as before if none comes by then.
            out["review"] = self.slots.free_before(time.monotonic() + self.left() - CHALLENGE_NEEDS)
        if ev["outcome"] == "challenged" and not out["review"]:
            self.tracer.event("orchestrator", "budget_stop", step="skeptic challenge review", reaction=r,
                              seconds_left=round(self.left()))
        reviewing = ev["outcome"] == "challenged" and out["review"]
        self.tracer.event("skeptic", "challenge_review_start" if reviewing else "challenge_review_none", reaction=r,
                          outcome=ev["outcome"], seconds_left=round(self.left()))
        out["counts"] = skeptic_round(ctx, {r: entry}, self.skeptic, self.reviewer, self.analyst, self.tracer, 1,
                                      prefetched=([r], [ev]), review=out["review"])
        out["challenged"], out["skipped_check"] = ev["outcome"] == "challenged", bool(ev.get("skipped_for_time"))
        if out["skipped_check"]:
            out["counts"]["checked"] = 0
        self.tracer.event("skeptic", "challenge_review_end", reaction=r, seconds_left=round(self.left()),
                          **out["counts"])
        return out

    def join(self) -> list[dict]:
        """Every target's result, in target order, once all are done (main thread, after the revision rounds)."""
        results = [self.started[r].result() for r in self.targets or []]
        self.tracer.event("skeptic", "early_checks_used", targets=self.targets or [],
                          from_early=[o["reaction"] for o in results if o["from_early"]],
                          checked_now=[o["reaction"] for o in results if o["checked_now"]],
                          not_checked_for_time=[o["reaction"] for o in results if o.get("skipped_check")],
                          unused=[r for r in self.candidates if r not in (self.targets or [])])
        return results


def merge_challenges(ctx: dict, state: dict, results: list[dict], revised: set[str],
                     tracer: Tracer) -> tuple[dict, list[str]]:
    """Fold each target's review back into the run (main thread, after both branches are done), and return the
    Skeptic's counts and the steps the budget skipped. A reaction the revision rounds handled keeps their result; that
    cannot happen (see ChallengeQueue), and if it ever did the clash is traced and left out of the counts."""
    counts = {"checked": 0, "challenged": 0, "challenge_not_reviewed": 0, "priority_changed": 0}
    ctx["skeptic"], skips = {}, []
    clash = [o["reaction"] for o in results if o["reaction"] in revised]
    if clash:
        tracer.event("orchestrator", "challenge_merge_conflict", reactions=clash, kept="revision round")
    for o in results:
        r = o["reaction"]
        if r in revised or o.get("cancelled"):  # neither happens in a run that reaches this point
            continue
        state[r] = o["entry"]
        ctx["skeptic"][r] = o["ctx"]["skeptic"][r]
        ctx["evidence_ids"] |= o["ctx"]["evidence_ids"]
        new = [x for x in o["ctx"]["unclassified"] if x not in ctx.get("unclassified", [])]
        if new:
            ctx.setdefault("unclassified", []).extend(new)
        counts = {k: counts[k] + o["counts"][k] for k in counts}
        if o.get("skipped_check"):
            skips.append("skeptic checks")
        if o["challenged"] and not o["review"]:
            skips.append("skeptic challenge review")
    return counts, skips


def skeptic_round(ctx: dict, state: dict, skeptic: Skeptic, reviewer: Reviewer, analyst: Analyst, tracer: Tracer,
                  top: int, prefetched: tuple[list[str], list[dict]] | None = None, review: bool = True) -> dict:
    """The Skeptic checks the strongest accepted review_next findings against their co-reported drugs.
    A challenged finding goes back to the Reviewer with that evidence. If the Reviewer rejects it, the Analyst
    gets one revision and the Reviewer one more look; a dispute still open after that ends as unresolved.
    If the Reviewer's look at the challenge itself fails (model call failed), the round-1 verdict stands and the
    item says the challenge was not reviewed, rather than losing its earlier review.
    prefetched: (targets, checks) already run, mostly while the first review round ran. review=False when the
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


VERDICT_FIELDS = ("workflow_status", "context", "label_coverage", "review_priority")
# What reads the World Model, for the dossier (the engine guide asks runs to say which read paths are live).
WORLD_MODEL_READS = {
    "code": "every queue item is compared with the verdict the World Model holds from earlier runs (since_last_run), "
            "and a new label version reopens the verdicts that rested on the old one",
    "agent_prompts": "none: earlier verdicts are kept out of the Analyst's and Reviewer's prompts, because a past "
                     "answer shown to the model is read as evidence (Nightshift's H-MEM replay, found 24 Oct)",
}


def since_last_run(q: dict, earlier: dict | None, earlier_version: dict | None, version: dict) -> dict:
    """How this run's verdict on one reaction compares with the one the World Model holds from an earlier run,
    and why it may differ: a new label version, different report counts, or this run's judgement on the same
    evidence. `earlier` is the stored decision as it was before this run wrote anything."""
    if earlier is None:
        return {"status": "new", "why": "No earlier settled verdict for this reaction in the World Model."}
    e = earlier["value"]
    before = {"run_id": e.get("run_id"), "decided_at": earlier.get("decidedAt"),
              "label_effective": (earlier_version or {}).get("effective_time"),
              **{k: e.get(k) for k in VERDICT_FIELDS + ("a", "prr")}}
    changed = [{"field": k, "earlier": e.get(k), "now": q.get(k)} for k in VERDICT_FIELDS
               if e.get(k) is not None and q.get(k) is not None and e.get(k) != q.get(k)]
    label_changed = bool(earlier_version) and earlier_version != version
    if label_changed:
        why = (f"The label changed from version {earlier_version.get('effective_time')} to "
               f"{version.get('effective_time')} since run {e.get('run_id')}, which reopened the earlier verdict.")
    elif e.get("a") is None:
        why = (f"Same label version as run {e.get('run_id')}; that run's report counts were not recorded, so a "
               f"difference may come from new reports or from this run's judgement.")
    elif e.get("a") != q.get("a"):
        why = (f"Same label version as run {e.get('run_id')}; reports with the drug went from {e.get('a')} to "
               f"{q.get('a')} (PRR {e.get('prr')} to {q.get('prr')}).")
    else:
        why = (f"Same label version and the same {q.get('a')} reports as run {e.get('run_id')}"
               + ("; the difference is this run's judgement on the same evidence." if changed else "."))
    if q["workflow_status"] not in SETTLED:
        status = "not_settled_now"
        why = f"Not settled in this run ({q['workflow_status']}); the earlier verdict is shown for reference. " + why
    else:
        status = "changed" if changed else "unchanged"
    return {"status": status, "label_changed": label_changed, "changed": changed, "earlier": before, "why": why}


def remember(world: WorldModel, drug: str, label: dict, queue: list[dict], run_id: str, at: str) -> dict:
    """Record this run's label version and settled verdicts in the World Model. A label version that
    differs from the last run's supersedes it, which reopens every earlier verdict that rested on it:
    those come back in `reopened` so the analyst knows which past answers need a second look.
    Before writing, every queue item is compared with the World Model's earlier verdict and gets
    `since_last_run`, so every run shows what the engine holds, not only runs where a label changed."""
    source = {"kind": "openfda-label-via-zetaris", "at": at, "runId": run_id}
    audit_from = len(world.audit())
    entity = world.upsert_entity(type="drug", name=drug, source=source)
    version = {"set_id": label.get("set_id"), "effective_time": label.get("effective_time")}
    previous = world.current_fact(entity["id"], "label_version")
    # Snapshots, taken before this run's writes change the decisions' status or replace them.
    earlier = {d["value"]["reaction"]: json.loads(json.dumps(d)) for d in world.decisions(about=entity["id"])}
    facts = world.state["facts"]
    earlier_versions = {r: (facts.get((d.get("dependsOn") or [None])[0]) or {}).get("value")
                        for r, d in earlier.items()}
    before = {d["key"] for d in world.decisions(status="reopened", about=entity["id"])}
    fact = world.assert_fact(about=entity["id"], predicate="label_version", value=version, source=source)
    reopened = [{"reaction": d["value"]["reaction"], "earlier_run": d["value"]["run_id"],
                 "earlier_label_coverage": d["value"].get("label_coverage"),
                 "earlier_review_priority": d["value"].get("review_priority")}
                for d in world.decisions(status="reopened", about=entity["id"]) if d["key"] not in before]
    for q in queue:
        q["since_last_run"] = since_last_run(q, earlier.get(q["reaction"]), earlier_versions.get(q["reaction"]),
                                             version)
    recorded = 0
    for q in queue:
        if q["workflow_status"] in SETTLED:
            world.record_decision(
                key=f"{entity['id']}|{q['reaction']}", about=entity["id"], depends_on=[fact["id"]], source=source,
                value={"reaction": q["reaction"], "run_id": run_id, "workflow_status": q["workflow_status"],
                       **{k: q.get(k) for k in ("label_coverage", "context", "review_priority", "a", "prr")}})
            recorded += 1
    in_queue = {q["reaction"] for q in queue}
    statuses = [q["since_last_run"]["status"] for q in queue]
    summary = {
        "compared_with_runs": sorted({d["value"].get("run_id") for d in earlier.values()} - {None}),
        "previous_label_version": (previous or {}).get("value"),
        "label_version_changed": bool(previous) and previous["value"] != version,
        **{s: statuses.count(s) for s in ("new", "unchanged", "changed", "not_settled_now")},
        "changed_items": [q["reaction"] for q in queue if q["since_last_run"]["status"] == "changed"],
        # Reactions an earlier run sent to review next that this run did not assess at all: the selection or the
        # screen moved, and an analyst should know a past flag is not being re-checked.
        "earlier_review_next_not_assessed": [
            {"reaction": r, "earlier_run": d["value"].get("run_id")} for r, d in sorted(earlier.items())
            if r not in in_queue and d["value"].get("review_priority") == "review_next"],
        "earlier_verdicts_not_in_this_run": sum(r not in in_queue for r in earlier),
    }
    audit = [{k: a.get(k) for k in ("seq", "kind", "actor", "summary", "eventId")} for a in world.audit()[audit_from:]]
    return {"label_fact": fact["id"], "label_version": version, "decisions_recorded": recorded,
            "reopened": reopened, "since_last_run": summary, "read_by": WORLD_MODEL_READS, "audit": audit}


PRIORITY_ORDER = {"review_next": 0, "insufficient_evidence": 1, "lower_priority": 2, None: 3}
STATUS_ORDER = {"unresolved": 0, "reviewed": 1, "not_reviewed": 2, "pending": 3, "failed": 4}


def review_queue(state: dict, passing: list, pending: list[dict], failed: list[str],
                 skeptic: dict | None = None, severity: dict | None = None, label: dict | None = None,
                 sources: dict | None = None) -> list[dict]:
    """The analyst's queue: every assessed reaction with its priority, objection and next check, plus
    reactions that were named for review but never reached, ranked review_next first. The serious and death
    shares are shown, not used for ranking: they describe whole reports, not the reaction. Each item carries the
    code's label search, so a "not found" says what was searched and an expected effect is quoted, and a review-next
    item its report sources (context flags, never used for ranking either). Each item's uncertainty (expected count,
    PRR interval, IC025, thin evidence) comes from the screen's Zetaris counts and is shown, never used to rank, and
    so is its manual_review flag (app/orchestration/manual_review.py)."""
    stats = {s.reaction: s for s in passing}
    def extra(r):
        return (({"uncertainty": uncertainty.of(stats[r])} if r in stats else {})
                | ({"seriousness": severity[r]} if severity and r in severity else {})
                | ({"label_search": search(r, label)} if label else {})
                | ({"report_sources": sources[r]} if sources and r in sources else {}))
    queue = []
    for r, e in state.items():
        f, v = e["finding"], e["verdict"]
        item = {**f.to_dict(), "chi2": stats[r].chi2 if r in stats else None, **extra(r),
                "workflow_status": e["status"], "reviewer": v.reason, "status_note": e.get("note", ""),
                "strongest_objection": v.objection, "next_check": v.next_check or f.next_check,
                "history": e["history"],
                **({"co_reported_drugs": skeptic[r]} if skeptic and r in skeptic else {})}
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
                      "chi2": s.chi2 if s else None, **extra(m["reaction"]), "workflow_status": "pending",
                      "review_priority": None,
                      "status_note": f"named by the Reviewer in the last round, not reached: {m.get('why', '')}"})
    for r in sorted(set(failed) - set(state)):
        s = stats.get(r)
        queue.append({"reaction": r, "a": s.a if s else None, "prr": s.prr if s else None,
                      "chi2": s.chi2 if s else None, **extra(r), "workflow_status": "failed", "review_priority": None,
                      "status_note": "the Analyst's model gave no classification for it after every fallback"})
    for q in queue:  # context only, added after every other field and never part of the sort below
        q["manual_review"] = manual_review(q, stats[q["reaction"]].a if q["reaction"] in stats else q.get("a"))
        if q.get("review_priority") == "review_next":  # display only, like the flags it reads
            q["reporting_cluster"] = cluster_check(q.get("report_sources"))
    queue.sort(key=lambda q: (PRIORITY_ORDER.get(q.get("review_priority"), 3),
                              STATUS_ORDER.get(q["workflow_status"], 5), -(q.get("chi2") or 0)))
    return queue
