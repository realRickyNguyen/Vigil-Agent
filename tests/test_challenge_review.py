"""Offline checks of the Skeptic's challenge reviews running alongside the Reviewer's first round and the revision
round: a target's review starts while round 1 is still going, the model calls together stay within MODEL_PARALLEL,
the budget rules hold, the results land in the dossier as before, and a run that stops on an error stops its reviews.
No Zetaris, no Nightshift: the real Nightshift client runs with its HTTP step replaced.
Run: python -I -m pytest tests"""
import io
import json
import sys
import threading
import time
import urllib.error
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless  # noqa: E402
from app.adapters.meterless import MeterlessUnauthorized  # noqa: E402
from app.config import Settings  # noqa: E402
from app.orchestration import pipeline  # noqa: E402
from app.schemas import Finding, QueryResult, Signal, Verdict  # noqa: E402

TARGETS = ["ALOPECIA", "TINNITUS", "VERTIGO"]   # accepted in round 1, then challenged by the Skeptic
REVISED = ["DYSGEUSIA", "MYALGIA", "PAROSMIA"]  # rejected in round 1, so revised
WAIT = 3  # seconds a call waits to see another one start, before the test calls the two sequential


class Clerk:
    """Zetaris answers for one drug. The challenge targets have the strongest chi2, so the Skeptic picks them."""
    label_choice = None
    label_missing, label_error = False, None  # the label below is found

    def __init__(self):
        self.rows = [Signal(r, a=500 - i, b=1000, c=2000, d=19000000, prr=8.0, chi2=9000.0 - 100 * i)
                     for i, r in enumerate(TARGETS + REVISED)]

    def register_drug(self, drug):
        return {}

    def totals(self, drug):
        return {"drug_reports": 100000, "all_reports": 20000000, "data_last_updated": "2026-07-30", "query_id": "q-t"}

    def signals(self, drug):
        return QueryResult("q-s", "", [], []), self.rows

    def label(self, drug):
        return "q-l", {"adverse_reactions": "Cough was common.", "effective_time": "20260804"}

    def combination_products(self, drug, reports):
        return None, None

    def seriousness(self, drug):
        return None, {}

    def scope(self, drug):
        return None, None

    def recheck(self, drug, reactions, agent="reviewer"):
        return QueryResult("q-r", "", [], []), {s.reaction: s for s in self.rows if s.reaction in reactions}


def skeptic_class(outcome="challenged"):
    class Skeptic:
        """Gives every target it checks the same outcome, with its own query ID per target."""
        def __init__(self, *a):
            self.checked = []

        def check(self, drug, reaction, prr):
            self.checked.append(reaction)
            return {"reaction": reaction, "outcome": outcome, "challenge_reasons": ["adjusted_below_threshold"],
                    "pairs": [], "query_ids": [f"q-sk-{reaction}"], "summary": "s"}
    return Skeptic


