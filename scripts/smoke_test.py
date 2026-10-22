"""Connectivity check for the three layers. Prints PASS/FAIL, never prints secrets.
Run: python -I scripts/smoke_test.py   (reads .env in the project root)
This only proves connections work. It is not evidence of a working agent."""
import json, os, sys, uuid, urllib.request, urllib.error
from pathlib import Path

env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

def post(url, body, headers, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())

def need(*names):
    missing = [n for n in names if not os.environ.get(n) or "your-" in os.environ[n] or "exact-model" in os.environ[n]]
    if missing:
        raise RuntimeError("missing or placeholder: " + ", ".join(missing))

def zetaris_gui():
    with urllib.request.urlopen("http://localhost:3000", timeout=10) as r:
        assert r.status == 200

def zetaris_rest():
    need("ZETARIS_REST_URL", "ZETARIS_API_KEY", "ZETARIS_ORG_ID")
    s, j = post(os.environ["ZETARIS_REST_URL"] + "/sql-editor/sqls/run",
                {"queryId": str(uuid.uuid4()), "sql": "SELECT 1 AS one", "source": "SqlEditor", "limit": 1},
                {"Authorization": "Bearer " + os.environ["ZETARIS_API_KEY"], "X-Org-ID": os.environ["ZETARIS_ORG_ID"], "X-Request-ID": str(uuid.uuid4())})
    assert j.get("data"), "no rows returned"

def model():
    need("MODEL_BASE_URL", "MODEL_API_KEY", "NEMOTRON_MODEL")
    s, j = post(os.environ["MODEL_BASE_URL"].rstrip("/") + "/chat/completions",
                {"model": os.environ["NEMOTRON_MODEL"], "messages": [{"role": "user", "content": "Reply with the word ok."}], "max_tokens": 16},
                {"Authorization": "Bearer " + os.environ["MODEL_API_KEY"]}, timeout=60)
    assert j["choices"][0]["message"], "empty reply"

failed = 0
for name, fn in [("Zetaris GUI :3000", zetaris_gui), ("Zetaris REST SELECT 1", zetaris_rest), ("Nemotron reply", model)]:
    try:
        fn(); print("PASS", name)
    except Exception as e:
        failed += 1; print("FAIL", name, "-", type(e).__name__, str(e)[:150])
sys.exit(1 if failed else 0)
