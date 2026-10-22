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

