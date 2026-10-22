# **Open Agent Hackathon 2026: Participant Setup Guide**

*Last updated 19 October 2026*

## **Welcome**

Welcome to Open Agent Hackathon 2026\! Every project stands on three layers: the **Data** your agent works with, the tools you **Build** it with, and the model that **Powers** it. This guide sets up all three before kickoff, so the event itself goes on ideas and building. Zetaris and meterless must be running on your machine for eligibility for this hackathon.

By the end of this guide you will have:

> * [**Data**](#Data): Zetaris running on your machine, serving the internal data your agent works with  
> * [**Build**](#Build): Cursor installed (with Grok and Composer models ready on your Cursor credit) and 1 or more Meterless Engines integrated (Markovian Thinking, H-Mem, World State), plus you have experimented with the Meterless.ai prompt library  
> * [**Power**](#Power): Meterless AI hotspot configured with NVIDIA integrated as a model provider

Set aside an afternoon, ideally a few days before the event. Start the Zetaris install first: it downloads large container images, and you can set up Build and Power while it runs.

Work through the guide in order. Each part ends with a **You're done when** you check, so you always know whether to move on. If a term is new to you, look it up in the Glossary at the end.

### **Where to get help**

> * **Hackathon help channel:** the Help desk channel on HackOS, https\://hackathon.genai.works/messages  
> * **Event details:** the [Open Agent Hackathon 2026 event page](https://hackathon.genai.works/event/open-agent-hackathon-2026) for rules, tracks and submission  
> * **Zetaris:** the [getting-started repository](https://github.com/zetaris/getting-started), especially its [troubleshooting guide](https://github.com/zetaris/getting-started/blob/main/docs/guides/troubleshooting.md) and [installation guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md), plus the [Zetaris knowledge base](https://kbase.zetaris.com/knowledge)  
> * **Cursor:** [Cursor docs](https://cursor.com/docs)  
> * **Meterless:** [meterless.ai](https://meterless.ai) and the [Meterless GitHub](https://github.com/Meterless/Meterless)  
> * **Nemotron:** [build.nvidia.com](https://build.nvidia.com) for NVIDIA's free API, and NVIDIA's [Nemotron developer page](https://developer.nvidia.com/nemotron)

When you ask for help, include your operating system, the exact command you ran, the full error message and the last step that worked. Remove passwords, API keys and tokens before you share anything.

The framework at a glance

Every project stacks three layers. **Data** is what your agent knows, **Build** is where you make it, and **Power** is the model that runs it

*Data, Build, Power · required and optional tools per layer*

Read it left to right: data feeds the app you build in Cursor, and the finished app runs on Nemotron, reached through Meterless or NVIDIA's free API. The bottom row is the one rule to remember: Cursor credit pays while you code, and your Nemotron route is used only when your product runs.

## **Before you start**

Do the slow item today: register at Zetaris Cloud and download the Zetaris platform bundle and registry sign-in command from its Run locally page (see Data 1.1), then start the install. The first download and startup take 30 to 45 minutes. Everything else on this list takes minutes.

| Layer | What | Why you need it | Where to get it |
| :---- | :---- | :---- | :---- |
| Data | Zetaris platform bundle and registry credentials | Everything Docker needs to install Zetaris | [From zetaris download page](https://cloud.enterprise.zetaris.com/register) |
| Data | Docker Desktop, version 25 or later recommended | Runs Zetaris on your machine | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Data | Git | Downloads Zetaris's getting-started recipes | [git-scm.com/downloads](https://git-scm.com/downloads) |
| Data | WSL 2 (Windows only) | Zetaris's setup commands run in a Linux terminal | Built into Windows, see Data 1.2 |
| Build | Cursor | Where you build, with Grok and Composer included | [cursor.com](https://cursor.com) |
| Power | Meterless account (Option A) or a free NVIDIA account (Option B) | Your route to Nemotron, the model that runs your product | See the Power section |
| All | Python 3 | Runs the smoke test and Zetaris's helper scripts | [python.org/downloads](https://www.python.org/downloads/) |

**Hardware.** Zetaris needs 8 GB of memory and 4 CPUs given to Docker, plus at least 15 GB of free disk space. In practice that means a laptop with 16 GB of RAM or more. Apple Silicon Macs work, with a slower first start. If your laptop can't manage it, you can run Zetaris in your own AWS account instead, following Zetaris's Managed AWS cluster guide: https\://zetaris.github.io/getting-started/docs/install/managed-aws-cluster-guide.html (AWS bills you for it directly).

**Keep your keys private.** You will collect three secrets: Zetaris password, a Zetaris API key, and a Meterless API key. Cursor needs no key of your own. Store the secrets in a file called .env in your project folder and list .env in your .gitignore file, so they never end up on GitHub. Names that start with a dot are hidden: on a Mac, press Cmd+Shift+. in Finder to show them. The Zetaris platform has its own separate .env file inside its install folder; keep that one private too.

## **Sources**

> 1. Zetaris: [getting-started README](https://github.com/zetaris/getting-started/blob/main/README.md), [Start here](https://github.com/zetaris/getting-started/blob/main/START-HERE.md), [installation guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md), [connection options](https://github.com/zetaris/getting-started/blob/main/docs/connections/README.md), [Cursor connection guide](https://github.com/zetaris/getting-started/blob/main/docs/connections/cursor-connection.md), [your first dataset](https://github.com/zetaris/getting-started/blob/main/docs/guides/first-dataset.md), [troubleshooting](https://github.com/zetaris/getting-started/blob/main/docs/guides/troubleshooting.md), [project paths and event tracks](https://github.com/zetaris/getting-started/blob/main/docs/guides/project-paths.md), [client scripts](https://github.com/zetaris/getting-started/blob/main/scripts/HOWTO.md), [Zetaris overview](https://kbase.zetaris.com/knowledge/zetaris-overview), [GenAI, RAG and the semantic layer](https://kbase.zetaris.com/knowledge/rag-semantic-layer)  
> 2. Cursor: [Cursor Learn](https://cursor.com/learn), [Grok in Cursor](https://cursor.com/help/models-and-usage/grok-4-6)  
> 3. Meterless: [Meterless GitHub](https://github.com/Meterless/Meterless), [Swarms README](https://github.com/Meterless/Swarms)  
> 4. NVIDIA Nemotron: [Nemotron developer page](https://developer.nvidia.com/nemotron), [build.nvidia.com](https://build.nvidia.com), [n8n's NVIDIA credential guide](https://docs.n8n.io/integrations/builtin/credentials/nvidia/) (base URL and key steps), [nemotron-ai.com](https://nemotron-ai.com) (an independent site, not run by NVIDIA)

## **Data: Zetaris for internal data**

**The Data rule:** your project must use Zetaris, which serves the internal data an organisation runs on and is the center of every build.

Zetaris is our headline sponsor. Start its install first, because the download and first startup take 30 to 45 minutes. These steps follow Zetaris's official [getting-started repository](https://github.com/zetaris/getting-started), which also holds ready-made data recipes and a guide to connecting Cursor. Please also use this guide for better tool using [https\://zetaris.github.io/getting-started/](https://zetaris.github.io/getting-started/)

### **Why Zetaris belongs at the center**

A model only knows what it was trained on. What an agent lacks is the data a real organisation runs on, and that is the gap Zetaris fills.

> * **One access point to many sources.** Zetaris connects to databases, files such as CSV and Parquet, and web APIs, then lets you query all of them with SQL from one place.  
> * **No pipeline per source.** Your agent asks Zetaris, and Zetaris reaches the underlying systems, so you don't write and maintain a connector for each one.  
> * **A semantic layer for grounding.** Zetaris's Unified Semantic Layer builds one consistent business view across several sources. Zetaris positions it as the foundation for grounding AI answers in real data (retrieval augmented generation, or RAG).  
> * **Made for this event's tracks.** Two of the tracks, Solving Fragmented Intelligence and The Agent That Can Explain Why, ask for agents that work across scattered sources and back their answers with evidence. That is exactly what Zetaris was built for.

### **1.1 Get the Zetaris platform files**

For this hackathon, everyone runs Zetaris locally in Docker. You need two things from Zetaris Cloud: the platform bundle, zetaris-platform.zip, and registry credentials so Docker can download the Zetaris images.

**How to get them: register at https\://cloud.enterprise.zetaris.com/register, then open the** 

**Run locally page at https\://cloud.enterprise.zetaris.com/dashboard/download to download zetaris-platform.zip and copy the registry sign-in command. Zetaris's full instructions: [https\://github.com/zetaris/getting-started/blob/main/README.md](https://github.com/zetaris/getting-started/blob/main/README.md)**

### **1.2 Prepare Docker**

| Requirement | What you need |
| :---- | :---- |
| Docker | Docker Desktop on macOS or Windows, or Docker Engine with the Compose plugin on Linux; version 25 or later recommended |
| Memory | 8 GB given to Docker (the preflight check fails below 6 GB) |
| CPU | 4 CPUs given to Docker |
| Disk | At least 15 GB free, plus room for data |

What counts is how much memory Docker Desktop is allowed to use, set in its settings, not your laptop's total RAM.

> * **Apple Silicon Macs:** the Zetaris images are built for Intel and AMD chips, so turn on **Use Rosetta** in Docker Desktop's settings, and expect a slower first start.  
> * **Windows:** run every command below from a WSL terminal (such as Ubuntu) with Docker Desktop's WSL integration turned on. If you don't have WSL yet, run wsl \--install in PowerShell.

Check Docker is ready:  
docker version  
docker compose version

### **1.3 Unpack, sign in to the registry and run preflight**

unzip zetaris-platform.zip  
cd zetaris-platform  
docker login zetarishackathon.azurecr.io  
./preflight.sh

When docker login asks, enter the registry credentials from the Run locally page. If that page shows a different sign-in command, use it instead. preflight.sh checks Docker, memory, disk and your registry sign-in: fix every failed check before you continue. Run all remaining Zetaris commands from this zetaris-platform folder.

### **1.4 Set your administrator account before the first start**

Open the .env file inside zetaris-platform in a text editor (Cursor works well). Keep every supplied value, and set these three:

| Setting | What to put |
| :---- | :---- |
| ZETARIS\_ADMIN\_EMAIL | The email you'll sign in with |
| ZETARIS\_ADMIN\_PASSWORD | A strong password: at least eight characters, with a lowercase letter, an uppercase letter, a digit and one of \$ @ \! % \* ? & (other punctuation is rejected) |
| ZETARIS\_ADMIN\_ORG | Your organisation name, such as your team name |

Then confirm these laptop settings, which Zetaris tested for a local install:

| Setting | Value |
| :---- | :---- |
| ZSPARK\_DRIVER\_MEM | 2g |
| ZSPARK\_DRIVER\_CORES | 2 |
| ZSPARK\_MASTER\_URL | local\[2\] |
| ZETARIS\_API\_MAX\_HEAP | 1g |
| UI\_PORT | 3000 |
| ALLOWED\_ORIGINS and GUI\_URL | http\://localhost:3000 |
| COMPOSE\_PROFILES | Empty |
| ZETARIS\_SEED\_TPCH | true (keeps the bundled sample data) |

Set these before the first start: changing them afterwards doesn't reset an account that already exists. Then lock the file and check it:  
chmod 600 .env  
docker compose config \--quiet  
The first command keeps .env private, and the second checks it's valid without printing your secrets. This .env belongs to the Zetaris platform: never commit it or copy it into your project.

### **1.5 Download and start Zetaris**

docker compose pull  
docker compose up \-d  
docker compose ps \--all  
Expect about 4 GB of downloads (5 to 15 minutes), then 5 to 10 minutes of first-time setup, which carries on after up \-d returns. Allow 30 to 45 minutes in total, longer on slow Wi-Fi or an Apple Silicon Mac.

When it's ready, docker compose ps \--all shows:

> 1. postgres, driver, api, ui and ai-datasteward running  
> 2. init and bootstrap showing Exited (0). These are one-time setup jobs, and exit code 0 means they succeeded.

To watch progress, run docker compose logs \--tail=80 driver api bootstrap.

### **1.6 Verify the install**

./verify.sh  
All nine checks should pass, including sign-in and a query through the web interface, the API and the query engine. If checks fail while setup is still running, wait a minute and run it again.

### **1.7 Sign in and run your first query**

> 2. Open [http\://localhost:3000](http://localhost:3000) and sign in with the administrator email and password you set in 1.4. If you kept a supplied password, change it straight away from the user menu.  
> 3. Open the **SQL Editor** and run:

SELECT 1 AS one;  
Expect one row containing 1. That confirms your login reaches the query engine.

### **1.8 Load your first dataset**

Zetaris can turn a web API into a table you query with SQL. The starter recipe does this with PokéAPI, a free API that needs no key.

> 3. Download the getting-started repository, which holds this recipe and many more:

git clone https\://github.com/zetaris/getting-started.git

> 1. Open open\_data/rest\_apis/sql/non\_rate\_limited/02\_pokeapi\_create.sql.  
> 2. In the SQL Editor, run these four statements from it, one complete statement at a time, waiting for each to finish:  
   1. CREATE LIGHTNING DATABASE POKEAPI\_REST ...  
   2. CREATE SCHEMASTORE CONTAINER pokeapi;  
   3. CREATE LIGHTNING REST TABLE pikachu\_facts ...  
   4. CREATE SCHEMASTORE VIEW pikachu\_abilities\_table ...  
> 3. Query the result:

SELECT pokemon\_name, ability\_name, is\_hidden  
FROM pokeapi.pikachu\_abilities\_table;  
Expect two rows: static (not hidden) and lightning-rod (hidden). The source can change, so if you see something different, look at pikachu\_facts. Leave the rest of the file (types, stats and Charizard) for later.

For more data, see the repo's [recipe readiness guide](https://github.com/zetaris/getting-started/blob/main/docs/guides/recipe-readiness.md). Skip the PUDL recipe: Zetaris lists it as known to fail.

### **1.9 Connect Cursor and your app to Zetaris**

| Route | Address on a local install | Use it for |
| :---- | :---- | :---- |
| Web interface and SQL Editor | http\://localhost:3000 | Exploring data, registering sources, testing SQL |
| REST API | http\://localhost:8888/api/v1.0 | Your agent sending SQL and reading results as JSON |
| JDBC | jdbc:zetaris:lightning@localhost:10000 | Tools that use a JDBC driver; needs Java 11 or later and the Zetaris driver file from the platform download |

REST is the simplest route for an agent because it needs no Java. To set it up:

> 1. In the Zetaris web interface, create an API key for your user and copy it straight away (it may be shown only once). Create the key yourself; don't ask an AI agent to create or fetch it.  
> 2. Add these settings to your project's .env file. In the getting-started repo, the same settings go in a file called .env.local.

ZETARIS\_REST\_URL=http\://localhost:8888/api/v1.0  
ZETARIS\_ORG\_ID=1  
ZETARIS\_API\_KEY=your-zetaris-api-key  
ZETARIS\_USERNAME=your-sign-in-email  
ZETARIS\_PASSWORD=your-password

1 is the organisation ID on a local install. The username and password are only needed to download the API's specification.

Every REST request sends your key as a bearer token, plus two headers: X-Org-ID (your organisation ID) and X-Request-ID (a fresh random ID in UUID format). To run SQL, your app sends a POST request to /sql-editor/sqls/run; the smoke test in "Verify your setup" shows a working example. Your own install serves the full API reference at [http\://localhost:8888/redoc/index.html](http://localhost:8888/redoc/index.html). Don't use port 8889: it's internal to Zetaris.

**Let Cursor do the wiring.** The getting-started repo includes an AGENTS.md file that teaches Cursor's agent the rules for working with Zetaris, such as using Zetaris's Lightning SQL, sending one statement at a time and never printing credentials. Open the repo folder in Cursor, put your settings in .env.local, and send this as your first message, replacing the goal with your own:  
Read AGENTS.md and follow it. Run python3 scripts/preflight.py and show me the  
result. Then connect over REST to the instance configured in .env.local and  
confirm with SELECT 1 and SHOW LIGHTNING DATABASES.

Goal: \<for example: onboard pokeapi\>

Dry-run before creating anything and wait for my go-ahead.  
The repo's [Cursor connection guide](https://github.com/zetaris/getting-started/blob/main/docs/connections/cursor-connection.md) covers JDBC and more goal ideas.

### **Stop and restart Zetaris**

docker compose stop \# stop, keeping your data  
docker compose start \# resume  
docker compose down \-v deletes everything, including your data and encryption keys, so use it only to start over.  
**You're done when** ./verify.sh passes, SELECT 1 AS one works in the SQL Editor, the Pikachu query returns two rows, and your Zetaris API key is saved in .env.

# **Build: Cursor, Meterless Engines, and the Workshop**

**The Build rule:** You must use **Cursor** among the platform to build your application (**required**) and implement **at least one Meterless Engine** in a working feature of your product (**required**). Use the prompts at [meterless.ai/engines.html](https://www.meterless.ai/engines.html) to find ideas faster, implement the engine in your code, and test that it works. You can also find meterless prompts and access to engines in HackOS resources tab.

In practice: code with Cursor's own models, and only call the AI provider when your product actually runs. Keep your Meterless Runtime token and NVIDIA key out of Cursor's model-provider settings. The **NVIDIA API key goes in Nightshift's Providers tab**. The **Nightshift Runtime URL and API key come from its top-right Console** and go into your application's Meterless provider settings, as explained in Power.

### **3.1 Set up Cursor**

1. Download Cursor from [cursor.com](https://cursor.com), install it, and sign in.  
2. **Claim your Cursor credit:** \[Organisers: add how participants redeem their Cursor credit\]  
3. Create an empty project folder, for example `open-agent-hack`, and open it in Cursor.  
4. Open the Agent chat and pick a model from the model menu. Cursor recommends Composer for everyday coding where speed matters, and Grok for harder, longer-running work. Both draw on your Cursor credit, where available on your plan.  
5. Ask the Agent to create and run a Python file that prints `hello`. This confirms it can edit files and use your terminal.  
6. If AI coding is new to you, work through the short [Cursor Learn](https://cursor.com/learn) lessons on tool calling and working with agents.

### **3.2 Build with Meterless Engines and the prompt library (required)**

Meterless Engines are open-source building blocks that add memory, long-task reasoning, shared world state, and intent routing to your applications. The Engines page provides ready-made prompts that tell your coding agent where to find the specifications, examples, and validation tools. You can combine multiple engines as your project grows.

| Meterless Engine | What it can add to your app | Example you can demonstrate |
| ----- | ----- | ----- |
| **H-MEM** | Persistent memory and retrieval | Your agent remembers information from an earlier session and uses it on a later task. |
| **Markovian** | Long-running tasks handled in bounded steps | Your app completes a multi-step job while keeping the context passed between steps controlled. |
| **World Model** | Shared state for agents, entities, and events | Two agents read and update a common project state without losing one another's changes. |
| **Scout Intent** | Understanding requests, routing actions, and checking risks | Your app recognizes different requests and sends them to the correct tool or workflow. |

**A working integration is required.** Simply mentioning an engine in your submission, copying a prompt, or adding an unused dependency does not satisfy the Build rule.

## **The one rule to remember: building versus running**

Your project uses AI in two different ways, and each has its own setup.

|  | AI that helps you build | AI that powers your product |
| ----- | ----- | ----- |
| **What it does** | Writes, fixes, and explains your code | Answers questions and makes decisions inside your app |
| **Models** | Cursor's available coding models, including Composer or Grok where offered | NVIDIA Nemotron and other models through Meterless Nightshift (see Power) |
| **Paid from** | Your Cursor credit; no separate provider API key needed for Cursor's included models | Your local hardware or the cloud provider credentials configured in Nightshift, subject to provider limits |
| **Used when** | Any time you're coding | When you run, power, or test your product |

The [Meterless Engines prompt library](https://www.meterless.ai/engines.html) gives you ready-made instructions for choosing, implementing, combining, and testing Meterless Engines in your application. **You do not need to write the engine integration from scratch.** Your Cursor Agent can read the open-source Meterless repo and work through the relevant implementation prompt.

**Step 1\. Find a strong use case.**

1. Open [meterless.ai/engines.html](https://www.meterless.ai/engines.html).  
2. If you already have a project idea, start with **IDEATE → Map it onto my product**. If you're still deciding, choose **IDEATE → Find my best use case** or the **The one prompt** starter at the top of the page.  
3. Click **Copy**, paste the prompt into Cursor's Agent chat, and describe what you want to build.  
4. Let the Agent recommend which Meterless Engine belongs in your product and how it improves the experience for your users.

**Step 2\. Implement at least one engine.**

1. On the same page, choose **IMPLEMENT**.  
2. Select the prompt that fits your project:  
   * **Give my agent memory** for **H-MEM**.  
   * **Long tasks, flat context** for **Markovian**.  
   * **Keep parallel agents in sync** for **World Model**.  
   * **Route tools by intent** for **Scout Intent**.  
3. Click **Copy** and paste the implementation prompt into Cursor's Agent chat with your project open.  
4. Ask Cursor to **implement the engine in your actual application**, connect it to a user-facing workflow, and run the tests or conformance checks described in the prompt. Review the changes and fix any failures.  
5. If you're starting from nothing, **IMPLEMENT → Scaffold a working agent** is another useful starting point. Keep its engine wiring intact as you adapt it.

**Step 3\. Improve and verify the result.**

1. Use **COMBINE** prompts if you want multiple engines working together, such as H-MEM memory carried into a Markovian long-running task.  
2. Use **HARDEN** prompts to add tests, guardrails, concurrency handling, or privacy checks.  
3. Run your application and show an actual feature powered by the engine. For example, demonstrate that an H-MEM agent remembers a fact across sessions or that Scout Intent routes two different requests to different tools.  
4. Keep a clear record of which engine you used, where it appears in your code, and the test or live demonstration showing it works.

**Important:** The **POWER → Add Meterless as a provider** prompt is used in the separate Power section to connect your product to Nightshift. It does **not**, by itself, fulfill the Build requirement to implement at least one Meterless Engine.

### **3.3 Join the vibe coding workshop**

Vibe coding means building software by describing what you want to an AI agent, then reviewing and steering what it produces. Our hands-on workshop uses Cursor and the Meterless Engines prompt library to build a small agent from scratch, and it's the quickest way to learn the workflow before the clock starts.

**Workshop details: \[Organisers: add the date, time and joining link\]**

Come with your Data, Build, and Power layers set up, so you can follow along on your own machine. If you're new to the engines, bring one use case you want to implement and use the workshop to get your first working feature running.

### **Verify your Build setup**

You're done when:

* Cursor is installed and signed in, your credit is active, and the Agent has created and run a file using Composer or Grok (or another available Cursor coding model).  
* You've used [meterless.ai/engines.html](https://www.meterless.ai/engines.html) to choose an engine and implementation path.  
* **At least one Meterless Engine is actually integrated into your application's working code.**  
* You can demonstrate the feature that uses that engine, not just describe it.  
* The engine's relevant conformance suite, evaluation, or a reproducible feature test passes, and you can show the evidence.

**For your submission:** Name the engine(s), explain what each one does in your project, and show the working feature and test result. The separate **Power** requirement covers connecting your application to Meterless Nightshift and, for the NVIDIA prize, using a Nemotron model through Nightshift.

**Quick links**

* [Meterless Engines and ready-made prompts](https://www.meterless.ai/engines.html)  
* [Meterless open-source repository](https://github.com/Meterless/Meterless)  
* [Cursor download](https://cursor.com)  
* [Cursor Learn](https://cursor.com/learn)

# **Power: Use Meterless Nightshift as your AI Hotspot**

## **The Power rule**

**Your application must support Meterless Nightshift as a primary AI provider.** Build your product in the language and framework you prefer, then connect its AI features to Meterless Runtime. Your application sends requests to Nightshift, and Nightshift serves those requests using the local or cloud models you configure.

The easiest way to meet this rule is to use the ready-made **POWER → Add Meterless as a provider** prompt at [meterless.ai/engines.html](https://www.meterless.ai/engines.html). You do not need to build the provider integration from scratch.

**NVIDIA Nemotron Award: Win a DGX Spark.** To compete for the NVIDIA award, test powering with at least one **NVIDIA Nemotron model through Meterless Nightshift** in a working feature of your application. Judging focuses on **technical depth, usefulness, and polish**. Show what Nemotron actually does inside the product, rather than simply listing it as an available model.

## **1\. Add Meterless to your application using the Power Prompt**

1. Open [**meterless.ai/engines.html**](https://www.meterless.ai/engines.html).  
2. Select the **POWER** category and find **“Add Meterless as a provider.”**  
3. Click **Copy** and paste the prompt into your coding assistant, such as Cursor, Claude Code, Copilot, or another agent that can edit your project.  
4. Open your application's codebase in that assistant. Ask it to implement the prompt, making **Meterless Runtime a first-class, selectable provider** and the primary provider for your demo.  
5. Have the assistant expose settings for **Meterless base URL**, **Meterless Runtime token**, and **Meterless routing mode**. Keep any existing providers available if you want.  
6. Have the assistant run the prompt's connection, authorization, model-discovery, and text-request checks.

The official Power Prompt specifies the OpenAI-compatible API, authentication, model discovery, and error states. **Use the prompt from the live Engines page as the implementation contract.** The separate NVIDIA API key will be configured inside Nightshift, not hard-coded into your application.

## **2\. Download and install Nightshift**

**What is Nightshift?** Nightshift is the Meterless AI Hotspot for your computer. It can serve AI requests from your apps, manage local models and connected cloud providers, and run multiple model lanes for longer work. For this challenge, it is the AI backend your product calls.

1. Visit [**meterless.ai**](http://meterless.ai) and scroll to the bottom to see the cards to install any version.  
2. Choose the **Nightshift edition for your machine** (Windows, Mac, or DGX).  
   1. Mac M1+ \= Older Macs Big Sur M1 to M4  
   2. Mac M5+ \= Tahoe M5-M6  
3. Enter your email address at the access gate, then open the confirmation email and complete verification.  
4. Return to the site or follow the verified download link. Download the correct edition, install it, and launch Nightshift.  
5. Complete any first-run prompts and leave Nightshift running while testing your application.

**Important:** Use the installed Nightshift edition with its Runtime/API hotspot for this challenge. The free browser experience is useful for exploring Nightshift, but do not assume a browser demo exposes the local Runtime your app needs.

## **3\. Add NVIDIA in Nightshift's Providers tab**

NVIDIA provides hosted model endpoints through [build.nvidia.com/models](https://build.nvidia.com/models). Some are marked as **Free Endpoint** for development and prototyping, subject to NVIDIA's access limits and terms.

1. Open [**build.nvidia.com/models**](https://build.nvidia.com/models), sign in, and select a **Nemotron** model that offers an API endpoint.  
2. Generate or copy your **NVIDIA API key**.  
3. In **Meterless Nightshift**, open the **Setup** tab and in the sub menu look for the **Providers** tab. You will see a Cloud Providers for Get Getting API keys and entering in the list below.  
4. Select **NVIDIA** from the list of provider options.  
5. Paste your **NVIDIA API key** into the NVIDIA provider credential field and save it.  
6. Confirm NVIDIA is connected. This **unlocks NVIDIA's available models in Nightshift's model catalog**, including the supported Nemotron models, so you can assign them to your lanes. Refresh the model list if necessary.

**Important:** The NVIDIA key goes in **Providers**, not in the Console and not in your application's `.env` file. Keep it private.

## **4\. Configure your first model lanes**

After connecting NVIDIA in the **Providers** tab, Click the **NIGHT** tab iun the top center left in the main aop menu and open Nightshift's model and lane configuration in the left sidebar menu in the middle far left of the screen called **LANES**. You should be able to add any model using the Add button for each lane you want to use. You can also load in fleets by choosing in the Fleets subtab.  Assign the models you want your application to use. Start with a small setup you can test.

| Lane | Suggested model | Job |
| ----- | ----- | ----- |
| **Lane 1: Fast worker** | `nvidia/nemotron-3.5-lightning-30b-a3b` | Quick responses, tool use, and first attempts |
| **Lane 2: Deep worker** | `nvidia/nemotron-3-super-120b-a12b` | More complex reasoning, planning, or second opinions |
| **Optional judge/verification lane** | A suitable available Nemotron or another supported model | Check outputs against your application's requirements |

These are **examples, not guaranteed account entitlements**. Select the exact Nemotron names exposed in your current NVIDIA catalog and Nightshift model picker. You can start with just **Lane 1**. If you also want local models, use Nightshift's model download and lane assignment flow, but a local download is **not required** to use NVIDIA-hosted endpoints.

Make sure at least one active lane actually uses Nemotron. Run a short test inside Nightshift and confirm the response and selected provider/model. For the NVIDIA award, demonstrate a task where Nemotron materially powers the result.

## **5\. Open the Nightshift Console and connect your application**

The **Console**, accessible from the **top-right corner of Nightshift**, is where you obtain the **Meterless Runtime URL and API key** that your application needs. These are **Nightshift connection credentials**, separate from the NVIDIA API key you entered in **Providers**.

1. In Nightshift, click **Console** at the **top right**.  
2. Find the **Runtime/API connection details** displayed in the Console.  
3. Copy your **Nightshift URL (base URL)** and **Nightshift API key (Runtime access token)**.  
4. Return to the application where you implemented **Meterless as a provider** using the Engines Power Prompt.  
5. Paste the **Nightshift URL** and **Nightshift API key** into your application's Meterless provider settings, or place them in private local environment variables.  
6. Select the Meterless routing mode or model exposed by Nightshift. Test the connection.

For example, if the Console displays the default local Runtime address, the application's private `.env` values might look like this:

```
METERLESS_BASE_URL=http://127.0.0.1:8088/v1
METERLESS_RUNTIME_TOKEN=<your-real-nightshift-runtime-token>
METERLESS_MODEL=meterless/auto
```

* **Copy the URL shown in the Console.** `http://127.0.0.1:8088/v1` is only an example for apps running on the **same computer**. If the Console shows a different URL, use it. For an app running on another device, `127.0.0.1` would refer to that device, so use the reachable, securely configured Nightshift URL.  
* **Copy the API key shown in the Console.** Use that real value as the application's **Meterless Runtime access token**. Do not substitute the NVIDIA provider key or a placeholder token.  
* `meterless/auto` is a **Meterless routing mode**, not a specific NVIDIA model ID. The concrete NVIDIA model is selected through your Nightshift provider and lane configuration. Use Runtime model discovery if you want to pin an available `meterless/*` route.  
* **Keep the NVIDIA API key in Nightshift's Providers tab.** Your application only needs its Meterless connection URL and Nightshift API key. Nightshift handles the NVIDIA call.

Your coding assistant should implement the official Runtime contract from the Engines Power Prompt, including `Authorization: Bearer <token>`, the `meterless-app` header, `meterless-scope: user` for chat, `GET /v1/models` for discovery, and OpenAI-compatible `POST /v1/chat/completions`. Do not mistake a working `/healthz` response for proof that a real model is connected.

## **6\. Verify your setup**

With Nightshift running and your token set, use your app's **Test Connection** action or send a simple request using the actual Runtime base URL and token:

```
curl -sS http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $METERLESS_RUNTIME_TOKEN" \
  -H "Content-Type: application/json" \
  -H "meterless-app: hackathon-demo" \
  -H "meterless-scope: user" \
  -d '{
    "model": "meterless/auto",
    "messages": [{"role": "user", "content": "Reply with one sentence confirming this connection works."}]
  }'
```

In the command above, \$METERLESS\_RUNTIME\_TOKEN must be available as a **shell environment variable** (a `.env` file does not automatically export it). You can instead use the application's own connection-test feature.

Then test the **actual application feature** end to end:

**Your app → Meterless Runtime → active NVIDIA Nemotron lane → result shown in your app.**

Inspect Nightshift's run details, logs, or available receipts to confirm **which underlying model handled the request**. `meterless/auto` may route to a non-NVIDIA model if multiple models are eligible; select/pin a Nemotron-backed lane or demonstrate an explicit Nemotron task to make your award evidence unambiguous.

**You're done when:**

* Meterless is a working primary AI provider in your application, not just a dependency listed in your README.  
* Nightshift is installed, running, and reachable from the app.  
* Your real Meterless Runtime token authenticates successfully.  
* NVIDIA credentials are saved in Nightshift's **Providers** tab and Nemotron models are unlocked.  
* The **Console** supplies the Nightshift URL and API key used by the application.  
* A Nemotron lane responds to a real request.  
* A feature in your app produces an actual answer through Meterless.  
* For the NVIDIA award, the underlying run visibly uses a **Nemotron** model.

## **7\. What to show judges**

In a short demo, show: **(1)** the finished application solving a useful problem, **(2)** its Meterless provider connection, **(3)** one real request passing through Nightshift and returning a result. You can show where the application connects to the Console-provided Runtime URL, but **hide all keys and tokens**.

**NVIDIA Nemotron Award: DGX Spark**  
**Suggested judging criteria:** technical depth, usefulness, and polish. Strong projects make meaningful use of Nemotron, demonstrate the working Meterless integration, and deliver a useful end-user experience. You qualify by having Meterless integrated as a Ai runtime provider in your agent or application.

**Key links:** [Meterless Engines and Power Prompt](https://www.meterless.ai/engines.html) · [Nightshift downloads](https://www.meterless.ai/) · [NVIDIA model catalog and API keys](https://build.nvidia.com/models)

## **Putting Data, Build and Power together**

The app you build in Cursor is a simple loop: Nemotron decides what to do, your code fetches the data it asks for from Zetaris, the result goes back to Nemotron, and the loop repeats until it can answer. Setting up this skeleton before the event means your team can start the event straight on ideas. Check the event rules on how much project code you may prepare in advance.

### **How one request moves through the layers**

> 1. A user asks your app a question.  
> 2. **Power:** your app sends the question to Nemotron, through Meterless or NVIDIA's free API, along with short descriptions of the tools your app offers, such as run\_sql.  
> 3. **Power:** Nemotron replies with a tool call, for example run\_sql with a SQL query.  
> 4. **Data:** your code runs that call against Zetaris, and sends the result back to Nemotron.  
> 5. Steps 3 and 4 repeat as needed, then Nemotron writes the final answer.

**Build** is where all of this code gets written, with Cursor's models doing the heavy lifting on your Cursor credit.

### **A starter project layout**

open-agent-hack/  
├── .env \# ZETARIS\_REST\_URL, ZETARIS\_ORG\_ID, ZETARIS\_API\_KEY,  
│ \# MODEL\_BASE\_URL, MODEL\_API\_KEY, NEMOTRON\_MODEL  
├── .gitignore \# lists .env  
├── prompts/ \# optional: Meterless prompt library files  
├── smoke\_test.py \# the check in "Verify your setup"  
└── agent/  
    ├── llm.py \# Power: Nemotron, via Meterless or NVIDIA  
    ├── tools\_zetaris.py \# Data: run\_sql() sends SQL to Zetaris, returns rows  
    └── main.py \# the agent loop  
This layout assumes Python, which has the widest support across all the services. JavaScript or TypeScript works just as well. Zetaris's getting-started repo has ready-made Python and TypeScript helpers in its scripts/ folder that you can learn from or reuse.  
To scaffold it, give Cursor's Agent a prompt like this (attach a Meterless prompt file with @ if you're using the library):  
Create a Python agent in the agent/ folder. In llm.py, use the openai package with  
base URL MODEL\_BASE\_URL, key MODEL\_API\_KEY and model NEMOTRON\_MODEL, all read  
from .env. Give the agent one tool, run\_sql, which sends one SQL statement to  
Zetaris with a POST to ZETARIS\_REST\_URL \+ /sql-editor/sqls/run, using  
ZETARIS\_API\_KEY as a bearer token plus X-Org-ID and a fresh UUID X-Request-ID  
header, and returns the rows. Keep all secrets in .env and explain each file.

### **Two patterns that put Zetaris at the center**

> * **Ground every answer in Zetaris.** Your agent queries Zetaris first for the facts, and uses web data only to add context. Judges and users can trust answers that trace back to governed data, which is what The Agent That Can Explain Why track asks for.  
> * **Bring outside data into Zetaris.** Zetaris can register a web API as a table, the way the PokéAPI starter does, so a public JSON API your idea relies on can sit alongside your business data in a single SQL query. For data you've saved as a file, put the file in storage Zetaris can reach (such as an S3 bucket) before registering it: Zetaris can't read a file sitting on your laptop.

**You're done when** your project folder exists, your .env holds all your secrets and settings, and .gitignore keeps them out of version control.

## **Verify your setup**

Run these three checks at least two days before kickoff, so there's time to fix anything that fails. When all three pass, every layer is ready.

### **Check 1 (Data): Zetaris is running and answers queries**

From the zetaris-platform folder, run:  
./verify.sh  
Then, in the SQL Editor at [http\://localhost:3000](http://localhost:3000), run SELECT 1 AS one; and the Pikachu query from Data 1.8.  
**Pass:** all nine verify.sh checks pass, SELECT 1 returns one row, and the Pikachu query returns two rows.

### **Check 2 (Build): Cursor builds on its own models**

In the Agent chat, select Composer or Grok and ask it to create and run a Python file that prints "hello".  
**Pass:** the file appears in your project and "hello" prints in the terminal, without you entering any API key.

### **Check 3 (Data and Power): the all-in-one smoke test**

This script sends a real query to Zetaris through its REST API and a real prompt to Nemotron through your chosen route. Save it as smoke\_test.py in your project folder. Your .env file should contain:  
ZETARIS\_REST\_URL=http\://localhost:8888/api/v1.0  
ZETARIS\_ORG\_ID=1  
ZETARIS\_API\_KEY=your-zetaris-api-key  
MODEL\_BASE\_URL=provider-address-for-your-route  
MODEL\_API\_KEY=your-meterless-or-nvapi-key  
NEMOTRON\_MODEL=the-nemotron-model-id-for-your-route  
\# smoke\_test.py: checks your Data and Power layers  
\# Install once: pip install openai python-dotenv requests  
import os  
import uuid

import requests  
from dotenv import load\_dotenv  
from openai import OpenAI

load\_dotenv()  
results \= \[\]

def check(name, fn):  
    try:  
        fn()  
        results.append(("PASS", name, ""))  
    except Exception as error:  
        results.append(("FAIL", name, str(error)\[:150\]))

def need(\*names):  
    for name in names:  
        assert os.environ.get(name), f"{name} is missing from .env"

def zetaris\_web():  
    url \= os.environ.get("ZETARIS\_BASE\_URL", "http\://localhost:3000")  
    requests.get(url, timeout=10).raise\_for\_status()

def zetaris\_sql():  
    need("ZETARIS\_REST\_URL", "ZETARIS\_ORG\_ID", "ZETARIS\_API\_KEY")  
    response \= requests.post(  
        os.environ\["ZETARIS\_REST\_URL"\].rstrip("/") \+ "/sql-editor/sqls/run",  
        headers={  
            "Authorization": "Bearer " \+ os.environ\["ZETARIS\_API\_KEY"\],  
            "X-Org-ID": os.environ\["ZETARIS\_ORG\_ID"\],  
            "X-Request-ID": str(uuid.uuid4()),  
        },  
        json={"queryId": str(uuid.uuid4()), "sql": "SELECT 1", "source": "SqlEditor", "limit": 1},  
        timeout=60,  
    )  
    response.raise\_for\_status()  
    data \= response.json().get("data")  
    assert data and str(data\[0\]\[0\]) \== "1", "unexpected reply: " \+ response.text\[:80\]

def nemotron():  
    need("MODEL\_BASE\_URL", "MODEL\_API\_KEY", "NEMOTRON\_MODEL")  
    client \= OpenAI(  
        base\_url=os.environ\["MODEL\_BASE\_URL"\],  
        api\_key=os.environ\["MODEL\_API\_KEY"\],  
    )  
    reply \= client.chat.completions.create(  
        model=os.environ\["NEMOTRON\_MODEL"\],  
        messages=\[{"role": "user", "content": "Reply with the single word: ready"}\],  
    )  
    assert reply.choices, "no reply from the model"

check("Data: Zetaris web interface", zetaris\_web)  
check("Data: Zetaris runs SQL over its REST API", zetaris\_sql)  
check("Power: Nemotron replies", nemotron)

for status, name, detail in results:  
    print(f"{status} {name} {detail}")  
Run it with python smoke\_test.py (or python3 on macOS and Linux) while Zetaris is running.  
**Pass:** all three lines say PASS. Each FAIL line includes the error, and the Troubleshooting section below covers the common ones.

### **Ready for kickoff**

> 1. ☐ **Data:** Zetaris Cloud account created and zetaris-platform.zip downloaded  
> 2. ☐ **Data:** ./verify.sh passes and the Pikachu query returns two rows  
> 3. ☐ **Data:** Zetaris API key created and saved in .env  
> 4. ☐ **Build:** Cursor installed, credit active, and check 2 passes  
> 5. ☐ **Build:** Meterless prompt library downloaded (optional) and a workshop seat booked  
> 6. ☐ **Power:** Nemotron route chosen, with its provider address, key and model ID saved in .env, all from the same route  
> 7. ☐ **All:** .env listed in .gitignore, and smoke\_test.py shows three PASS lines

## **Troubleshooting and help**

Most setup problems fall into a handful of patterns. Find your symptom below; if it isn't listed, ask for help early rather than on the morning of the event.

| Layer | Symptom | Likely cause | Fix |
| :---- | :---- | :---- | :---- |
| Data | You don't have the platform bundle or registry credentials | You haven't registered at Zetaris Cloud yet | Register at Zetaris Cloud and download them from its Run locally page. If the download isn't enabled for your account, contact Zetaris support or ask in Help Zetaris on HackOS |
| Data | ./preflight.sh reports failures | Docker isn't running, has too little memory or disk, or the registry sign-in is missing | Give Docker 8 GB and 4 CPUs, free 15 GB of disk, rerun the registry sign-in, then rerun preflight |
| Data | docker compose pull fails with "denied" or "unauthorized" | The registry didn't accept your sign-in | Rerun docker login with the registry credentials from the Run locally page |
| Data | ./verify.sh fails right after starting | First-time setup is still running | Wait until bootstrap shows Exited (0), wait another minute, then run it again |
| Data | Very slow first start on a Mac | Apple Silicon runs Zetaris's Intel-built images under emulation | Turn on **Use Rosetta** in Docker Desktop and allow extra time |
| Data | Sign-in fails | Wrong email or password; editing .env after the first start doesn't reset an existing account | Use the details you set in .env before the first start |
| Data | REST requests return 401 | The Zetaris API key is missing, wrong or expired | Create a new key in the Zetaris web interface and update .env |
| Data | REST requests return 400 | Wrong X-Org-ID, or X-Request-ID isn't a UUID | Use organisation ID 1 on a local install and a fresh UUID for every request |
| Data | "Object already exists" | You've already run that create statement | Check the existing object matches, reuse it and move on to the next statement |
| Data | A table is created but returns no rows | The Zetaris server can't reach the source, or the path is wrong | Check the source address, and that Zetaris itself (not just your laptop) can reach it |
| Data | A file on your laptop won't query | Zetaris can't read files on your laptop | Put the file in storage Zetaris can reach, such as an S3 bucket, then register it |
| Build | Grok or Composer is missing from Cursor's model menu, or requests stop | Your Cursor credit isn't active or has run out | Check your plan and usage in Cursor's settings, and ask the organisers about credit |
| Build | You see charges on your Meterless credit while coding | Your Meterless key ended up in Cursor's settings | Remove it from Cursor and code with Grok or Composer instead |
| Power | Nemotron calls fail even though each setting looks right | Settings mixed from the two routes, such as a Meterless key with NVIDIA's address | Take all three settings from the same route (Power 4.5) |
| Power | The smoke test says a MODEL\_ setting is missing | The setting isn't in .env, or .env isn't in the folder you ran the script from | Add the setting and run the script from your project folder |
| Power | Nemotron returns 401 or 403 | The API key doesn't match the route in MODEL\_BASE\_URL | Copy the key again from Meterless or build.nvidia.com |
| Power | Nemotron returns 404 or "model not found" | The model ID doesn't match your route's model list | Copy the exact model ID again from Meterless or the build.nvidia.com model page |
| Power | Requests fail with a credit or rate-limit error | Your Meterless credit has run out, or you hit NVIDIA's free-tier rate limit | Wait and retry, check your credit or limits, or switch routes by changing the three settings |
| All | pip install fails with "externally-managed-environment" | Your system Python blocks global installs | Create a virtual environment with python3 \-m venv .venv, then install with .venv/bin/pip install ... |
| All | python isn't found | Python is missing or not on your PATH | Reinstall Python 3 and tick "Add to PATH" on Windows |

### **Where to get help**

> * **Hackathon help channel:** the Help desk channel on HackOS, https\://hackathon.genai.works/messages  
> * **Event details:** the [Open Agent Hackathon 2026 event page](https://hackathon.genai.works/event/open-agent-hackathon-2026) for rules, tracks and submission  
> * **Zetaris:** the [getting-started repository](https://github.com/zetaris/getting-started), especially its [troubleshooting guide](https://github.com/zetaris/getting-started/blob/main/docs/guides/troubleshooting.md) and [installation guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md), plus the [Zetaris knowledge base](https://kbase.zetaris.com/knowledge)  
> * **Cursor:** [Cursor docs](https://cursor.com/docs)  
> * **Meterless:** [meterless.ai](https://meterless.ai) and the [Meterless GitHub](https://github.com/Meterless/Meterless)  
> * **Nemotron:** [build.nvidia.com](https://build.nvidia.com) for NVIDIA's free API, and NVIDIA's [Nemotron developer page](https://developer.nvidia.com/nemotron)

When you ask for help, include your operating system, the exact command you ran, the full error message and the last step that worked. Remove passwords, API keys and tokens before you share anything.

## **Glossary**

| Term | What it means here |
| :---- | :---- |
| Agent | An app where an AI model decides which steps to take and which tools to call, then uses the results to finish a task |
| API | A way for one program to ask another for data or actions over the internet |
| API key or token | A secret password your code sends so a service knows it's you; keep it in .env |
| Base URL (provider address) | The web address your code sends model requests to; for this hackathon, Meterless's address or NVIDIA's |
| Composer | Cursor's own coding model, built for fast everyday coding |
| Container | A self-contained package that runs one piece of software, like Zetaris's query engine or web interface |
| Credit | Prepaid usage. Cursor credit pays for Build; Meterless credit pays for Power if you take Option A |
| Docker Desktop | The app that runs containers on your laptop |
| Docker Compose | A tool that starts several containers together from one setup file, docker-compose.yml |
| .env file | A plain text file that holds your secrets and settings so they stay out of your code |
| Git, clone | Git tracks code versions; cloning downloads a copy of a project, such as Zetaris's getting-started recipes |
| Grok | A model from xAI included in Cursor, suited to harder, longer coding tasks |
| IDE | Integrated development environment: the app where you write and run code, such as Cursor |
| JDBC | A standard way for programs to connect to databases; Zetaris accepts JDBC connections on port 10000 |
| Lightning SQL | The SQL dialect Zetaris uses, including commands such as CREATE LIGHTNING REST TABLE for registering sources |
| LLM | Large language model: the AI that reads and writes text, such as Nemotron |
| localhost and ports | localhost means your own computer; a port, such as 3000, picks which program on it you're talking to |
| Model provider | The service your app sends model requests to and that bills for them; here, Meterless or NVIDIA's own API |
| Prompt file | A saved, reusable set of instructions you hand to an AI agent, such as those in the Meterless prompt library |
| RAG | Retrieval augmented generation: fetching relevant data first, then giving it to the model so its answer is grounded in facts |
| Registry | An online store of container images; Zetaris's platform images come from a private registry you sign in to |
| Semantic layer | A consistent business view of data that spans several systems; Zetaris's version is the Unified Semantic Layer (USL) |
| SQL | The standard language for asking questions of data, such as SELECT \* FROM customers |
| Terminal | The text window where you type commands: Terminal on macOS and Linux, a WSL terminal on Windows |
| Tool calling | A model's ability to reply with a request to run a function, such as run\_sql, instead of plain text |
| UUID | A long random ID, such as 3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90; Zetaris wants a fresh one with every API request |
| Vibe coding | Building software by describing what you want to an AI agent, then reviewing and steering what it produces |
| WSL 2 | Windows Subsystem for Linux: lets Windows run the Linux commands and software Zetaris needs |

## 