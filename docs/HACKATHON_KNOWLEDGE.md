# Hackathon knowledge base (as of Thu 22 Oct 2026)

Neutral facts about the event and the stack. The project chosen on 22 Oct is Black Box; see `docs/HANDOFF.md` and `docs/ideas/BLACK_BOX.md`. Each item is marked **confirmed** (seen in an organiser document or tested on this machine), **reported** (from a source we did not verify ourselves) or **unknown**. The live HackOS page and organiser announcements override everything here.

Sources: `docs/reference/03_LLM_context_for_your_AI.md`, the 21 Oct Participant Setup Guide PDF (30 pages; the 19 Oct guide in `docs/reference/` matches it closely), `cursor-sponsor-overview.md`, and the Zetaris getting-started catalog pages (REST, Parquet/CSV, USL).

## Event
- Open Agent Hackathon 2026, GenAI Works, platform HackOS (hackathon.genai.works). Online. Teams of 1 to 5.
- Build window opened Thu 22 Oct 00:00 UTC (11:00 Sydney). Submissions close Tue 27 Oct 23:45 UTC (Wed 28 Oct 10:45 Sydney). Hard deadline.
- Registration: the HackOS notice says it closes 22 Oct 23:59 UTC (Fri 23 Oct 10:59 Sydney). Plan for 10:45 Sydney.
- Our team is registered on HackOS (confirmed by the user, 22 Oct). **Track 02 chosen provisionally** for Black Box. We have **not seen the challenge statements** on HackOS; they override the generic track text.
- Help desk: the Help desk channel on HackOS (hackathon.genai.works/messages).

## Tracks and prizes (confirmed from the context pack)
| Track | Brief | Data that fits (organiser hint) | Cash 1st/2nd/3rd |
|---|---|---|---|
| 01 Solving Fragmented Intelligence | Discover and work across fragmented data sources | 3 or 4 small sources that disagree | $1,600 / $1,200 / $900 |
| 02 The Agent That Can Explain Why | Investigate across sources, connect findings, evidence-backed answers | Documents for one bounded question; every conclusion traceable | $1,600 / $1,200 / $900 |
| 03 Reasoning Architecture | Turn data, knowledge, memory and reasoning into reliable decisions | Records, rules or policies, memory of past decisions | $1,500 / $1,200 / $900 |
| Wildcard | Extend an existing project; only new work scored | Keep old and new work separate | $1,000 / $600 / $400 |

In-kind: NVIDIA DGX Spark for best use of Nemotron through Nightshift; SpaceX Cursor API credits for best Cursor-built product. We have no existing project, so Wildcard does not apply.

## Judging (100 points)
Impact 30, Technical 20, Innovation 15, Demo 15, Product/UX 10, Sponsor Tech 10 (covers Zetaris, Meterless, Cursor, NVIDIA).

## Deliverables
Demo video (1 to 4 min), slide deck, public GitHub repo with README, sponsor technology explanation. Cursor: say how the team used it in the **README and `metadata.json`** (new in the Cursor sponsor file; what `metadata.json` should contain is unknown, ask on HackOS). Cursor became optional on 23 Oct and the team does not use it, so the README says so plainly.

