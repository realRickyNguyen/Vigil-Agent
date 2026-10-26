"""Offline tests for sample mode (app/sample_mode.py): recording at the two adapters and replaying with no service.
Run: python -I -m pytest tests"""
import io
import json
import sys
import urllib.error
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import sample_mode  # noqa: E402
from app.adapters.meterless import MeterlessError, NightshiftClient  # noqa: E402
from app.adapters.zetaris import AlreadyExists, ZetarisClient, ZetarisError  # noqa: E402
from app.config import for_sample_mode, get_settings  # noqa: E402
from app.tracing import Tracer, progress_line  # noqa: E402


def settings(tmp_path, **kw):
    return replace(get_settings(), logs_dir=tmp_path, samples_dir=tmp_path / "samples", sample_mode=False,
                   zetaris_key="k", meterless_token="t", max_retries=1, **kw)


def reply(text, model="nvidia/nemotron-3-ultra-550b-a55b"):
    return {"model": model, "usage": {"completion_tokens": 3}, "meterless": None,
            "choices": [{"message": {"role": "assistant", "content": text}}]}


def msgs(user, system="You are the Analyst."):
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def record(tmp_path, monkeypatch, zetaris_answers, model_answers):
    """A recorded 'run': the fake services answer in order; returns the saved recording's path."""
    s = settings(tmp_path)
    monkeypatch.setattr(ZetarisClient, "_post", lambda self, sql, timeout: zetaris_answers[sql].pop(0)())
    monkeypatch.setattr(NightshiftClient, "_post", lambda self, body: model_answers.pop(0)())
    monkeypatch.setattr("app.adapters.meterless.time.sleep", lambda s: None)
    monkeypatch.setattr("app.adapters.zetaris.time.sleep", lambda s: None)
    tracer = Tracer(tmp_path, echo=False)
    with sample_mode.recording(s, "montelukast") as rec:
        z, llm, info = sample_mode.clients(s, tracer, "montelukast")
        assert isinstance(z, sample_mode.RecordingZetaris) and info is None
        res = z.run("SELECT 1", "one")
        assert not z.ensure("CREATE x", "create x")  # already exists
        with pytest.raises(ZetarisError):
            z.run("SELECT broken", "broken")
        first = llm.chat("analyst", "m", msgs("classify NIGHTMARE from q-1"))  # a first-byte cut, then a reply
        second = llm.chat("reviewer", "m", msgs("review NIGHTMARE", "You are the Reviewer."))
    assert rec.summary["model_calls"] == 3
    return s, res, first, second


def already_exists():
    raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b'{"msg": "Table already exists"}'))


def zetaris_down():
    raise urllib.error.URLError("Connection refused")


def ttfb():
    e = MeterlessError("provider_error: ttfb_timeout:nvidia/nemotron-3-ultra-550b-a55b")
    e.detail, e.retryable = "ttfb_timeout:nvidia/nemotron-3-ultra-550b-a55b", True
    raise e


def recorded(tmp_path, monkeypatch):
    zetaris = {"SELECT 1": [lambda: {"headers": ["x"], "data": [[1]]}], "CREATE x": [already_exists],
               "SELECT broken": [zetaris_down, zetaris_down]}
    model = [ttfb, lambda: reply('{"findings": []}'), lambda: reply('{"verdicts": []}')]
    return record(tmp_path, monkeypatch, zetaris, model)


def test_a_recorded_run_replays_with_no_service(tmp_path, monkeypatch):
    s, live_res, first, second = recorded(tmp_path, monkeypatch)
    # Any network use now fails the test.
    monkeypatch.setattr(ZetarisClient, "_post", lambda *a: pytest.fail("Zetaris was called in sample mode"))
    monkeypatch.setattr(NightshiftClient, "_post", lambda *a: pytest.fail("Nightshift was called in sample mode"))
    s = for_sample_mode(replace(s, zetaris_key="", meterless_token=""))  # a judge has neither
    tracer = Tracer(tmp_path, echo=False)
    z, llm, info = sample_mode.clients(s, tracer, "montelukast")
    assert info["replayed_from_run"] and "Replayed from a recorded live run" in info["note"]
    res = z.run("SELECT 1", "one")
    assert (res.query_id, res.rows) == (live_res.query_id, live_res.rows)  # same evidence ID as the live run
    assert z.ensure("CREATE x", "create x") is False
    with pytest.raises(ZetarisError, match="Connection refused"):
        z.run("SELECT broken", "broken")
    with pytest.raises(ZetarisError, match="not in the recording"):
        z.run("SELECT never recorded", "missing")
    assert llm.chat("analyst", "m", msgs("classify NIGHTMARE from q-1")) == first   # retried past the cut
    assert llm.chat("reviewer", "m", msgs("review NIGHTMARE", "You are the Reviewer.")) == second
    events = [json.loads(line) for line in tracer.path.read_text(encoding="utf-8").splitlines()]
    assert all(e.get("sample_mode") is True for e in events)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "sample_mode" and "replay_miss" in kinds and "llm_retry" in kinds
    assert progress_line(events[0]).startswith("Sample mode: replaying recorded run")


