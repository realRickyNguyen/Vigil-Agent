"""Tests for the World Model's read path in a run: every queue item compared with the verdict the engine holds
from earlier runs (since_last_run), the run summary, the engine's audit entries, and that no prompt reads it.
No network. Run: python -I -m pytest tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.world_model import WorldModel  # noqa: E402
from app.orchestration.pipeline import WORLD_MODEL_READS, remember  # noqa: E402
from app.tracing import progress_line  # noqa: E402

LABEL = {"set_id": "s1", "effective_time": "20260304"}
NEW_LABEL = {"set_id": "s1", "effective_time": "20260804"}


def item(reaction, priority="review_next", coverage="not_found", status="reviewed", a=100, prr=3.0,
         context="clinical_event"):
    return {"reaction": reaction, "a": a, "prr": prr, "label_coverage": coverage, "context": context,
            "review_priority": priority, "workflow_status": status}


def run(path, queue, run_id, at, label=LABEL):
    return remember(WorldModel("bb", path), "montelukast", label, queue, run_id, at)


def by_reaction(queue):
    return {q["reaction"]: q["since_last_run"] for q in queue}


def test_a_first_run_marks_everything_new_and_records_its_audit(tmp_path):
    queue = [item("SPUTUM DISCOLOURED"), item("NAUSEA", status="pending")]
    out = run(tmp_path / "w.json", queue, "run-1", "2026-10-25T01:00:00+00:00")
    assert {s["status"] for s in by_reaction(queue).values()} == {"new"}
    s = out["since_last_run"]
    assert s["compared_with_runs"] == [] and s["new"] == 2 and s["previous_label_version"] is None
    # The engine's own audit entries for this run: the drug, the label fact and one decision per settled item.
    kinds = [a["kind"] for a in out["audit"]]
    assert kinds == ["upsertEntity", "assertFact", "recordDecision"]
    assert all(a["seq"] for a in out["audit"]) and out["read_by"] == WORLD_MODEL_READS
    assert "none" in out["read_by"]["agent_prompts"]
    line = progress_line({"agent": "world_model", "event": "remembered", **out})
    assert "no earlier verdicts" in line


def test_a_later_run_with_the_same_label_says_what_changed_and_why(tmp_path):
    path = tmp_path / "w.json"
    run(path, [item("SPUTUM DISCOLOURED", a=1691, prr=25.7), item("ANGER"), item("PNEUMONIA"),
               item("ASTHMA", priority="lower_priority", coverage="not_assessed", context="treated_condition")],
        "run-1", "2026-10-25T01:00:00+00:00")
    queue = [item("SPUTUM DISCOLOURED", a=1691, prr=25.7),                       # same verdict, same counts
             item("ANGER", priority="insufficient_evidence", a=100),             # same counts, new judgement
             item("ASTHMA", priority="lower_priority", coverage="not_assessed", context="treated_condition", a=140),
             item("BRONCHITIS")]                                                 # never seen before
    out = run(path, queue, "run-2", "2026-10-26T01:00:00+00:00")
    s = by_reaction(queue)
    assert s["SPUTUM DISCOLOURED"]["status"] == "unchanged" and s["SPUTUM DISCOLOURED"]["changed"] == []
    assert s["ANGER"]["status"] == "changed"
    assert s["ANGER"]["changed"] == [{"field": "review_priority", "earlier": "review_next",
                                      "now": "insufficient_evidence"}]
    assert "same evidence" in s["ANGER"]["why"] and s["ANGER"]["earlier"]["run_id"] == "run-1"
    assert s["ASTHMA"]["status"] == "unchanged" and "from 100 to 140" in s["ASTHMA"]["why"]
    assert s["BRONCHITIS"]["status"] == "new"
    assert not any(x["label_changed"] for r, x in s.items() if r != "BRONCHITIS")
    summary = out["since_last_run"]
    assert summary["compared_with_runs"] == ["run-1"] and summary["label_version_changed"] is False
    assert (summary["changed"], summary["unchanged"], summary["new"]) == (1, 2, 1)
    assert summary["changed_items"] == ["ANGER"]
    # PNEUMONIA was sent to review next before and this run did not assess it: the analyst is told.
    assert summary["earlier_review_next_not_assessed"] == [{"reaction": "PNEUMONIA", "earlier_run": "run-1"}]
    assert summary["earlier_verdicts_not_in_this_run"] == 1
    line = progress_line({"agent": "world_model", "event": "remembered", **out})
    assert "1 changed, 2 unchanged, 1 new" in line


def test_a_new_label_version_is_named_as_the_reason(tmp_path):
    path = tmp_path / "w.json"
    run(path, [item("ANGER"), item("ASTHMA", priority="lower_priority", coverage="covered")],
        "run-1", "2026-10-25T01:00:00+00:00")
    queue = [item("ANGER", coverage="covered", priority="lower_priority"),
             item("ASTHMA", priority="lower_priority", coverage="covered")]
    out = run(path, queue, "run-2", "2026-10-26T01:00:00+00:00", label=NEW_LABEL)
    s = by_reaction(queue)
    assert s["ANGER"]["status"] == "changed" and s["ANGER"]["label_changed"] is True
    assert "20260304 to 20260804" in s["ANGER"]["why"] and "reopened" in s["ANGER"]["why"]
    assert s["ASTHMA"]["status"] == "unchanged" and s["ASTHMA"]["label_changed"] is True
    assert s["ANGER"]["earlier"]["label_effective"] == "20260304"
    assert out["since_last_run"]["label_version_changed"] is True
    assert out["since_last_run"]["previous_label_version"] == LABEL
    assert sorted(r["reaction"] for r in out["reopened"]) == ["ANGER", "ASTHMA"]   # the existing behaviour stays
    assert "reopen" in [a["kind"] for a in out["audit"]]


def test_an_item_not_settled_now_shows_the_earlier_verdict_for_reference(tmp_path):
    path = tmp_path / "w.json"
    run(path, [item("ANGER")], "run-1", "2026-10-25T01:00:00+00:00")
    queue = [item("ANGER", status="not_reviewed")]
    out = run(path, queue, "run-2", "2026-10-26T01:00:00+00:00")
    s = by_reaction(queue)["ANGER"]
    assert s["status"] == "not_settled_now" and s["why"].startswith("Not settled in this run (not_reviewed)")
    assert s["earlier"]["review_priority"] == "review_next"
    assert out["decisions_recorded"] == 0
    # The earlier verdict is still the one the World Model holds.
    w = WorldModel("bb", path)
    assert [d["value"]["run_id"] for d in w.decisions()] == ["run-1"]


def test_verdicts_recorded_before_counts_were_stored_still_compare(tmp_path):
    # Runs before 26 Oct stored no report counts with a verdict.
    path = tmp_path / "w.json"
    w = WorldModel("bb", path)
    src = {"kind": "openfda-label-via-zetaris", "at": "2026-10-23T01:00:00+00:00", "runId": "old"}
    drug = w.upsert_entity(type="drug", name="montelukast", source=src)
    fact = w.assert_fact(about=drug["id"], predicate="label_version", value=LABEL, source=src)
    w.record_decision(key=f"{drug['id']}|ANGER", about=drug["id"], depends_on=[fact["id"]], source=src,
                      value={"reaction": "ANGER", "run_id": "old", "workflow_status": "reviewed",
                             "label_coverage": "not_found", "context": "clinical_event",
                             "review_priority": "review_next"})
    queue = [item("ANGER")]
    run(path, queue, "run-2", "2026-10-26T01:00:00+00:00")
    s = by_reaction(queue)["ANGER"]
    assert s["status"] == "unchanged" and "were not recorded" in s["why"] and s["earlier"]["a"] is None
    # This run's verdict now carries its counts for the next comparison.
    assert WorldModel("bb", path).decisions()[0]["value"]["a"] == 100


def test_a_whole_run_compares_with_the_last_run_but_no_prompt_reads_the_world_model(tmp_path, monkeypatch):
    # Bryan's whole-run fake (fake Data Clerk and model), run twice against the same World Model file.
    from test_safety_net import net_raw
    from test_safety_net import run as whole_run
    first, first_prompts = whole_run(tmp_path, monkeypatch, net_raw())
    second, second_prompts = whole_run(tmp_path, monkeypatch, net_raw())
    assert {q["since_last_run"]["status"] for q in first["review_queue"]} == {"new"}
    assert {q["since_last_run"]["status"] for q in second["review_queue"]} == {"unchanged"}
    s = second["world_model"]["since_last_run"]
    assert s["compared_with_runs"] == [first["run_id"]] and s["unchanged"] == len(second["review_queue"])
    # Earlier verdicts never reach a model: the second run's prompts are word for word the first run's.
    assert sorted(second_prompts) == sorted(first_prompts) and len(second_prompts) > 0
    assert not any("since_last_run" in p or first["run_id"] in p for p in second_prompts)
    # The engine's audit entries for the run are in the trace, inside the World Model's event.
    events = [json.loads(line) for line in (tmp_path / second["trace"]).read_text(encoding="utf-8").splitlines()]
    remembered = [e for e in events if e["event"] == "remembered"]
    assert len(remembered) == 1 and remembered[0]["audit"] and remembered[0]["since_last_run"]["unchanged"] > 0


def test_the_api_returns_the_comparison(tmp_path):
    from dataclasses import replace
    from app.config import get_settings
    from app.server import success_body
    queue = [item("ANGER")]
    world = run(tmp_path / "w.json", queue, "run-1", "2026-10-25T01:00:00+00:00")
    d = {"run_id": "r", "drug": "montelukast", "data": {"drug_reports": 1}, "trace": "trace-r.jsonl",
         "counts": {"passing_evans": 1, "reactions_screened": 1, "assessed": 1, "decided_by_rule": 0, "reviewed": 1,
                    "unresolved": 0, "pending": 0, "failed": 0, "review_next": 1},
         "review_queue": [{**queue[0], "reasoning": "r"}], "world_model": world}
    out = success_body(d, replace(get_settings(), logs_dir=tmp_path), 1.0)["output"]
    assert out["since_last_run"]["new"] == 1
    assert out["recommendations"][0]["since_last_run"]["status"] == "new"
    json.dumps(out)  # serialisable as the API sends it
