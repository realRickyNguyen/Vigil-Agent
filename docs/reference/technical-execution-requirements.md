# Technical Execution Guide

**OPEN AGENT HACKATHON 2026 | Build an agent that does real work**

This guide covers how to make your submission runnable, reproducible and judgeable. Judges have limited time per project. Anything they cannot start, call or read counts against you.

> **The official requirements are in the Official Rules on the event page.** Where this guide and the Official Rules disagree, the Official Rules apply. Everything below is recommended practice, not a rule, unless the Rules say otherwise. For installing the sponsor tools, follow the Participant Setup Guide in the Resource Center on HackOS.

---

## 1. The Standard Every Submission Should Meet

| Area | Recommended standard |
|---|---|
| **Startup** | Runs from a clean checkout with a documented command, no manual fixing |
| **Interface** | Exposes a programmatic entry point, not only a user interface |
| **Reproducibility** | Docker or a documented environment setup that installs everything at build time |
| **Hardware** | Your app runs on a standard machine; model calls go through Meterless Nightshift to hosted NVIDIA endpoints, so no local GPU is needed |
| **Runtime** | A single run completes in minutes, not hours, with internal timeouts |
| **Secrets** | Loaded from environment variables only, never committed |
| **Data** | Zetaris as the data layer; small samples in the repository, scripts or APIs for anything larger |
| **Logs** | Printed to stdout and saved to `logs/`, showing how the agent worked |
| **Examples** | At least three sample inputs and their outputs |
| **Sponsor technology** | Zetaris as the data layer, at least one Meterless Engine in a working feature, Meterless Nightshift as the primary AI provider, NVIDIA wherever it contributes |

---

## 2. Give Judges a Programmatic Entry Point

A user interface is fine and Product & UX is worth 10 points, but a judge should also be able to run your agent without clicking through a screen.

The simplest pattern that works:

```text
/project-root/run.py     # starts the app, or runs the agent on one input
```

If you expose an HTTP API, bind to all interfaces so it is reachable from outside a container:

```python
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
```

Avoid binding only to `127.0.0.1` inside Docker; the port mapping will not reach it.

A run endpoint that takes JSON and returns JSON makes your project easy to test:

```json
{
  "run_id": "demo-001",
  "input": {
    "query": "Reconcile supplier records across the three sources and flag conflicts."
  },
  "options": {
    "sample_mode": false
  }
}
```

And returns something a reader can inspect:

```json
{
  "run_id": "demo-001",
  "status": "success",
  "output": {
    "summary": "Generated result here",
    "recommendations": [],
    "artifacts": []
  },
  "agents": [
    { "name": "Planner", "role": "Breaks down the task and delegates work" },
    { "name": "Evaluator", "role": "Reviews outputs and requests refinement" }
  ],
  "trace_id": "trace-demo-001",
  "log_file": "logs/trace-demo-001.jsonl",
  "execution_time_seconds": 42.7
}
```

On failure, return a structured error rather than crashing silently:

```json
{
  "run_id": "demo-001",
  "status": "error",
  "error": {
    "type": "UpstreamTimeout",
    "message": "Zetaris did not respond after 3 retries; fell back to sample mode.",
    "recoverable": true
  },
  "trace_id": "trace-demo-001",
  "execution_time_seconds": 61.3
}
```

If your project includes a UI, run it on a separate port from the API so neither blocks the other.

---

## 3. Docker

Docker is the most reliable way to make sure your project runs the same way on a judge's machine as on yours.

Your image should:

- Build with a standard `docker build` command
- Install all dependencies at **build time**
- Start without manual shell steps
- Run without a local GPU
- Take secrets as runtime environment variables, never at build time

### Reference Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "run.py"]
```

### Running it

```bash
docker build -t oah-submission .

docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  oah-submission
```

Any dependency manager is fine (`pip`, `poetry`, `uv`, `conda`) as long as nothing installs during a run. No `pip install`, `apt-get` or model download inside the request path.

### Reaching Zetaris and Nightshift from a container

Zetaris and Meterless Nightshift run on your machine, outside your app's container. Inside a container, `localhost` and `127.0.0.1` mean the container itself, not your machine. On Docker Desktop, use `host.docker.internal` in your container's settings instead:

```bash
ZETARIS_REST_URL=http://host.docker.internal:8888/api/v1.0
METERLESS_BASE_URL=http://host.docker.internal:8088/v1
```

If you run your app directly on your machine without Docker, keep the `localhost` and `127.0.0.1` addresses from the setup guide.

---

## 4. Hardware

Assume a judge has an ordinary machine.

Your app should not need a local GPU, CUDA drivers or local model weights that require an accelerator. Connect NVIDIA models through Meterless Nightshift using NVIDIA's hosted endpoints, as covered in the setup guide and the POWER workshop, so your project runs without NVIDIA hardware.

Zetaris itself needs 8 GB of memory and 4 CPUs given to Docker, plus at least 15 GB of free disk space, which in practice means a laptop with 16 GB of RAM or more. If yours can't manage it, the setup guide explains how to run Zetaris on AWS instead.

Because a judge may not have Zetaris or Nightshift running, your sample mode matters (see section 5).

---

## 5. Keep Runs Bounded

A run that takes an hour is hard to judge and hard to demo.

| Operation | Suggested timeout |
|---|---:|
| Zetaris SQL request | 30–60 seconds |
| Model request through Nightshift | 30–90 seconds |
| One agent loop iteration | 1–3 minutes |
| A full run | Target 5–10 minutes |

Also:

- Cap agent loop iterations; unbounded debate is the most common cause of a hung run
- Do not download large datasets during a run
- Ship a `SAMPLE_MODE=true` path that works without Zetaris, Nightshift or any network access
- Return a controlled error or partial result instead of hanging

---

## 6. Secrets

All credentials come from environment variables.

Never put keys in source code, `README.md`, notebooks, config files committed to the repo, logs, or screenshots in your demo video or slide deck.

Your app needs only its Zetaris and Meterless Nightshift settings. The NVIDIA API key goes in Nightshift's Providers tab, not in your app.

Ship a `.env.example` with placeholders only:

```bash
# Zetaris (data layer)
ZETARIS_REST_URL=http://localhost:8888/api/v1.0
ZETARIS_ORG_ID=1
ZETARIS_API_KEY=your-zetaris-api-key

# Meterless Nightshift (primary AI provider), from Nightshift's Console
METERLESS_BASE_URL=http://127.0.0.1:8088/v1
METERLESS_RUNTIME_TOKEN=your-nightshift-runtime-token
METERLESS_MODEL=meterless/auto

# Runtime behaviour
SAMPLE_MODE=false
LOG_LEVEL=INFO
PORT=8000
```

Read them at runtime. Nightshift accepts OpenAI-format requests, so an OpenAI-compatible client works:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["METERLESS_RUNTIME_TOKEN"],
    base_url=os.environ["METERLESS_BASE_URL"],
    default_headers={
        "meterless-app": "my-hackathon-app",
        "meterless-scope": "user",
    },
)
```

For the full provider integration, use the **POWER → Add Meterless as a provider** prompt at meterless.ai/engines.html.

Add `.env` to `.gitignore`. If a real key ever reached a commit, rotate it rather than trying to scrub history.

---

## 7. Data

Keep the repository light. A judge cloning a multi-gigabyte repo is a judge who stops.

Zetaris is your data layer: register your sources in Zetaris and have your agent query them through its REST API. The setup guide shows how to register a web API as a table and run your first query.

| Pattern | Use when | Requirements |
|---|---|---|
| **Source registered in Zetaris** | Your main data | Documented in the README: what each source is and how to register it |
| **Static sample in repo** | Small curated data, and sample mode | Documented source and licence in the README |
| **Automated download script** | Larger open datasets | Fully automated, no login, no manual clicks |
| **Runtime public API** | Fresh or live data | Timeouts, retries, and a sample-mode fallback |

Zetaris can't read a file sitting on your laptop. Put files in storage Zetaris can reach, such as an S3 bucket, before registering them.

Avoid: large raw datasets, private or proprietary data, anything requiring manual download or approval, and real personal, clinical or financial records.

Document every source in your README: where it came from, the licence, what subset you used, and how to regenerate it. If you prepared data before the build window opened, declare it as a pre-existing component in the submission form.

---

## 8. Logs

Logs are how a judge verifies that your agent did what you say it did. This matters directly for the Technical and Demo scores.

Write to both **stdout** and a `logs/` directory.

### What logs should show