class Nvidia:
    """Stands in for Nightshift's HTTP reply. Classifies every row as an unlabelled review_next event; the Reviewer
    rejects each REVISED item once and the first TARGET once in its challenge review, and accepts everything else.
    Records each call's branch and timing. With `hold`, the last round-1 Reviewer call waits until a challenge-review
    call has started; with `fail`, it then fails as Nightshift does for a rejected token."""
    def __init__(self, hold=False, fail=False, pause=0.0):
        self.lock, self.seen, self.calls, self.pause, self.hold, self.fail = threading.Lock(), {}, [], pause, hold, fail
        self.challenge_started, self.round1_saw_challenge, self.failed_at = threading.Event(), None, None

    def post(self, client, body):
        system, user = body["messages"][0]["content"], body["messages"][-1]["content"]
        reviewer = system.startswith("You are the Reviewer")
        challenge = '"co_reported_drugs"' in user or "The Skeptic checked the drugs" in user
        names = [r for r in TARGETS + REVISED if f'"reaction": "{r}"' in user or f"\n{r} | " in user]
        with self.lock:
            counts = {r: self.seen.get((reviewer, r), 0) for r in names}
            for r in names:
                self.seen[(reviewer, r)] = counts[r] + 1
            first_review = reviewer and not challenge and all(c == 0 for c in counts.values())
            branch = ("challenge" if challenge else "round 1 review" if first_review
                      else "revision" if any(r in REVISED and counts[r] >= 1 for r in names) else "analyst round 1")
            start = time.monotonic()
        if challenge:
            self.challenge_started.set()
        try:
            if self.hold and first_review and names == [REVISED[-1]]:
                self.round1_saw_challenge = self.challenge_started.wait(WAIT)
                if self.fail:
                    self.failed_at = time.monotonic()
                    raise urllib.error.HTTPError("m", 401, "unauthorized", {}, io.BytesIO(b"bad token"))
            time.sleep(self.pause)
            reply = self.reply(system, user, reviewer, challenge, names, counts)
        finally:
            with self.lock:
                self.calls.append((branch, start, time.monotonic()))
        return {"model": body["model"], "choices": [{"message": {"content": json.dumps(reply)}}],
                "usage": {"completion_tokens": 10}}

    @staticmethod
    def reply(system, user, reviewer, challenge, names, counts):
        if reviewer:
            def decide(r):
                if r in REVISED and counts[r] == 0:
                    return "reject"
                if challenge and r == TARGETS[0] and counts[r] == 1:
                    return "reject"  # the challenge review turns down the first target once
                return "accept"
            return {"verdicts": [{"reaction": r, "decision": decide(r), "reason": "r", "objection": "o",
                                  "next_check": "n"} for r in names], "missing": [], "summary": ""}
        if "choose up to" in system:
            return {"picked": []}
        rows = [line.split(" | ") for line in user.splitlines() if line.count(" | ") >= 3
                and not line.startswith("reaction")]
        lowered = challenge and "The Reviewer reviewed your earlier findings" in user
        return {"findings": [{"reaction": r[0], "a": int(r[1]), "prr": float(r[2]), "context": "clinical_event",
                              "label_coverage": "not_found",
                              "review_priority": "insufficient_evidence" if lowered else "review_next",
                              "reasoning": "x", "next_check": "y", "evidence": ["q-s"]} for r in rows], "summary": ""}

    def max_in_flight(self, after: str = "round 1 review") -> int:
        """Most calls in flight at once, counting from the first call of branch `after`."""
        t0 = min(a for k, a, _ in self.calls if k == after)
        points = sorted([(a, 1) for _, a, b in self.calls if a >= t0] + [(b, -1) for _, a, b in self.calls if a >= t0],
                        key=lambda p: (p[0], p[1]))
        now = most = 0
        for _, d in points:
            now += d
            most = max(most, now)
        return most


def settings(tmp_path, parallel=4, budget=600):
    return Settings(zetaris_url="z", zetaris_key="k", zetaris_org="1", meterless_url="m", meterless_token="t",
                    meterless_app="vigil", analyst_model="a", reviewer_model="a", source_timeout=20, model_timeout=90,
                    model_stream=True, max_retries=0, reviewer_rounds=1, parallel=parallel, run_budget=budget,
                    sample_mode=False, logs_dir=tmp_path, world_path=tmp_path / "world.json", analyst_top=6,
                    analyst_extra=0)


def run(tmp_path, monkeypatch, nvidia, outcome="challenged", **kw):
    monkeypatch.setattr(pipeline, "ZetarisClient", lambda s, t: None)
    monkeypatch.setattr(pipeline, "DataClerk", lambda z: Clerk())
    monkeypatch.setattr(pipeline, "Skeptic", skeptic_class(outcome))
    monkeypatch.setattr(pipeline, "SOURCE_ITEMS", 0)
    monkeypatch.setattr(meterless.NightshiftClient, "_post", lambda self, body: nvidia.post(self, body))
    tracer = pipeline.Tracer(tmp_path, echo=False)
    dossier = pipeline.investigate({"drug": "montelukast"}, settings(tmp_path, **kw), tracer)
    return dossier, [json.loads(line) for line in tracer.path.read_text(encoding="utf-8").splitlines()]


