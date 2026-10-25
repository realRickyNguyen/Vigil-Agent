"""Offline checks of the run-time changes: Zetaris work that runs side by side or early, and retries that do not
wait for nothing. No Zetaris, no Nightshift. Run: python -I -m pytest tests"""
import json
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless  # noqa: E402
from app.adapters.meterless import read_sse  # noqa: E402
from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.agents.analyst import Analyst  # noqa: E402
from app.agents.reviewer import Reviewer  # noqa: E402
from app.data.faers import DataClerk, DrugNotFound  # noqa: E402
from app.orchestration.pipeline import (early_recheck, early_skeptic_targets, gather_evidence,  # noqa: E402
                                        skeptic_evidence)
from app.schemas import Finding, Signal  # noqa: E402

WAIT = 5  # seconds a test waits for work that should be running at the same time, before it fails


class FakeTracer:
    def __init__(self):
        self.events = []

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


class OrderedZetaris:
    """Records statements in order. The three raw-table statements wait for each other, so the test fails if they
    are sent one at a time."""
    def __init__(self):
        self.sql, self.lock, self.raws = [], threading.Lock(), threading.Barrier(3, timeout=WAIT)

    def ensure(self, sql, purpose):
        if "REST TABLE" in sql:
            self.raws.wait()
        with self.lock:
            self.sql.append(sql)
        return "REST TABLE" in sql

    def run(self, sql, purpose, **kw):
        with self.lock:
            self.sql.append(sql)


def test_register_drug_sends_the_raw_tables_together_and_views_after_them():
    z = OrderedZetaris()
    created = DataClerk(z).register_drug("montelukast")
    assert list(created) == ["reactions_raw", "total_raw", "label_raw", "reactions", "total"]
    assert created == {"reactions_raw": True, "total_raw": True, "label_raw": True, "reactions": False, "total": False}
    last_raw = max(i for i, s in enumerate(z.sql) if "REST TABLE" in s)
    later = z.sql[last_raw + 1:]
    assert sum("SCHEMASTORE VIEW" in s for s in later) == 2  # a view reads its raw table, so it must come after
    assert sum(s.startswith("CACHE TABLE") for s in later) == 3


class EvidenceClerk:
    """The totals query only answers once the screen query has started, so a run that waits for the totals
    before starting the others fails."""
    def __init__(self, no_reports=False):
        self.screen_started, self.no_reports, self.combination_for = threading.Event(), no_reports, None

    def totals(self, drug):
        if not self.screen_started.wait(WAIT):
            raise AssertionError("the screen did not start alongside the totals")
        if self.no_reports:
            raise DrugNotFound("no reports")
        return {"drug_reports": 42, "query_id": "q-t"}

    def signals(self, drug):
        self.screen_started.set()
        return SimpleNamespace(query_id="q-s"), []

    def label(self, drug):
        return "q-l", {}

    def seriousness(self, drug):
        return None, {}

    def combination_products(self, drug, drug_reports):
        self.combination_for = drug_reports
        return None, None

    def scope(self, drug):
        return None, None


def test_evidence_queries_start_alongside_the_totals():
    clerk = EvidenceClerk()
    totals, (screen, signals), (label_qid, _), combo, severity, scope = gather_evidence(clerk, "x")
    assert totals["drug_reports"] == 42 and screen.query_id == "q-s" and label_qid == "q-l"
    assert clerk.combination_for == 42  # the combination share is still of the drug's own reports


def test_a_drug_with_no_reports_still_fails_at_the_totals():
    with pytest.raises(DrugNotFound):
        gather_evidence(EvidenceClerk(no_reports=True), "x")


class CountingClerk:
    def __init__(self):
        self.calls = []

    def recheck(self, drug, reactions, agent="reviewer"):
        self.calls.append(list(reactions))
        return SimpleNamespace(query_id="q-new"), {r: Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50)
                                                   for r in reactions}


class AcceptLLM:
    def __init__(self):
        self.tracer = FakeTracer()

    def chat_json(self, agent, model, messages, **kw):
        batch = json.loads(messages[-1]["content"].split("Analyst findings with code checks:\n", 1)[1])
        return {"verdicts": [{"reaction": p["reaction"], "decision": "accept", "reason": "ok", "objection": "o",
                              "next_check": "n"} for p in batch], "missing": [], "summary": ""}


def review_ctx():
    return {"drug": "x", "label": {}, "label_qid": "q-l", "screen_qid": "q-s", "evidence_ids": {"q-s"},
            "passing": [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in "ABC"]}


def lower(reaction):
    return Finding(reaction, 10, 3.0, "not_assessed", "non_clinical", "lower_priority", "x", "y", ["q-s"])


def test_reviewer_uses_an_early_recheck_that_covers_every_finding():
    clerk = CountingClerk()
    early = (["A", "B", "C"], CountingClerk().recheck("x", ["A", "B", "C"]))
    verdicts, _, _ = Reviewer(AcceptLLM(), "m", clerk, 2).review(review_ctx(), [lower("A"), lower("B")], {"A", "B"},
                                                                recheck=early)
    assert clerk.calls == [] and [v.decision for v in verdicts] == ["accept", "accept"]
    assert all(v.checks["numbers_match"][0] for v in verdicts)