- Which agents ran, and what each was asked to do
- Handoffs and delegation decisions
- Critique or validation steps
- Refinement loops
- Retries, fallbacks and recovery
- Zetaris queries and what they returned
- Which Meterless Engine ran, and what it did
- Requests through Nightshift, including which model handled each one
- The final synthesis
- Errors, with what happened next

If you're competing for the NVIDIA award, log the model name for each request. `meterless/auto` can route to a non-NVIDIA model, so your logs should show where a Nemotron model handled the work.

### Recommended trace format

One JSONL file per run, `logs/trace-<run_id>.jsonl`, one JSON object per line:

```json
{
  "timestamp": "2026-10-24T18:42:11Z",
  "run_id": "demo-001",
  "agent_name": "Planner",
  "action": "delegate_task",
  "input_summary": "User asked for a reconciliation across three supplier sources.",
  "output_summary": "Created three sub-questions and assigned retrieval to Researcher.",
  "target_agent": "Researcher",
  "model": "nvidia/nemotron-3-super-120b-a12b",
  "confidence": 0.91,
  "retry_count": 0,
  "status": "success"
}
```

### Readable stdout

```text
[INFO] run_id=demo-001 Starting run
[INFO] run_id=demo-001 Planner delegated retrieval to Researcher
[INFO] run_id=demo-001 Researcher queried Zetaris and returned 5 candidate records
[INFO] run_id=demo-001 H-MEM recalled 2 facts from an earlier session
[INFO] run_id=demo-001 Evaluator flagged a conflict between sources 2 and 3
[INFO] run_id=demo-001 Planner requested a second pass on source 3
[INFO] run_id=demo-001 Writer produced final reconciliation (model: Nemotron via Nightshift)
[INFO] run_id=demo-001 Completed in 42.7 seconds
```

### Never log secrets

Mask them:

```text
METERLESS_RUNTIME_TOKEN=...redacted
```

---

## 9. Sponsor Technology

Sponsor Tech is worth 10 points, so document where each sponsor technology fits in your build rather than leaving a judge to guess. Your submission includes a sponsor technology explanation covering exactly this.

| Sponsor | Requirement | Workshop recording | Help |
|---|---|---|---|
| **Zetaris** | Required: your agent's data layer, running locally in Docker | DATA with Zetaris | Help Zetaris channel |
| **Meterless** | Required: at least one Meterless Engine (H-MEM, Markovian, World Model or Scout Intent) working in a feature, and Meterless Nightshift as your primary AI provider | BUILD with Meterless and Cursor; POWER | Help Meterless channel |
| **Cursor (with Space XAI)** | Optional: recommended AI coding tool. Any coding tool works | BUILD with Meterless and Cursor | Help Cursor channel |
| **NVIDIA** | Wherever it contributes. Connect Nemotron models through Nightshift; the best use of Nemotron wins an NVIDIA DGX Spark | POWER | Help NVIDIA channel |

Workshop recordings and the Participant Setup Guide are in the Resource Center on HackOS. For general technical questions, use the #help desk channel on HackOS.

Keep each sponsor integration behind an adapter so a service outage does not take your whole project down during judging, and so a judge without your setup can still run sample mode.

For your Meterless Engine, keep the test or conformance check that shows it works, and point to it in your README.

---

## 10. Suggested Repository Structure

```text
/project-root
│── app/                 # Core agent logic
│── app/adapters/        # Zetaris and Meterless Nightshift integrations
│── app/engines/         # Your Meterless Engine integration(s)
│── data/                # Small static data or download scripts
│── scripts/             # Helper scripts
│── tests/               # Including your Meterless Engine test
│── run.py               # Entry point
│── requirements.txt     # Dependencies
│── Dockerfile           # Reproducible build
│── input_examples/      # At least 3 sample inputs
│── output_examples/     # Matching outputs
│── logs/                # Agent traces
│── .env.example         # No real keys
│── README.md            # Setup, usage, dependencies, architecture, limitations
```

If your agents run in Google Colab, include the Colab links in your README.

---

## 11. Test It Like a Judge Would

Before you submit, do this on a clean machine or a fresh clone, with Zetaris and Nightshift running:

```bash
git clone <your-repo-url>
cd <your-repo>

cp .env.example .env     # fill in your Zetaris and Nightshift settings

docker build -t oah-submission .
docker run --rm -p 8000:8000 --env-file .env oah-submission
```