def test_a_targets_challenge_review_starts_while_round_1_is_still_going(tmp_path, monkeypatch):
    nvidia = Nvidia(hold=True)
    dossier, events = run(tmp_path, monkeypatch, nvidia)
    # The last round-1 Reviewer call saw a challenge-review call start before it finished.
    assert nvidia.round1_saw_challenge is True
    kinds = [e["event"] for e in events]
    first_round_end = next(i for i, e in enumerate(events) if e["event"] == "verdicts" and e["round"] == 1)
    assert kinds.index("challenge_review_start") < first_round_end
    assert "skeptic challenge review" not in dossier["run_time"]["skipped_for_time"]


def test_the_results_land_in_the_dossier_as_before(tmp_path, monkeypatch):
    dossier, events = run(tmp_path, monkeypatch, Nvidia())
    by = {q["reaction"]: q for q in dossier["review_queue"]}
    for r in REVISED:  # rejected in round 1, accepted after the revision round
        assert by[r]["workflow_status"] == "reviewed" and [h["round"] for h in by[r]["history"]] == [1, 2]
    first, *rest = TARGETS
    assert [h["round"] for h in by[first]["history"]] == [1, "skeptic", "skeptic_revision"]
    assert by[first]["review_priority"] == "insufficient_evidence" and by[first]["workflow_status"] == "reviewed"
    for r in rest:
        assert [h["round"] for h in by[r]["history"]] == [1, "skeptic"] and by[r]["review_priority"] == "review_next"
    for r in TARGETS:
        assert by[r]["co_reported_drugs"]["outcome"] == "challenged"
        assert by[r]["co_reported_drugs"]["query_ids"] == [f"q-sk-{r}"]
    assert [r["round"] for r in dossier["rounds"]] == [1, 2, "skeptic"]
    assert dossier["rounds"][-1] == {"round": "skeptic", "checked": 3, "challenged": 3, "challenge_not_reviewed": 0,
                                     "priority_changed": 1}
    assert dossier["counts"]["skeptic_challenged"] == 3 and dossier["counts"]["skeptic_priority_changed"] == 1
    assert dossier["run_time"]["skipped_for_time"] == []
    assert not any(e["event"] in ("challenge_merge_conflict", "challenge_target_mismatch") for e in events)


def test_all_model_calls_share_model_parallel_slots(tmp_path, monkeypatch):
    nvidia = Nvidia(pause=0.15)
    run(tmp_path, monkeypatch, nvidia, parallel=2)
    challenge = [(a, b) for k, a, b in nvidia.calls if k == "challenge"]
    others = [(a, b) for k, a, b in nvidia.calls if k in ("round 1 review", "revision")]
    assert challenge and others
    # Never more than MODEL_PARALLEL calls in flight, from the first round-1 review call to the end, however the
    # challenge calls and the Reviewer's rounds interleave (the challenge calls take only slots left free).
    assert nvidia.max_in_flight() <= 2


def test_a_challenge_review_without_time_is_skipped_and_recorded_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CHALLENGE_NEEDS", 10_000)
    nvidia = Nvidia()
    dossier, events = run(tmp_path, monkeypatch, nvidia)
    assert dossier["run_time"]["skipped_for_time"] == ["skeptic challenge review"]
    by = {q["reaction"]: q for q in dossier["review_queue"]}
    for r in TARGETS:
        assert by[r]["workflow_status"] == "reviewed"
        assert "time budget ran out before the Reviewer" in by[r]["status_note"]
    assert not any(k == "challenge" for k, _, _ in nvidia.calls)  # no model call looked at the challenges
    assert [r["round"] for r in dossier["rounds"]] == [1, 2, "skeptic"]  # the revision round still ran
    assert dossier["rounds"][-1]["challenge_not_reviewed"] == 3
    assert any(e["event"] == "budget_stop" and e["step"] == "skeptic challenge review" for e in events)


def test_nothing_challenged_means_no_challenge_calls(tmp_path, monkeypatch):
    nvidia = Nvidia()
    dossier, _ = run(tmp_path, monkeypatch, nvidia, outcome="no_challenge")
    assert not any(k == "challenge" for k, _, _ in nvidia.calls)
    assert dossier["counts"]["skeptic_checked"] == 3 and dossier["counts"]["skeptic_challenged"] == 0
    assert dossier["run_time"]["skipped_for_time"] == [] and [r["round"] for r in dossier["rounds"]] == [1, 2]


