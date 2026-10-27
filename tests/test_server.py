"""Offline tests for the HTTP entry point (POST /run, GET /runs/<run_id>, GET /health) and the Docker address
handling. The pipeline is replaced by a stand-in, so no Zetaris or Nightshift is needed.
Run: python -I -m pytest tests"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.adapters.meterless import MeterlessError, MeterlessUnauthorized  # noqa: E402
from app.adapters.zetaris import ZetarisError  # noqa: E402
from app.data.faers import DrugNotFound  # noqa: E402
from app.server import BadRequest, Runner, classify_error, make_handler, parse_request  # noqa: E402
from app.tracing import RunStopped, Tracer  # noqa: E402


def settings(tmp_path, **kw):
    return replace(config.get_settings(), logs_dir=tmp_path, sample_mode=False, **kw)


def dossier(run_id, drug):
    queue = [{"reaction": "NIGHTMARE", "a": 1200, "prr": 7.1, "label_coverage": "covered", "context": "clinical_event",
              "review_priority": "lower_priority", "workflow_status": "reviewed"},
             {"reaction": "SLEEP TERROR", "a": 700, "prr": 14.3, "label_coverage": "not_found",
              "context": "clinical_event", "review_priority": "review_next", "workflow_status": "reviewed",
              "reasoning": "r", "strongest_objection": "o", "next_check": "n", "evidence": ["q-1"]},
             {"reaction": "ALOPECIA", "a": 300, "prr": 2.1, "review_priority": "review_next",
              "workflow_status": "unresolved"}]
    return {"run_id": run_id, "drug": drug, "data": {"drug_reports": 5000},
            "counts": {"passing_evans": 40, "reactions_screened": 999, "assessed": 3, "decided_by_rule": 1,
                       "reviewed": 2, "unresolved": 1, "pending": 0, "failed": 0, "review_next": 1},
            "review_queue": queue, "trace": f"trace-{run_id}.jsonl", "nightshift_warnings": [],
            "run_time": {"seconds": 1}}


def fake_investigate(request, s, tracer):
    tracer.event("orchestrator", "run_start", request=request, analyst_model="m", reviewer_model="m")
    d = dossier(tracer.run_id, request["drug"].lower())
    (s.logs_dir / f"dossier-{tracer.run_id}.json").write_text(json.dumps(d), encoding="utf-8")
    return d


def failing(error):
    def run(request, s, tracer):
        raise error
    return run


def test_both_request_shapes_are_accepted():
    assert parse_request({"drug": "montelukast"}) == (None, {"drug": "montelukast"}, {})
    assert parse_request({"run_id": "demo-001", "input": {"drug": "metformin"}, "options": {"wait": False}}) == \
        ("demo-001", {"drug": "metformin"}, {"wait": False})
    for bad in ([], {}, {"input": {"query": "x"}}, {"drug": 3}, {"drug": "x", "options": []},
                {"drug": "x", "run_id": "../etc/passwd"}):
        with pytest.raises(BadRequest):
            parse_request(bad)


def test_errors_map_to_types_statuses_and_recoverability():
    assert classify_error(ValueError("bad name")) == ("InvalidInput", 400, False)
    assert classify_error(DrugNotFound("none")) == ("DrugNotFound", 404, False)
    assert classify_error(MeterlessUnauthorized("401")) == ("NightshiftUnauthorized", 502, False)
    assert classify_error(MeterlessError("deadline")) == ("NightshiftUnavailable", 502, True)
    assert classify_error(ZetarisError("refused")) == ("ZetarisUnavailable", 502, True)
    assert classify_error(KeyError("x")) == ("InternalError", 500, False)


def test_a_run_returns_the_recommendations_and_where_the_logs_are(tmp_path):
    status, out = Runner(settings(tmp_path), fake_investigate).run(
        {"run_id": "demo-001", "input": {"drug": "Montelukast"}})
    assert status == 200 and out["status"] == "success" and out["run_id"] == "demo-001"
    assert out["log_file"] == "logs/trace-demo-001.jsonl" and (tmp_path / "trace-demo-001.jsonl").exists()
    assert [r["reaction"] for r in out["output"]["recommendations"]] == ["SLEEP TERROR"]  # accepted review_next
    assert out["output"]["unresolved"] == ["ALOPECIA"]
    assert "1 to review next" in out["output"]["summary"]
    assert {a["name"] for a in out["agents"]} == {"Data Clerk", "Analyst", "Reviewer", "Skeptic"}
    assert out["models"]["provider"] == "Meterless Nightshift" and out["execution_time_seconds"] >= 0


def test_a_failed_run_is_a_structured_error_recorded_in_the_trace(tmp_path):
    status, out = Runner(settings(tmp_path), failing(ZetarisError("Connection refused"))).run({"drug": "montelukast"})
    assert status == 502 and out["status"] == "error"
    assert out["error"]["type"] == "ZetarisUnavailable" and out["error"]["recoverable"] is True
    trace = (tmp_path / out["log_file"].split("/")[-1]).read_text(encoding="utf-8")
    assert '"run_error"' in trace
    status, out = Runner(settings(tmp_path), fake_investigate).run({"drug": "x/../y"})
    assert status == 400 and out["error"]["type"] == "InvalidInput"


def test_one_run_at_a_time_and_polling(tmp_path):
    release = threading.Event()

    def slow(request, s, tracer):
        release.wait(5)
        return fake_investigate(request, s, tracer)

    runner = Runner(settings(tmp_path), slow)
    status, out = runner.run({"run_id": "first", "input": {"drug": "montelukast"}, "options": {"wait": False}})
    assert status == 202 and out["status"] == "running" and out["poll"] == "/runs/first"
    assert runner.status("first") == (200, {"run_id": "first", "status": "running", "log_file": "logs/trace-first.jsonl"})
    status, busy = runner.run({"drug": "metformin"})
    assert status == 409 and busy["error"]["type"] == "Busy" and busy["error"]["recoverable"] is True
    assert runner.health()["busy"] and runner.health()["current_run"] == "first"
    assert runner.health()["current_drug"] == "montelukast"  # named the busy run, not the refused metformin request
    assert runner.list_runs()[0] == {"run_id": "first", "status": "running", "drug": "montelukast",
                                     "sample_mode": runner.health()["current_sample_mode"]}
    release.set()
    for _ in range(50):
        if runner.status("first")[1]["status"] != "running":
            break
        threading.Event().wait(0.05)
    status, done = runner.status("first")
    assert status == 200 and done["status"] == "success" and not runner.health()["busy"]
    assert runner.health()["current_drug"] is None
    # A finished run is also found from its dossier after a restart.
    assert Runner(settings(tmp_path), slow).status("first")[1]["status"] == "success"
    assert Runner(settings(tmp_path), slow).status("nope")[0] == 404


def test_sample_mode_and_a_reused_run_id_are_refused_clearly(tmp_path):
    runner = Runner(settings(tmp_path, samples_dir=tmp_path / "no-samples"), fake_investigate)
    status, out = runner.run({"drug": "montelukast", "options": {"sample_mode": True}})
    assert status == 404 and out["error"]["type"] == "NoSampleRecording" and "can replay: none" in out["error"]["message"]
    assert runner.run({"run_id": "same", "input": {"drug": "montelukast"}})[0] == 200
    status, out = runner.run({"run_id": "same", "input": {"drug": "montelukast"}})
    assert status == 409 and out["error"]["type"] == "RunIdInUse"


def test_the_example_is_a_replay_made_once_outside_the_run_list(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "metformin.json.gz").write_bytes(b"")
    (samples / "montelukast.json.gz").write_bytes(b"")
    calls = []

    def replay(request, s, tracer):
        calls.append((request, s))
        return fake_investigate(request, s, tracer)

    logs = tmp_path / "logs"
    logs.mkdir()
    runner = Runner(settings(logs, samples_dir=samples), replay)
    status, out = runner.example()
    assert status == 200 and out["example"] is True and out["output"]["dossier"]["drug"] == "montelukast"
    request, s = calls[0]
    assert request == {"drug": "montelukast"} and s.sample_mode and s.logs_dir != logs
    assert s.world_path.parent == s.logs_dir and not s.logs_dir.exists()  # its own World Model, folder removed after
    assert out["log_file"] is None and out["output"]["artifacts"] == []
    assert runner.list_runs() == [] and not any(logs.iterdir())  # never in GET /runs, nothing left in logs/
    assert runner.example() == (200, out) and len(calls) == 1  # made once per process
    status, out = Runner(settings(logs, samples_dir=tmp_path / "none"), replay).example()
    assert status == 404 and out["error"]["type"] == "NoSampleRecording"


def test_each_item_links_to_its_reports_on_openfda(tmp_path):
    out = Runner(settings(tmp_path), fake_investigate).run({"drug": "montelukast"})[1]
    url = out["output"]["case_reports"]["SLEEP TERROR"]
    assert url.startswith("https://api.fda.gov/drug/event.json?search=") and url.endswith("&limit=10")
    assert "montelukast" in url and "SLEEP%20TERROR" in url and "+AND+" in url


def test_http_round_trip(tmp_path):
    from http.server import ThreadingHTTPServer
    runner = Runner(settings(tmp_path), fake_investigate)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(runner))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        assert call("/health")[1]["status"] == "ok"
        assert "token" not in json.dumps(call("/health")[1]).replace("token_set", "")  # no secrets
        status, out = call("/run", json.dumps({"drug": "montelukast"}).encode())
        assert status == 200 and out["output"]["drug"] == "montelukast"
        assert call(f"/runs/{out['run_id']}")[1]["status"] == "success"
        runs = call("/runs")[1]["runs"]
        assert runs[0]["run_id"] == out["run_id"] and runs[0]["drug"] == "montelukast" and runs[0]["review_next"] == 1
        status, ev = call(f"/runs/{out['run_id']}/events?after=0")
        assert status == 200 and ev["events"][0]["line"].startswith("Starting run for montelukast")
        assert call(f"/runs/{out['run_id']}/events?after={ev['last_seq']}")[1]["events"] == []
        assert call("/runs/nope/events")[0] == 404
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            assert r.headers["Content-Type"].startswith("text/html") and b"<title>Vigil" in r.read()
        with urllib.request.urlopen(base + "/fonts/publicsans.woff2", timeout=10) as r:
            assert r.headers["Content-Type"] == "font/woff2" and r.read(4) == b"wOF2"
        for bad in ("/fonts/nope.woff2", "/fonts/..%2Fserver.py", "/fonts/OFL-newsreader.txt"):
            assert call(bad)[0] == 404
        with urllib.request.urlopen(base + "/mascots/reviewer-squint.png", timeout=10) as r:
            assert r.headers["Content-Type"] == "image/png" and r.read(4) == b"\x89PNG"
        for bad in ("/mascots/nope-nope.png", "/mascots/..%2Fserver.py", "/mascots/reviewer-squint.svg"):
            assert call(bad)[0] == 404
        status, out = call("/run", b"{not json")
        assert status == 400 and out["error"]["type"] == "InvalidInput"
        assert call("/nowhere")[0] == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_container_reaches_host_services_and_env_file_values_are_cleaned(monkeypatch):
    monkeypatch.setattr(config, "in_container", lambda: True)
    assert config.host_url("http://localhost:8888/api/v1.0") == "http://host.docker.internal:8888/api/v1.0"
    assert config.host_url("http://127.0.0.1:8088/v1") == "http://host.docker.internal:8088/v1"
    assert config.host_url("http://zetaris.example.com:8888") == "http://zetaris.example.com:8888"
    assert config.host_url("http://localhost.example.com") == "http://localhost.example.com"
    monkeypatch.setenv("DOCKER_HOST_REWRITE", "false")
    assert config.host_url("http://localhost:8888") == "http://localhost:8888"
    monkeypatch.setattr(config, "in_container", lambda: False)
    monkeypatch.delenv("DOCKER_HOST_REWRITE")
    assert config.host_url("http://localhost:8888") == "http://localhost:8888"
    # docker run --env-file keeps comments and quotes as part of the value.
    assert config.env_value("http://127.0.0.1:8088/v1   # example only") == "http://127.0.0.1:8088/v1"
    assert config.env_value('"quoted"') == "quoted" and config.env_value("a#b") == "a#b"
    assert config.env_value(None) is None


def until_done(runner, run_id):
    for _ in range(500):
        status, out = runner.status(run_id)
        if out["status"] != "running":
            return status, out
        time.sleep(0.01)
    pytest.fail("the run did not end")


def endless(started):
    """A run that keeps working until it is stopped, and whose steps fall back on any Exception, as the agents do."""
    def run(request, s, tracer):
        tracer.event("orchestrator", "run_start", request=request, analyst_model="m", reviewer_model="m")
        started.set()
        for _ in range(1000):
            time.sleep(0.01)
            try:
                tracer.event("analyst", "routed", reaction="X", classification="on_label")
            except Exception:  # a degraded step; a stop must still get through
                pass
        (s.logs_dir / f"dossier-{tracer.run_id}.json").write_text("{}", encoding="utf-8")
        return dossier(tracer.run_id, request["drug"])
    return run


def test_a_stopped_run_ends_as_stopped_and_keeps_no_results(tmp_path):
    started = threading.Event()
    runner = Runner(settings(tmp_path), endless(started))
    assert runner.run({"run_id": "stop-1", "input": {"drug": "montelukast"}, "options": {"wait": False}})[0] == 202
    assert started.wait(5)
    status, out = runner.stop("stop-1")
    assert status == 202 and out["status"] == "stopping"
    status, out = until_done(runner, "stop-1")
    assert status == 409 and out["status"] == "error" and out["error"]["type"] == "Stopped"
    assert out["log_file"] == "logs/trace-stop-1.jsonl" and out["drug"] == "montelukast"
    assert not (tmp_path / "dossier-stop-1.json").exists()
    kinds = [json.loads(line)["event"] for line in (tmp_path / "trace-stop-1.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "stop_requested" in kinds and kinds[-1] == "run_stopped"
    # The slot is free again for the next run.
    assert runner.health()["busy"] is False and runner.current is None


def test_only_the_run_in_progress_can_be_stopped(tmp_path):
    runner = Runner(settings(tmp_path), fake_investigate)
    assert runner.stop("no-such-run")[1]["error"]["type"] == "NotRunning"
    assert runner.stop("../x")[0] == 400
    runner.run({"run_id": "done-1", "input": {"drug": "montelukast"}})
    assert runner.stop("done-1")[0] == 409


def test_a_stopped_run_sends_no_more_model_calls_or_queries(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.adapters import meterless, zetaris
    tracer = Tracer(tmp_path, echo=False)
    tracer.stop()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("a request went out after the stop"))
    llm = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", meterless_app="a", meterless_url="http://x",
                                                     model_stream=True, model_timeout=5), tracer)
    with pytest.raises(RunStopped):
        llm._post({"model": "m", "messages": []})
    db = zetaris.ZetarisClient(SimpleNamespace(zetaris_key="k", zetaris_org="o", zetaris_url="http://x"), tracer)
    with pytest.raises(RunStopped):
        db._post("SELECT 1", 5)
    with pytest.raises(RunStopped):
        tracer.event("analyst", "routed", reaction="X", classification="on_label")
