"""Run every statement in a .sql file against Zetaris through the REST API, in order.
Stops at the first error, except "already exists", which is reported as SKIP so re-runs work.
Never prints secrets. Reads .env in the project root.

Run:  python -I scripts/zetaris/run_sql.py scripts/zetaris/openfda_baseline.sql --stop-before "Part B"

A statement that holds ';' itself, such as a multi-table COMPILE USL, goes between the comment lines
"-- begin one statement" and "-- end one statement" and is sent whole.
"""
import argparse, json, os, sys, uuid, urllib.request, urllib.error
from pathlib import Path

env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

def statements(text, stop_before=None, start_at=None):
    """Split on ';', ignoring '--' comment lines, except inside a begin/end one statement block.
    Assumes no ';' inside strings."""
    lines = text.splitlines()

    def heading(l, mark):  # a comment line that starts with mark, so a mention inside a sentence does not count
        return l.startswith("--") and l.lstrip("- ").startswith(mark)

    if start_at:
        lines = lines[next((i for i, l in enumerate(lines) if heading(l, start_at)), len(lines)):]
    if stop_before:
        lines = lines[:next((i for i, l in enumerate(lines) if heading(l, stop_before)), len(lines))]
    out, chunk, whole = [], [], None
    for l in lines:
        mark = l.strip().lower()
        if mark == "-- begin one statement":
            whole = []
        elif mark == "-- end one statement":
            out.append("\n".join(whole).strip().rstrip(";").strip())
            whole = None
        elif mark.startswith("--"):
            continue
        elif whole is not None:
            whole.append(l)
        else:
            chunk.append(l)
            if l.rstrip().endswith(";"):
                out += [s.strip() for s in "\n".join(chunk).split(";") if s.strip()]
                chunk = []
    out += [s.strip() for s in "\n".join(chunk).split(";") if s.strip()]
    return [s for s in out if s]

def run(sql, timeout):
    url = os.environ["ZETARIS_REST_URL"] + "/sql-editor/sqls/run"
    body = {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": 1000}
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + os.environ["ZETARIS_API_KEY"],
               "X-Org-ID": os.environ["ZETARIS_ORG_ID"],
               "X-Request-ID": str(uuid.uuid4())}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sql_file")
    ap.add_argument("--stop-before", help="stop at the first comment line that starts with this text")
    ap.add_argument("--start-at", help="start at the first comment line that starts with this text")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--show", type=int, default=1500, help="characters of each result to print")
    args = ap.parse_args()

    stmts = statements(Path(args.sql_file).read_text(encoding="utf-8"), args.stop_before, args.start_at)
    for n, sql in enumerate(stmts, 1):
        label = f"[{n}/{len(stmts)}] {sql.splitlines()[0][:90]}"
        try:
            j = run(sql, args.timeout)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:600]
            if "already exist" in msg.lower():
                print("SKIP", label, "- already exists"); continue
            print("FAIL", label, f"- HTTP {e.code}: {msg}"); sys.exit(1)
        except Exception as e:
            print("FAIL", label, "-", type(e).__name__, str(e)[:300]); sys.exit(1)
        print("OK  ", label)
        if sql.upper().startswith(("SELECT", "RUN DQ", "SHOW", "LIST")):
            print("     ", json.dumps(j.get("data", j), default=str)[:args.show])
    print(f"Done: {len(stmts)} statements.")

if __name__ == "__main__":
    main()