def test_a_run_that_stops_on_an_error_stops_its_challenge_reviews(tmp_path, monkeypatch):
    nvidia = Nvidia(hold=True, fail=True, pause=0.2)
    with pytest.raises(MeterlessUnauthorized):
        run(tmp_path, monkeypatch, nvidia)
    time.sleep(1.0)  # time for a review that kept going to make more calls
    # The client stops every call of the run as it sees the rejected token. A challenge call already past its last
    # check may still go out within a few milliseconds of that; nothing later does.
    later = [k for k, a, _ in nvidia.calls if a > nvidia.failed_at + 0.05]
    assert later == []


class RecordingPool:
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args):
        self.submitted.append(args[0])
        return None


def queue(candidates, top=3, early=None, left=600.0):
    tracer = SimpleNamespace(events=[], event=lambda agent, kind, **d: tracer.events.append((kind, d)))
    ctx = {"drug": "x", "evidence_ids": set(), "sources": {},
           "passing": [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in candidates + ["E"]]}
    return pipeline.ChallengeQueue(ctx, candidates, top, early or {}, skeptic_class("no_challenge")(), None, None,
                                   tracer, lambda: left, RecordingPool(), threading.Event(), ThreadPoolExecutor(2))


def verdict(q, r, decision):
    q.on_verdict(Finding(r, 10, 3.0, "not_found", "clinical_event", "review_next", "x", "y", ["q-s"]),
                 Verdict(r, decision, "r"))


def test_a_target_starts_only_once_it_is_certain_to_be_one():
    q = queue(["A", "B", "C", "D"])
    verdict(q, "D", "accept")
    assert q.pool.submitted == []  # A, B and C could still all be accepted, which would leave D out
    verdict(q, "A", "accept")
    assert q.pool.submitted == ["A"]  # nothing ranks above A
    verdict(q, "B", "reject")
    assert q.pool.submitted == ["A", "D"]  # with B out, D is in the top 3 whatever C's verdict is
    verdict(q, "C", "accept")
    assert q.pool.submitted == ["A", "D", "C"]
    state = {r: {"finding": None, "verdict": None, "history": [], "status": "reviewed"} for r in ("A", "C", "D", "E")}
    q.finish_round(state, ["A", "C", "D"])
    assert q.pool.submitted == ["A", "D", "C"]  # nothing left to start
    q2 = queue(["A", "B"], top=3)
    verdict(q2, "A", "accept")
    verdict(q2, "B", "reject")
    q2.finish_round({**state, "A": q2.verdicts["A"]}, ["A", "E"])  # E was not a candidate: it starts at the round's end
    assert q2.pool.submitted == ["A", "E"]


def entry(r):
    return {"finding": Finding(r, 10, 3.0, "not_found", "clinical_event", "review_next", "x", "y", ["q-s"]),
            "verdict": Verdict(r, "accept", "ok"), "status": "reviewed", "history": [], "note": ""}


def done(value):
    f = Future()
    f.set_result(value)
    return f


def test_a_target_the_early_checks_missed_is_checked_only_with_time_left():
    ev = {"reaction": "E", "outcome": "no_challenge", "pairs": [], "query_ids": ["q-e"]}
    q = queue(["A"], left=pipeline.SKEPTIC_CHECK_NEEDS + 5)
    q.finish_round({"E": entry("E")}, ["E"])  # E was not a candidate, so its check starts now, in the checks pool
    out = q._review("E", entry("E"), dict(q.ctx))
    assert q.skeptic.checked == ["E"] and out["checked_now"] and not out["from_early"]
    assert out["counts"]["checked"] == 1
    q = queue(["A"], left=pipeline.SKEPTIC_CHECK_NEEDS - 5)
    q.finish_round({"E": entry("E")}, ["E"])
    out = q._review("E", entry("E"), {**q.ctx})
    assert q.skeptic.checked == [] and out["skipped_check"] and out["counts"]["checked"] == 0
    assert out["ctx"]["skeptic"]["E"]["outcome"] == "not_checked" and out["ctx"]["skeptic"]["E"]["skipped_for_time"]
    assert ("budget_stop", {"step": "skeptic late checks", "reaction": "E", "seconds_left": 85}) in q.tracer.events
    q = queue(["A"], early={"A": done([ev | {"reaction": "A"}])})
    assert q._review("A", entry("A"), {**q.ctx})["from_early"]


