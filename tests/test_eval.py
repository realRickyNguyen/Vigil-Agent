"""Tests for the evaluation scorer (eval/score.py) on small hand-made runs. No network."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.score import agreement, gold_provenance, load_gold, load_run, score_run, summarise  # noqa: E402

EVAL = Path(__file__).resolve().parents[1] / "eval"

GOLD_ROWS = [
    {"drug": "x", "reaction": "A", "gold": "on_label", "ambiguous": False},
    {"drug": "x", "reaction": "B", "gold": "likely_indication_or_disease", "ambiguous": False},
    {"drug": "x", "reaction": "C", "gold": "possible_new_signal", "ambiguous": False},
    {"drug": "x", "reaction": "D", "gold": "not_meaningful", "ambiguous": False},
    {"drug": "x", "reaction": "E", "gold": "on_label", "ambiguous": True},
]


def f(reaction, cls, who="analyst"):
    return {"reaction": reaction, "classification": cls, "decided_by": who}


def write_run(logs, run_id, round1, accepted, excluded=(), not_reviewed=()):
    events = [{"event": "run_start"}, {"event": "findings", "round": 1, "findings": round1},
              {"event": "findings", "round": 2, "findings": []}]
    (logs / f"trace-{run_id}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    dossier = {"run_id": run_id, "drug": "x", "findings": list(accepted), "excluded_by_judge": list(excluded),
               "not_reviewed_by_judge": list(not_reviewed), "not_classified": [], "rounds": []}
    (logs / f"dossier-{run_id}.json").write_text(json.dumps(dossier), encoding="utf-8")


def gold(tmp_path):
    p = tmp_path / "gold.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in GOLD_ROWS), encoding="utf-8")
    return load_gold(p)


def test_reviewer_effect_categories(tmp_path):
    write_run(tmp_path, "r1",
              round1=[f("A", "on_label"), f("B", "possible_new_signal"), f("C", "on_label"), f("D", "not_meaningful")],
              accepted=[f("A", "on_label"), f("B", "likely_indication_or_disease"), f("E", "on_label")],
              excluded=[f("C", "on_label")])
    s = score_run(load_run("r1", tmp_path), gold(tmp_path))
    assert s["round1"] == {"scored": 4, "correct": 2, "accuracy": 0.5}
    assert s["final"] == {"scored": 2, "correct": 2, "accuracy": 1.0}  # ambiguous E is not scored
    assert s["reviewer_effect"] == {"kept_correct": 1, "fixed": 1, "caught_wrong": 1, "dropped": 1}
    assert s["ambiguous_classified"] == 1


def test_added_after_missing_and_new_signal_precision(tmp_path):
    write_run(tmp_path, "r2", round1=[f("A", "on_label")],
              accepted=[f("A", "on_label"), f("C", "possible_new_signal"), f("D", "possible_new_signal", "rule")])
    s = score_run(load_run("r2", tmp_path), gold(tmp_path))
    assert s["added_after_missing"] == {"count": 2, "scored": 2, "correct": 1, "accuracy": 0.5}
    assert s["new_signal_precision"] == {"claimed": 2, "gold_new": 1}
    assert s["by_decider"] == {"analyst": {"correct": 2}, "rule": {"wrong": 1}}


def test_v2_review_queue_dossier(tmp_path):
    queue = [
        {**f("C", "possible_new_signal"), "review_priority": "review_next", "workflow_status": "reviewed"},
        {**f("A", "possible_new_signal"), "review_priority": "review_next", "workflow_status": "reviewed"},
        {**f("B", "on_label"), "review_priority": "lower_priority", "workflow_status": "unresolved"},
        {"reaction": "D", "workflow_status": "pending"},
    ]
    events = [{"event": "findings", "round": 1, "findings": [f("B", "on_label"), f("C", "possible_new_signal")]}]
    (tmp_path / "trace-v2.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (tmp_path / "dossier-v2.json").write_text(json.dumps({"drug": "x", "review_queue": queue}), encoding="utf-8")
    s = score_run(load_run("v2", tmp_path), gold(tmp_path))
    assert s["unresolved"] == ["B"] and s["open_items"] == {"pending": 1}
    assert s["reviewer_effect"] == {"unresolved_was_wrong": 1, "kept_correct": 1}
    assert s["review_next"] == {"count": 2, "gold": {"possible_new_signal": 1, "on_label": 1}}


def test_repeat_run_agreement(tmp_path):
    write_run(tmp_path, "a", round1=[], accepted=[f("A", "on_label"), f("B", "likely_indication_or_disease")])
    write_run(tmp_path, "b", round1=[], accepted=[f("A", "on_label"), f("B", "possible_new_signal"), f("C", "on_label")])
    out = agreement([load_run("a", tmp_path), load_run("b", tmp_path)])
    p = out["pairs"][0]
    assert (p["accepted_in_both"], p["same_classification"]) == (2, 1)
    assert p["reaction_overlap_jaccard"] == round(2 / 3, 3)
    assert out["classification_agreement"] == 0.5


def test_report_header_says_who_reviewed_the_gold():
    rows = {(r["drug"], r["reaction"]): r for r in GOLD_ROWS}
    assert gold_provenance(rows) == "labelled by an AI assistant, not yet reviewed by a person"
    by = {"by": "a team member", "date": "2026-10-26"}
    partly = {k: {**r, "review": {"verdict": "agree", **by} if r["reaction"] in "AE" else {"verdict": "not reviewed"}}
              for k, r in rows.items()}
    assert gold_provenance(partly) == ("drafted by an AI assistant; 2 of 5 rows reviewed by a team member on "
                                       "2026-10-26, covering 1 of its 4 clear rows; the other clear rows are "
                                       "AI-drafted, see `eval/GOLD_REVIEW.md`")
    fully = {k: {**r, "review": {"verdict": "change", **by}} for k, r in rows.items()}
    assert "5 of 5 rows reviewed by a team member on 2026-10-26, covering all 4 clear rows" in gold_provenance(fully)
    report = summarise([], [], "gold.jsonl", fully)
    assert "not yet reviewed" not in report and "covering all 4 clear rows" in report


def test_report_header_for_the_repo_gold_files():
    for name in ("gold_v1.jsonl", "gold_v2.jsonl", "gold_newdrugs_v1.jsonl"):
        assert gold_provenance(load_gold(EVAL / name)).endswith("not yet reviewed by a person")
    assert "covering all 68 clear rows" in gold_provenance(load_gold(EVAL / "gold_v2_reviewed.jsonl"))
    assert "15 of 217 rows reviewed" in gold_provenance(load_gold(EVAL / "gold_newdrugs_v1_reviewed.jsonl"))