Then call it:

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d @input_examples/example_1.json
```

And read the logs:

```bash
docker logs <container_id>
cat logs/trace-*.jsonl
```

Then run it again with `SAMPLE_MODE=true` and Zetaris and Nightshift stopped, to check a judge without your setup can still see it work.

If any step needs a fix you make by hand, your README is incomplete.

---

## 12. Common Failures

| Failure | What it looks like | Fix |
|---|---|---|
| **UI only** | A dashboard runs, but nothing can be called programmatically | Add an entry point that takes input and returns output |
| **Runtime installs** | `os.system("pip install ...")` inside a request | Install at build time |
| **Hardcoded secrets** | A real key in the source | Environment variables and `.env.example` |
| **NVIDIA key in the app** | The NVIDIA key sits in `.env` or the code | Put it in Nightshift's Providers tab; the app only needs the Nightshift URL and token |
| **Container can't reach Zetaris or Nightshift** | Connection refused on `localhost` from inside Docker | Use `host.docker.internal` |
| **No trace** | Logs say "Final answer generated." | Log each agent, handoff, critique and retry |
| **Unbounded run** | Downloads 4GB during a run and hangs | Small samples, timeouts, sample mode |
| **Localhost binding** | API unreachable from outside the container | Bind to `0.0.0.0` |
| **Works on my machine** | Undocumented setup steps | Test from a fresh clone |
| **Silent crash** | Process dies with no output | Return a structured error |
| **Meterless Engine not really used** | An engine is mentioned or installed but no feature uses it | Wire it into a user-facing feature and keep the passing test |
| **Sponsor tech bolted on** | Zetaris or Meterless added at the end with no real role | Design them into the architecture from day one |
| **Private repository** | Judges cannot open the GitHub link | Make the repository public before you submit |

---

## 13. Readiness Checklist

### Running

- [ ] A documented command starts the project from a clean clone
- [ ] There is a programmatic entry point, not only a UI
- [ ] Input and output are structured and machine-readable
- [ ] Nothing requires interactive input

### Build

- [ ] Docker build succeeds, or setup is fully documented
- [ ] Dependencies install at build time
- [ ] Runs without a local GPU
- [ ] No runtime installs or model downloads

### Secrets

- [ ] No keys in code, logs, examples, the demo video or the slide deck
- [ ] The NVIDIA key is in Nightshift, not in the app
- [ ] `.env.example` present with placeholders
- [ ] `.env` is gitignored

### Data

- [ ] Zetaris is the data layer, with sources documented
- [ ] Repository is small
- [ ] Sources and licences documented
- [ ] No manual data setup
- [ ] Sample mode works without Zetaris, Nightshift or network access

### Runtime

- [ ] A run finishes in minutes
- [ ] External calls have timeouts
- [ ] Agent loops are bounded
- [ ] Failures return a controlled response

### Logs

- [ ] Written to stdout and `logs/`
- [ ] Show agent handoffs, critique, retries and recovery
- [ ] Show Zetaris queries, Meterless Engine activity and which model handled each request
- [ ] Contain no secrets

### Submission

- [ ] GitHub repository is public, with a README covering setup, usage and dependencies
- [ ] At least three sample inputs and outputs
- [ ] Zetaris integrated as the data layer
- [ ] At least one Meterless Engine working in a feature, with a passing test
- [ ] Meterless Nightshift is the primary AI provider
- [ ] Sponsor technology explanation covers Zetaris, Meterless and NVIDIA
- [ ] Demo video (1–4 minutes) recorded and uploaded
- [ ] Slide deck complete
- [ ] Pre-existing components declared in the submission form
- [ ] Submitted on HackOS before 27 October, 23:45 UTC

---

## 14. The Standard in One Line Each

**Runnable** — starts cleanly from a documented command.
**Reachable** — can be driven programmatically, not only through a screen.
**Reproducible** — no manual setup, no hidden dependencies.
**Portable** — no local GPU requirement.
**Bounded** — finishes in minutes, with timeouts and caps.
**Secure** — secrets only through environment variables, the NVIDIA key only in Nightshift.
**Data-conscious** — Zetaris as the data layer, light repository, documented sources.
**Observable** — logs to stdout and `logs/`.
**Integrated** — Zetaris, a Meterless Engine and Nightshift have a real role in the build.
**Agentic** — the traces show the agent doing real work.