def test_the_wait_for_a_targets_check_ends_at_the_deadline():
    q = queue(["A"], early={"A": Future()}, left=0)  # a check that never finishes
    t0 = time.monotonic()
    out = q._review("A", entry("A"), {**q.ctx})
    assert time.monotonic() - t0 < 1 and q.skeptic.checked == [] and out["skipped_check"]
    assert out["counts"] == {"checked": 0, "challenged": 0, "challenge_not_reviewed": 0, "priority_changed": 0}
    assert any(k == "budget_stop" and d["step"] == "skeptic checks" for k, d in q.tracer.events)


def test_merge_keeps_the_revision_round_if_a_reaction_were_ever_in_both():
    tracer = SimpleNamespace(events=[], event=lambda agent, kind, **d: tracer.events.append((kind, d)))
    state = {"A": {"from": "revision"}, "B": {"from": "main"}}
    ctx = {"evidence_ids": {"q-1"}, "unclassified": ["X"]}
    counts = {"checked": 1, "challenged": 1, "challenge_not_reviewed": 0, "priority_changed": 1}

    def result(r, **kw):
        return {"reaction": r, "entry": {"from": "branch"}, "counts": counts, "challenged": True, "review": True,
                "ctx": {"evidence_ids": {"q-1", f"q-{r}"}, "unclassified": ["X", "Y"], "skeptic": {r: {"r": r}}}, **kw}
    total, skips = pipeline.merge_challenges(ctx, state, [result("A"), result("B"), result("C", review=False,
                                                                                         skipped_check=True)],
                                             {"A"}, tracer)
    assert state["A"]["from"] == "revision" and state["B"]["from"] == "branch" and ctx["skeptic"] == {
        "B": {"r": "B"}, "C": {"r": "C"}}
    assert ctx["evidence_ids"] == {"q-1", "q-B", "q-C"} and ctx["unclassified"] == ["X", "Y"]
    assert total == {"checked": 2, "challenged": 2, "challenge_not_reviewed": 0, "priority_changed": 2}
    assert skips == ["skeptic checks", "skeptic challenge review"]
    assert tracer.events == [("challenge_merge_conflict", {"reactions": ["A"], "kept": "revision round"})]


OK = {"model": "m", "choices": [{"message": {"content": "ok"}}]}


def client(slots, retries=0):
    c = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=retries, model_stream=True),
                                   SimpleNamespace(event=lambda *a, **k: None))
    c.slots = slots
    return c


def test_the_client_slots_bound_calls_in_flight():
    c, lock, state = client(meterless.Slots(4)), threading.Lock(), {"now": 0, "max": 0}

    def post(body):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return OK

    c._post = post
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: c.chat("x", "m", [{"role": "user", "content": "hi"}]), range(8)))
    assert state["max"] <= 4
    # Without slots the same eight calls are all in flight at once (they meet at a barrier).
    c, barrier = client(None), threading.Barrier(8, timeout=5)
    c._post = lambda body: barrier.wait() and OK or OK
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: c.chat("x", "m", [{"role": "user", "content": "hi"}]), range(8)))


def test_a_failed_attempt_gives_its_slot_back(monkeypatch):
    monkeypatch.setattr(meterless.time, "sleep", lambda s: None)
    c, held = client(meterless.Slots(1), retries=1), []
    replies = [ConnectionResetError("dropped"), OK]

    def post(body):
        held.append(c.slots.free == 0)  # the attempt holds the only slot
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    c._post = post
    with ThreadPoolExecutor(max_workers=1) as pool:  # a slot kept by the failed attempt would block the retry
        assert pool.submit(c.chat, "x", "m", [{"role": "user", "content": "hi"}]).result(timeout=5) == "ok"
    assert held == [True, True] and c.slots.free == 1  # and it is free afterwards


