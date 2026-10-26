"""Offline tests for the HTTP entry point (POST /run, GET /runs/<run_id>, GET /health) and the Docker address
handling. The pipeline is replaced by a stand-in, so no Zetaris or Nightshift is needed.
Run: python -I -m pytest tests"""
import json
import sys
import threading
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


def settings(tmp_path, **kw):
    return replace(config.get_settings(), logs_dir=tmp_path, decisions_dir=tmp_path / "decisions", sample_mode=False,
                   **kw)


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
    release.set()
    for _ in range(50):
        if runner.status("first")[1]["status"] != "running":
            break
        threading.Event().wait(0.05)
    status, done = runner.status("first")
    assert status == 200 and done["status"] == "success" and not runner.health()["busy"]
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


def test_decisions_are_appended_with_what_vigil_said_and_the_latest_wins(tmp_path):
    runner = Runner(settings(tmp_path), fake_investigate)
    runner.run({"run_id": "done", "input": {"drug": "montelukast"}})
    status, out = runner.decide("done", {"reaction": "SLEEP TERROR", "decision": "escalate",
                                         "note": "  Check the Canadian cluster first. ", "by": "Sally"})
    assert status == 201 and out["decision"]["note"] == "Check the Canadian cluster first."
    assert out["decision"]["vigil"]["review_priority"] == "review_next" and out["decision"]["decided_at"].endswith("Z")
    runner.decide("done", {"reaction": "SLEEP TERROR", "decision": "agree", "note": "Cluster checked: 40 cases."})
    latest = runner.decisions("done")[1]["decisions"]
    assert latest["SLEEP TERROR"]["decision"] == "agree" and latest["SLEEP TERROR"]["times_decided"] == 2
    assert latest["SLEEP TERROR"]["by"] is None
    assert len((tmp_path / "decisions" / "done.jsonl").read_text(encoding="utf-8").splitlines()) == 2  # audit trail
    for body, code in [({"reaction": "SLEEP TERROR", "decision": "maybe", "note": "x"}, 400),
                       ({"reaction": "SLEEP TERROR", "decision": "agree", "note": "   "}, 400),
                       ({"reaction": "SLEEP TERROR", "decision": "agree"}, 400),
                       ({"reaction": "NOT IN RUN", "decision": "agree", "note": "x"}, 404),
                       ([], 400)]:
        assert runner.decide("done", body)[0] == code
    assert runner.decide("never-ran", {"reaction": "X", "decision": "agree", "note": "x"})[0] == 404
    assert runner.decisions("never-ran")[0] == 404 and runner.decisions("../x")[0] == 400


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
        status, saved = call(f"/runs/{out['run_id']}/decisions",
                             json.dumps({"reaction": "SLEEP TERROR", "decision": "dismiss", "note": "Known."}).encode())
        assert status == 201 and saved["decision"]["decision"] == "dismiss"
        assert call(f"/runs/{out['run_id']}/decisions")[1]["decisions"]["SLEEP TERROR"]["note"] == "Known."
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            assert r.headers["Content-Type"].startswith("text/html") and b"<title>Vigil" in r.read()
        with urllib.request.urlopen(base + "/fonts/publicsans.woff2", timeout=10) as r:
            assert r.headers["Content-Type"] == "font/woff2" and r.read(4) == b"wOF2"
        for bad in ("/fonts/nope.woff2", "/fonts/..%2Fserver.py", "/fonts/OFL-newsreader.txt"):
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