def test_reviewer_runs_the_recheck_itself_when_the_early_one_misses_a_finding():
    clerk = CountingClerk()
    early = (["A"], CountingClerk().recheck("x", ["A"]))
    Reviewer(AcceptLLM(), "m", clerk, 2).review(review_ctx(), [lower("A"), lower("B")], {"A", "B"}, recheck=early)
    assert clerk.calls == [["A", "B"]]


def test_a_failed_early_recheck_leaves_the_recheck_to_the_reviewer():
    failed = Future()
    failed.set_exception(ZetarisError("HTTP 500"))
    assert early_recheck({"names": ["A"], "job": failed}) is None
    assert early_recheck({}) is None
    done = Future()
    done.set_result(("res", {}))
    assert early_recheck({"names": ["A"], "job": done}) == (["A"], ("res", {}))


class PickLLM:
    """Picks the first extra row offered, classifies every row it is shown, and records what it classified."""
    def __init__(self):
        self.tracer, self.classified, self.lock = FakeTracer(), [], threading.Lock()

    def chat_json(self, agent, model, messages, **kw):
        user = messages[-1]["content"]
        rows = [line.split(" | ") for line in user.splitlines() if line.count(" | ") >= 3
                and not line.startswith("reaction")]
        if "choose up to" in messages[0]["content"]:
            return {"picked": [{"reaction": rows[0][0], "why": "w"}]}
        with self.lock:
            self.classified += [r[0] for r in rows]
        return {"findings": [{"reaction": r[0], "a": int(r[1]), "prr": float(r[2]), "context": "clinical_event",
                              "label_coverage": "not_found", "review_priority": "review_next", "reasoning": "x",
                              "next_check": "y", "evidence": ["q-s"]} for r in rows], "summary": ""}


def test_the_analyst_names_its_reactions_before_classifying_the_extra_picks():
    passing = [Signal(n, a=10, b=1, c=1, d=1, prr=3.0, chi2=50 - i) for i, n in enumerate("ABCDEF")]
    ctx = {"drug": "x", "passing": passing, "label": {}, "label_qid": "q-l", "screen_qid": "q-s",
           "screen_shown": 6, "totals": {"drug_reports": 1, "all_reports": 2, "data_last_updated": "d",
                                         "query_id": "q-t"}}
    llm, seen = PickLLM(), {}
    findings, _ = Analyst(llm, "m", parallel=2, top=3, extra=1).run(
        ctx, on_selection=lambda picked: seen.update(picked=list(picked), classified=list(llm.classified)))
    assert seen["picked"] == ["A", "B", "C", "D"]
    assert sorted(seen["classified"]) == ["A", "B", "C"]  # the extra pick, D, is classified after the callback
    assert {f.reaction for f in findings} == set("ABCD")


def test_early_skeptic_targets_are_the_analysts_strongest_review_next_findings():
    ctx = {"passing": [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=c) for r, c in
                       (("A", 10), ("B", 40), ("C", 30), ("D", 20), ("E", 50))]}
    findings = [Finding(r, 10, 3.0, "not_found", "clinical_event", p, "x", "y", ["q-s"]) for r, p in
                (("A", "review_next"), ("B", "review_next"), ("C", "review_next"), ("D", "review_next"),
                 ("E", "lower_priority"))]
    assert early_skeptic_targets(ctx, findings, 3) == ["B", "C", "D"]


class CountingSkeptic:
    def __init__(self):
        self.checked = []

    def check(self, drug, reaction, prr):
        self.checked.append(reaction)
        return {"reaction": reaction, "outcome": "no_challenge", "pairs": [], "query_ids": [f"q-{reaction}"]}


def test_skeptic_evidence_reuses_early_checks_and_runs_only_the_rest():
    ctx = {"drug": "x", "passing": [Signal(r, a=10, b=1, c=1, d=1, prr=3.0, chi2=50) for r in "ABC"]}
    skeptic = CountingSkeptic()
    early = {"A": {"reaction": "A", "early": True}, "C": {"reaction": "C", "early": True}}
    out = skeptic_evidence(ctx, skeptic, ["C", "B", "A"], early)
    assert [e["reaction"] for e in out] == ["C", "B", "A"] and skeptic.checked == ["B"]
    assert out[0].get("early") and out[2].get("early") and not out[1].get("early")
    assert skeptic_evidence(ctx, skeptic, ["A"], early) == [early["A"]] and skeptic.checked == ["B"]


def sse(*frames):
    return [("data: " + (f if isinstance(f, str) else json.dumps(f))).encode() for f in frames]


OK = sse({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}, "[DONE]")


@pytest.mark.parametrize("detail, waits", [("ttfb_timeout:nvidia/nemotron-3-ultra-550b-a55b", []),
                                           ("provider_deadline", [5])])
def test_a_first_byte_cut_is_retried_at_once_and_other_failures_still_wait(monkeypatch, detail, waits):
    sleeps = []
    monkeypatch.setattr(meterless.time, "sleep", lambda s: sleeps.append(s))
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=1), FakeTracer())
    replies = [sse({"error": {"code": "provider_error", "meterless_detail": detail}}), OK]
    monkeypatch.setattr(client, "_post", lambda body: read_sse(replies.pop(0)))
    assert client.chat("analyst", "m", [{"role": "user", "content": "hi"}]) == "ok"
    assert sleeps == waits