def test_a_call_that_waited_for_a_slot_also_waits_out_a_cool_down():
    c, holding, posted = client(meterless.Slots(1)), threading.Event(), {}

    def post(body):
        if body["messages"][0]["content"] == "a":
            holding.set()
            time.sleep(0.3)  # call b passes its first cool-down check (none yet) and queues for the slot
            with c._lock:  # then another call's 429 starts a cool-down while this one holds the slot
                c._cooldown_until = time.monotonic() + 0.5
            posted["until"] = c._cooldown_until
            time.sleep(0.05)
        else:
            posted["b"] = time.monotonic()
        return OK

    c._post = post
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(c.chat, "x", "m", [{"role": "user", "content": "a"}])
        holding.wait(5)
        b = pool.submit(c.chat, "x", "m", [{"role": "user", "content": "b"}])  # queues for the slot
        a.result(5), b.result(5)
    assert posted["b"] >= posted["until"]


def test_a_cancelled_run_makes_no_more_calls():
    c = client(None)
    c.cancelled = threading.Event()
    c.cancelled.set()
    c._post = lambda body: pytest.fail("a call went out after the run was cancelled")
    with pytest.raises(meterless.MeterlessError, match="run cancelled"):
        c.chat("x", "m", [{"role": "user", "content": "hi"}])


def test_a_rejected_token_stops_every_call_of_the_run():
    c = client(None)
    c.cancelled = threading.Event()
    c._post = lambda body: (_ for _ in ()).throw(urllib.error.HTTPError("m", 401, "no", {}, io.BytesIO(b"")))
    with pytest.raises(MeterlessUnauthorized):
        c.chat("x", "m", [{"role": "user", "content": "hi"}])
    assert c.cancelled.is_set()


def test_a_main_call_gets_a_freed_slot_before_a_waiting_challenge_call():
    s, order = meterless.Slots(1), []
    s.acquire()  # held by a call in flight
    low = threading.Thread(target=lambda: (s.acquire(low=True), order.append("challenge"), s.release()))
    low.start()
    time.sleep(0.05)
    main = threading.Thread(target=lambda: (s.acquire(), order.append("main"), time.sleep(0.05), s.release()))
    main.start()
    time.sleep(0.05)
    s.release()
    main.join(5), low.join(5)
    assert order == ["main", "challenge"]


def test_a_challenge_call_takes_no_slot_a_main_worker_asks_for_again_at_once():
    s, finished, took = meterless.Slots(1), {}, {}

    def reviewer_worker():  # gives its slot back and asks again straight away, as between two batches
        for _ in range(6):
            s.acquire()
            time.sleep(0.03)
            s.release()
            time.sleep(0.01)
        finished["at"] = time.monotonic()

    def challenge_call():
        s.acquire(low=True)
        took["at"] = time.monotonic()
        s.release()

    workers = [threading.Thread(target=reviewer_worker), threading.Thread(target=challenge_call)]
    workers[0].start()
    time.sleep(0.005)
    workers[1].start()
    for w in workers:
        w.join(5)
    assert took["at"] >= finished["at"]  # it waited until the worker had stopped asking