def test_a_slightly_different_prompt_uses_the_closest_recorded_reply(tmp_path, monkeypatch):
    s, *_ = recorded(tmp_path, monkeypatch)
    tracer = Tracer(tmp_path, echo=False)
    _, llm, _ = sample_mode.clients(for_sample_mode(s), tracer, "montelukast")
    # One evidence ID differs: close enough to reuse the recorded reply, and the trace says so.
    assert llm.chat("reviewer", "m", msgs("review NIGHTMARE.", "You are the Reviewer.")) == '{"verdicts": []}'
    near = [json.loads(x) for x in tracer.path.read_text(encoding="utf-8").splitlines()
            if '"replay_nearest"' in x]
    assert near and 0.9 <= near[0]["similarity"] < 1
    # A prompt of another agent, or far from any recorded one, is not in the recording: no retry, a clear error.
    with pytest.raises(MeterlessError, match="not in the recording"):
        llm.chat("skeptic", "m", msgs("something else entirely", "You are someone else."))


def test_a_replay_runs_with_the_recorded_settings_and_its_own_world_model(tmp_path, monkeypatch):
    s, *_ = recorded(tmp_path, monkeypatch)
    judge = for_sample_mode(replace(s, parallel=1, reviewer_rounds=3, run_budget=60, analyst_top=5))
    replayed = sample_mode.with_recorded_settings(judge, "montelukast")
    assert (replayed.parallel, replayed.reviewer_rounds, replayed.run_budget, replayed.analyst_top) == \
           (s.parallel, s.reviewer_rounds, s.run_budget, s.analyst_top)
    assert replayed.world_path == tmp_path / "sample-world-model.json" and replayed.sample_mode


def test_a_drug_without_a_recording_says_what_can_be_replayed(tmp_path, monkeypatch):
    s, *_ = recorded(tmp_path, monkeypatch)
    with pytest.raises(sample_mode.NoSampleRecording, match="can replay: montelukast"):
        sample_mode.load(for_sample_mode(s), "metformin")
    assert sample_mode.available(s) == ["montelukast"]


def test_the_recorded_montelukast_sample_replays_to_its_live_dossier(tmp_path):
    """The committed recording (samples/montelukast.json.gz) replayed through the whole pipeline gives the live run's
    queue, rounds and counts (output_examples/montelukast/), offline, with every prompt found in the recording."""
    from app.orchestration import pipeline
    root = Path(__file__).resolve().parents[1]
    live = json.loads(next((root / "output_examples" / "montelukast").glob("dossier-*.json")).read_text(encoding="utf-8"))
    s = for_sample_mode(replace(get_settings(), logs_dir=tmp_path, samples_dir=root / "samples", zetaris_key="",
                                meterless_token=""))
    tracer = Tracer(tmp_path, echo=False)
    d = pipeline.investigate({"drug": "montelukast"}, s, tracer)
    key = lambda q: (q["reaction"], q.get("review_priority"), q["workflow_status"], q.get("label_coverage"),  # noqa: E731
                     q.get("context"))
    assert [key(q) for q in d["review_queue"]] == [key(q) for q in live["review_queue"]]
    assert d["rounds"] == live["rounds"] and d["counts"] == live["counts"]
    assert d["sample_mode"]["replayed_from_run"] == live["run_id"]
    events = [json.loads(line) for line in tracer.path.read_text(encoding="utf-8").splitlines()]
    assert all(e.get("sample_mode") for e in events)
    assert not [e for e in events if e["event"] in ("replay_miss", "replay_nearest")]
    # The replay keeps its own World Model, never the live one.
    assert (tmp_path / "sample-world-model.json").exists()