## Rules that can disqualify (confirmed)
- Zetaris and Meterless must be load-bearing. Zetaris and Meterless must run on our own machine.
- Build rule: at least one Meterless Engine in a working feature with a passing test. Power rule: Meterless Nightshift as the app's primary AI provider. A prompt file or unused dependency does not count.
- Minimum two genuinely interacting agents, with visible critique, retry or branching.
- No hardcoded outputs, no fabricated logs, no overclaiming. Logs in `logs/trace-<id>.jsonl`, never hand-edited.
- Data: public licensed data, small samples, login-free download scripts, public APIs, labelled synthetic data. No confidential or personal data. NVIDIA's endpoint logs requests.
- Judges must be able to run it: `run.py` and/or `POST /run`, `Dockerfile`, 3+ sample inputs, `SAMPLE_MODE` running real agent logic on cached data without keys.
- Secrets only in `.env`. Declare pre-22-Oct code in `docs/PREEXISTING.md`. The team must be able to explain its code.
- Three checks to apply to any idea: removal (would it work without Zetaris/Meterless?), collaboration (does one agent change another's work?), hardcoding (does a new input give a real answer?).

## How the stack fits together
- **Cursor (Build).** **Optional since 23 Oct** (organiser change, reported by the user); no Cursor credits are provided. The team does not use it (decided 23 Oct); development is done with Claude Code. Not part of the running product. Keep Nightshift token and NVIDIA key out of Cursor settings.
- **Zetaris (Data).** Runs locally in Docker. GUI http://localhost:3000, REST http://localhost:8888/api/v1.0 (org ID 1). App calls `POST /sql-editor/sqls/run` with bearer key, `X-Org-ID`, fresh UUID `X-Request-ID`. Sources become SQL tables (REST/JSON, files, databases).
- **Nightshift (Power).** Local gateway at http://127.0.0.1:8088/v1, OpenAI-compatible. App needs base URL, Runtime token and the `meterless-app` header (the guide's curl also sends `meterless-scope: user`). The NVIDIA key lives inside Nightshift only. `meterless/auto` may pick a non-NVIDIA model, so pin a Nemotron lane for award evidence.
- **Nemotron agents.** Roles in our own Python code calling a Nemotron model through Nightshift, with tools such as `run_sql`. Loop: user asks, model returns a tool call, code runs SQL on Zetaris, rows go back, repeat, answer.
- **Meterless Engines.** Building blocks in our code (memory, long tasks, shared state, intent routing), separate from Nightshift. Both rules must be met.

## Meterless Engines (confirmed from the repo clone and engines page)
- Repo: https://github.com/Meterless/Meterless, engines under `engines/`. Apache-2.0. Reference implementations are TypeScript.
- H-MEM: memory across sessions (working, episodic, semantic tiers), stored as files. Test: `HMEM_IMPL=... npx tsx conformance/runner.ts`.
- World Model: event-sourced shared state for parallel agents. Test: `WORLD_MODEL_IMPL=... npx tsx conformance/runner.ts`.
- Markovian: long tasks in bounded chunks with carryover. Test: `MARKOVIAN_IMPL=... npx tsx conformance/runner.ts`.
- Scout Intent: classifies requests, flags risk, routes tools, guards against prompt injection. Test: `npm run evals` in its folder.
- Prompt library: meterless.ai/engines.html (IDEATE, IMPLEMENT, COMBINE, HARDEN, POWER). The POWER "Add Meterless as a provider" prompt covers the provider contract (real bearer token, `meterless-app` header, model ids from `GET /v1/models`, 401/403 shown as unauthorized, 180 s timeout).
- No-key demo ran correctly here (cold run 12 chunks, warm run 8) using H-MEM plus Markovian with a **mock LLM**.
- **Unknown:** whether organisers accept a Python port of an engine with its own pytest. Our app is planned in Python. Options: port with ported tests, or a small TypeScript component. Ask on HackOS.
- Reported (one agent's reading of the specs, unverified): World Model's runner has 7 checks (stable IDs, merge bands, provenance required on writes, idempotent ingest, bitemporal supersession, strictly increasing audit sequence); a Python port of those parts is about a day of work.
- Untrusted clone location: `C:\Users\Ricky\untrusted\meterless\repo` (about 160 MB with dev dependencies). Not part of this repo.

## Nightshift models available (confirmed 22 Oct)
`GET /v1/models` lists `meterless/*` routing modes (auto, fast, deep, local, fusion, judge, embed and others) and NVIDIA models including `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3.5-super-vl-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/nemotron-3-nano-30b-a3b`, plus many `local-runtime/*` models. NVIDIA access is trial credits with a per-minute cap. Cap size is unknown.

## Nightshift behaviour seen while building Black Box (confirmed 22 Oct)
- A pinned model ID does not pin the model. Receipts in `%APPDATA%\ai.meterless.runtime\meterless.json` show `requested_mode: meterless/auto`, a learned-router race of width 2 (Super vs Lightning), with Lightning winning. The response's `model` field shows the model that actually served the call; the app logs it as `served_by`.
- The Super lane is broken for this account. Requests for Super above a few KB return 502 with an NVIDIA 404 "Function ... Not found for account". The same function ID fails for `nemotron-3.5-super-vl`. Small Super requests are answered by Lightning.
- Lightning hides its reasoning tokens and still counts them. Task prompts (classifying FAERS reactions against a label) often use up the whole budget and return 502 `empty_response`. Large ones hit `provider_deadline` after about 45 s. `max_tokens` is not enforced (one call returned 7,157 completion tokens with a 4,000 cap).
- None of these turned reasoning off: `chat_template_kwargs.enable_thinking=false`, `/no_think` in the system or user message, `reasoning_effort` low/none, `reasoning.enabled=false`, `thinking.type=disabled`, `meterless/fast`, streaming.
- Asking the model to copy exact label quotes made calls run much longer. Asking for a 1 to 4 word matching term, which code then finds in the label, cut a 5-reaction call to about 18 s.
- Nightshift adds its own steps to app requests (receipts in `meterless.json`, field `hmem` and `reasoning_scaffold`): its memory reinjects 2 to 3 earlier answers into each prompt ("comprehensive" strategy, similarity up to 0.88), and a reasoning scaffold switches on for prompts it rates as difficult. Both make prompts and outputs longer, and the memory mixes earlier answers (possibly the Hunter's) into later calls such as the Judge's. The Console's Apps tab sets a mode per app (auto, fast, deep, cheap, local, fusion). The Console's "daemon not running" and "proxy needs a health check" warnings (with a Linux `systemctl` hint) were wrong on 22 Oct: requests were served and receipts were signed by meterlessd.
- Reliability on 22 Oct between 00:55 and 02:00 UTC: 6 successful agent calls out of 39 attempts.
- **Fix found (22 Oct, about 04:30 UTC):** racing lanes was the main cause. With two lanes racing, a pinned model ID is not honoured, and an empty reply from one lane fails the whole request. Changing the Super lane's model to `nemotron-3-ultra-550b-a55b` (it works with this key), stopping the Lightning lane and setting race width to 1 in Preferences gave 12 successful calls out of 17 attempts, all served by Ultra, and a full montelukast run in 9 minutes. Restarting Nightshift re-seats lanes from the imported `lanes.toml` snapshot (`%LOCALAPPDATA%\ai.meterless.runtime\lanes.toml`), so check the lanes after a restart. Ultra returns its reasoning inline, ending in `</think>` with no opening tag. Simple small prompts kept working throughout (the smoke test passes).

## Zetaris facts
**Confirmed on this machine**
- All containers healthy. `verify.sh` shows 6/9; the bootstrap job and two login checks fail only because they still use the default admin password (changed 20 Oct). Expected, not a fault.
- GUI and REST work. The PokéAPI recipe works: `pikachu_abilities_table` returns 2 rows (`static` false, `lightning-rod` true). Its SQL is in the getting-started repo under `open_data/rest_apis/sql/non_rate_limited/02_pokeapi_create.sql`.
- Zetaris samples already loaded: `NY_TAXI`, `TPCDS_DB`.
- Run one SQL statement at a time in the editor.

**From the Zetaris catalog pages (organiser-side documentation, not re-tested by us)**
- REST tables: `CREATE LIGHTNING REST TABLE ... REQUEST(endpoint, method "get", response_type "json", http_encoding "URLENCODED") HEADER (...) BODY ()`, then a `CREATE SCHEMASTORE VIEW ... LATERAL VIEW explode(...)` to flatten nested arrays. `HEADER` is used for things like a `User-Agent` (the `company_dns` source needs one for its higher rate limit). Whether it can carry an API key is untested.
- Use `CACHE TABLE` after creating a table; uncached queries refetch the URL. Rate limits can return 429 on bursts even when the average is low.
- JSON shape matters: flat arrays are easy; dynamic-key objects were awkward.
- Verified REST sources are all non-health: SEC EDGAR, PokéAPI, Open Food Facts, NASA NeoWs, Eurostat, StatCan, ABS, `company_dns`. Known to fail: Singapore PM2.5, NASA DONKI (provider 503).
- Parquet/CSV (file) sources: only 2 of 7 verified (NOAA GHCN-Daily, AWS Public Blockchain). 5 known to fail (dotted bucket names rejected; some register but every query returns HTTP 500). Zetaris cannot read files on the laptop; needs storage such as S3. File sources are a risky route.
- USL (Unified Semantic Layer) models: lifecycle is namespace, compile, activate. Supports foreign keys and data-quality rules (`RUN DQ`, `SHOW DQ ALL INVALID`). In their example, the FK rule surfaced a company missing from a reference list that a plain `INNER JOIN` silently dropped. Limits: examples are tiny, materialization is deferred, custom checks cannot be registered as DQ rules, and the lifecycle was verified over JDBC (REST support unknown).
- `docs/plans/FUTURES.md` and its recipes in the getting-started repo cover other source types (Kafka, logs, JSON/REST, SQL databases, PDFs, government open data). **Not read yet.**

**Confirmed 22 Oct (openFDA spike, `scripts/zetaris/openfda_baseline.sql`)**
- `CREATE LIGHTNING REST TABLE`, `CREATE SCHEMASTORE VIEW` and `CACHE TABLE` all work at runtime through `POST /sql-editor/sqls/run`. `scripts/zetaris/run_sql.py` runs a whole .sql file this way. REST tables still have fixed URLs, but an app can create a new one per input.
- Query parameters with URL encoding (`%22`, `%20`) inside the `endpoint` string work.
- openFDA `drug/event` count endpoints work as REST tables. `LATERAL VIEW explode(results)` flattens them; the field named `count` needs backticks.
- `DESCRIBE BY` text in `CREATE LIGHTNING DATABASE` rejects parentheses. Allowed: letters, digits, spaces, `_ . - ,`.
- An "already exists" error comes back as an HTTP error from the REST API.

**Unknown (untested here)**
- REST tables have no query-time parameters, pagination or POST (one agent's reading of the docs).
- POST or GraphQL sources in Zetaris.
- How the guide's "Zetaris answers to judges" works for local instances (open question for organisers).

## Machine state
- Windows 11 Home, 15.8 GB RAM. **C: free about 4.2 GB** (after clearing the npm cache). Docker's disk file is about 22 GB and only grows. Docker reports about 5.5 GB of unused images (not hackathon-related: `bayesimpact/pandas-base`, `cancer-kg/cdot-alignment`, `cancer-kg/hgvs-inspection`, `biocommons/uta`, `staphb/bcftools` x2, `python:3.11.5-slim`). Nothing removed; they may belong to the user's other work. Deleting images does not shrink the file on C: until `scripts/compact-wsl-disks.ps1` runs in an administrator PowerShell with Docker quit.
- Avoid large downloads and big installs.
- 22 Oct: a Cursor install/update filled C: to 0 GB (cancelled; Cursor to be uninstalled, the teammate uses Cursor instead). Moved Nightshift's unused local Llama 1B/3B models (2.6 GB) to the Recycle Bin. Removed the five unused non-hackathon Docker images (biocommons/uta, staphb/bcftools ×2, python:3.11.5-slim-bookworm, bayesimpact/pandas-base; about 3.6 GB, all re-pullable from Docker Hub). Also cleared 1.16 GB of Docker build cache. That space only returns to C: after `scripts/compact-wsl-disks.ps1` runs with Docker quit (planned for the evening of 22 Oct).
- Docker Desktop needed the `run` folder rename again on 22 Oct (stale `userAnalyticsOtlpHttp.sock`). Services started with "lets begin": Docker engine 27.3.1, Zetaris up, Nightshift up, smoke test 3 PASS.

## Setup status (22 Oct)
Done: Docker/WSL, Zetaris install and API key, Zetaris GUI and PokéAPI recipe, Nightshift with NVIDIA key and Nemotron lanes, `.env` filled in, smoke test 3 PASS, team registered on HackOS.

Open:
- Track choice and reading the challenge statements on HackOS.
- Cursor: optional since 23 Oct; the team does not use it. Nothing to do.
- Meterless Engine feature with a passing test (needs a project idea). Nightshift as primary provider in the app (needs a project idea).
- Judge-facing files: public repo, Dockerfile, `run.py` or `POST /run`, `SAMPLE_MODE`, 3+ sample inputs, README, `metadata.json`, demo video, deck.
- Questions for organisers: Python port of an engine; what `metadata.json` needs; how judges reach a local Zetaris.

See `docs/SETUP_CHECKLIST.md` for the full checklist.