def test_the_certainty_rule_matches_skeptic_targets_on_random_rounds():
    import random
    rng = random.Random(25)
    for _ in range(400):
        n, top = rng.randint(0, 9), rng.randint(1, 3)
        names = [f"R{i}" for i in range(n)]
        passing = [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=rng.choice([10, 20, 20, 30, 40])) for r in names]
        findings = [Finding(r, 10, 3.0, "not_found", "clinical_event",
                            rng.choice(["review_next", "review_next", "lower_priority"]), "x", "y", ["q-s"])
                    for r in names]
        ctx = {"drug": "x", "passing": passing, "evidence_ids": set(), "sources": {}}
        candidates = pipeline.early_skeptic_targets(ctx, findings, top + 1)
        tracer = SimpleNamespace(event=lambda *a, **k: None)
        q = pipeline.ChallengeQueue(ctx, candidates, top, {}, None, None, None, tracer, lambda: 600.0,
                                    RecordingPool(), threading.Event(), RecordingPool())
        verdicts = {f.reaction: Verdict(f.reaction, rng.choice(["accept", "accept", "reject", "unresolved",
                                                                "unreviewed"]), "r") for f in findings}
        for f in rng.sample(findings, len(findings)):
            q.on_verdict(f, verdicts[f.reaction])
        during = list(q.pool.submitted)
        state = {}
        for f in findings:
            pipeline.record(state.setdefault(f.reaction, {"history": []}), f, verdicts[f.reaction], 1)
        targets = pipeline.skeptic_targets(ctx, state, top)
        assert set(during) <= set(targets)  # nothing started during the round is ever outside the targets
        q.finish_round(state, targets)
        assert sorted(q.pool.submitted) == sorted(targets) and len(q.pool.submitted) == len(set(q.pool.submitted))


def test_on_verdict_sees_the_same_verdicts_the_review_returns():
    from app.agents.reviewer import Reviewer

    class LLM:
        tracer = SimpleNamespace(event=lambda *a, **k: None)

        def chat_json(self, agent, model, messages, **kw):
            name = next(r for r in "ABCDE" if f'"reaction": "{r}"' in messages[-1]["content"])
            own = {"A": "accept", "B": "reject", "C": "unresolved", "E": "maybe"}
            verdicts = [{"reaction": name, "decision": own[name], "reason": "r"}] if name in own else []
            if name == "B":  # a verdict for A from a call that never saw A: ignored
                verdicts.append({"reaction": "A", "decision": "reject", "reason": "stray"})
            return {"verdicts": verdicts, "missing": [], "summary": ""}

    class Clerk:
        def recheck(self, drug, reactions, agent="reviewer"):
            return QueryResult("q-r", "", [], []), {r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
                                                    for r in reactions}

    ctx = {"drug": "x", "label": {}, "label_qid": "q-l", "screen_qid": "q-s", "evidence_ids": {"q-s"}, "sources": {},
           "passing": [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in "ABCDE"]}
    findings = [Finding(r, 10, 3.0, "not_assessed", "non_clinical", "lower_priority", "x", "y", ["q-s"])
                for r in "ABCDE"]
    seen = {}
    verdicts, _, _ = Reviewer(LLM(), "m", Clerk(), 2).review(ctx, findings, set("ABCDE"),
                                                             on_verdict=lambda f, v: seen.update({f.reaction: v}))
    assert {v.reaction: v for v in verdicts} == seen
    assert [seen[r].decision for r in "ABCDE"] == ["accept", "reject", "unresolved", "unreviewed", "unreviewed"]


def test_a_low_priority_call_gives_up_at_its_deadline():
    s = meterless.Slots(1)
    s.acquire()  # the Reviewer's round keeps the only slot busy
    t0 = time.monotonic()
    assert s.acquire(low=True, until=t0 + 0.3) is False and 0.25 <= time.monotonic() - t0 < 1.5
    s.release()
    assert s.acquire(low=True, until=time.monotonic() + 2) is True  # free again: taken after the grace


def test_a_review_starved_of_slots_is_skipped_as_out_of_time():
    challenged = {"A": done([{"reaction": "A", "outcome": "challenged", "challenge_reasons": ["x"], "pairs": [],
                              "query_ids": ["q-a"], "summary": "s"}])}
    q = queue(["A"], early=challenged, left=pipeline.CHALLENGE_NEEDS + 0.3)
    q.slots = meterless.Slots(1)
    q.slots.acquire()  # a saturated round 1: no slot comes free before the gate stops holding
    e = entry("A")
    out = q._review("A", e, {**q.ctx})
    assert out["review"] is False and out["counts"]["challenge_not_reviewed"] == 1
    assert "time budget ran out before the Reviewer could look at the challenge" in e["note"] and e["history"] == []
    assert any(k == "budget_stop" and d["step"] == "skeptic challenge review" for k, d in q.tracer.events)
