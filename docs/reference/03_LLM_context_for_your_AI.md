# Open Agent Hackathon 2026: shared LLM context and team starting guide

**For every teammate:** upload this Markdown file to your preferred assistant, such as Claude, ChatGPT or Gemini, then send the starter message below. It is the team's consolidated reference and starting guide; no previous chat or access to the original project folder is needed to begin planning. Uploading a file alone does not guarantee an assistant will read it or start work. File support and available tools vary by product.

**Handover updated:** 19 Oct 2026. **Rules and source review:** 17 Oct 2026, as detailed below. The handover update does not establish that event information has been checked again since then.

**Starter message — copy after attaching this file:**

> Read the attached hackathon context pack, including section 0 and the team status in section 22. Help me get started as a team member. Explain the current phase, the key constraints and my next three practical actions, with a completion check for each. Ask only the missing questions needed to tailor those actions to my role, skills and our team's progress. Keep confirmed facts, proposals and unknowns separate. Do not assume we have selected a project or completed setup.

If the team has a newer checkpoint, attach or paste that alongside this file. This file provides the consolidated event reference; the checkpoint supplies the latest team decisions and evidence. A teammate's report can update team status but does not by itself change official event rules.

**Local filing note (optional):** this is the single current master, `01_Share_with_colleagues/03_LLM_context_for_your_AI.md`. Human-readable PDFs and editable slides are in the same sharing folder. Original organiser documents are in `02_Source_material/Organiser_guides`; recordings and transcripts are in `02_Source_material/Recordings_and_transcripts`. Older exports are in `90_Archive`; build/audit records are in `99_Workfiles`. Those folder names describe the author's workspace, not files automatically available to a recipient's assistant. Source filenames below identify provenance; they are not required attachments for initial guidance.

Last updated: 17 Oct 2026, incorporating the Participant Setup Guide (internally dated 15 Oct; local file modified 16 Oct) and the presentation source review. All ten official rule sections were expanded and re-read live during the one-page accuracy audit; they agree with the saved 15 Oct extract. Visible dates, prizes and scoring were rechecked, and displayed Sydney times independently recalculated. Zetaris's installation guide was also checked on 17 Oct. The saved FAQ remains the 15 Oct snapshot. Provider availability and local installations remain untested.

- **Build window:** opens Thu 22 Oct 2026, 00:00 UTC (11:00 Sydney).
- **Participant onboarding:** Wed 21 Oct, 12:00 to 13:30 UTC (23:00 to 00:30 Sydney).
- **Submissions close:** Tue 27 Oct, 23:45 UTC (Wed 28 Oct, 10:45 Sydney).

## 0. How to use this document (read first)

You are helping a team compete in the Open Agent Hackathon 2026. Use this document as the consolidated reference for rules, dates, judging expectations, engineering standards and sponsor technology. It is a dated synthesis, not a replacement for current official rules or organiser clarifications. Preserve source distinctions and unresolved conflicts. If fresh authoritative evidence changes a fact, record the source and date and explain the change.

### 0.1 First conversation: turn the reference into action [TEAM]

Read the whole attachment if supported. If any part is inaccessible or truncated, say which part is missing; do not claim to have reviewed it. Use the sections relevant to the immediate task and request only missing material that changes the next decision.

1. **Establish the phase.** Use the actual current date, not the file's update date. Before 22 Oct 2026 at 00:00 UTC / 11:00 Sydney, prioritise registration, learning, access, setup and scoping. Track and declare pre-existing work under section 3. During the build window, prioritise a working entry and submission. After 27 Oct at 23:45 UTC / 28 Oct at 10:45 Sydney, do not imply late submissions are accepted. For a different year or an unclear date, ask which event or retrospective task is intended.
2. **Give a short orientation.** State the phase and deadline; explain that the goal is a working agent system with meaningful sponsor integration, reproducible evidence and the four submission deliverables. Flag the unresolved Nemotron, Meterless and deployment wording before making a dependent technology choice. Use sections 3, 8, 10 and 20 for the actual requirements and qualifications.
3. **Check the latest team state.** Start with section 22 and any newer checkpoint supplied by the user. A plan, sample scaffold, presentation or expected test result is not evidence that the product or integration exists. Do not duplicate another teammate's assigned work without checking ownership.
4. **Ask a compact set of questions.** What is this person's role, experience, available time and operating system if setup is relevant? What project/track and responsibilities has the team actually agreed? What repository, challenge statement and setup/test results already exist? Accept partial answers and keep useful independent work moving; never request private keys or credentials in chat.
5. **Provide the next three actions immediately.** For each, specify an owner (or proposed owner), concrete output, dependencies and an observable completion check. Tailor scope to the person's experience and remaining time. When answers are missing, label assumptions and give preparation actions that do not require an unconfirmed project choice.
6. **End with a portable checkpoint.** Capture decisions, evidence, blockers, ownership and next actions using section 0.3. Ask the teammate to share it through the team's agreed channel. Separate assistants do not share memory automatically.

### 0.2 Route each teammate to useful work [TEAM]

These are proposed work areas, not an assigned roster. One person may cover several; agree owners before parallel work.

| Work area | First useful output | Completion evidence | Reference |
|---|---|---|---|
| Team coordination and problem choice | Confirm roster and working agreement; draft one user, problem, available data, intended output and success measure | Team-approved brief, owners and unresolved questions recorded; challenge fit checked | 3, 9, 14, 19 |
| Data and sponsor integration | Inventory lawful data access and platform/provider readiness; map each sponsor to a real product role | Actual connectivity results and an integration plan; distinguish access checks from a working agent loop | 11, 15, 20 |
| Agent orchestration and domain logic | Design the smallest feedback loop around one real input and useful output | During the build window, a logged end-to-end run with decisions, tool calls and feedback | 8, 11–13, 18 |
| Evaluation and testing | Define representative inputs, expected behaviour, failure cases and success criteria | Recorded observed results, including an unseen input and the three design tests; no invented passes | 7, 8.1, 16 |
| Demo, deck and documentation | Draft the evidence-backed story and a checklist for all four deliverables | Claims match real runs; README works for a new user; final links and live form checked | 10, 16 |

For a teammate without an agreed role, begin with the project brief, their skills and the team's unowned work. Suggest a manageable contribution and confirm it with the team. For someone joining mid-build, use the latest checkpoint to choose the next unblocked task instead of restarting Day 1.

### 0.3 Shared team checkpoint — fill with verified updates [TEAM]

Copy this block into the team's shared notes or the next assistant conversation. Keep one agreed current team record; personal chats are working copies. Record reports as reports until evidence is available. Do not replace unknowns with guesses.

```text
TEAM CHECKPOINT — Open Agent Hackathon 2026
Updated at / timezone / updated by: not yet supplied
Event phase and next deadline: determine from actual current date
Project / target user / problem / intended output: not yet confirmed
Track / challenge statement / source and date: not yet confirmed
Roster / lead / backup / responsibilities: not yet confirmed
This teammate's role / skills / availability / timezone: not yet supplied
Repository / agreed working branch / shared task board: not yet supplied
Data sources / permission / access status: not yet confirmed
Zetaris access and observed test results: not yet established
Meterless access / agreed meaningful role / observed results: not yet established
Cursor access and observed coding check: not yet established
Model provider / model ID / observed inference result (no secrets): not yet established
Working end-to-end run / trace or result location: not yet established
Latest official clarification / source / date: none recorded beyond this pack
Decisions made / by whom / supporting evidence: none recorded
Pre-existing work to declare / licence and attribution: not yet inventoried
Completed tasks / owner / evidence: record actual results only
Tasks in progress / owner / dependencies: not yet supplied
Blockers / responsible person / next check: see sections 19–20, then update
Next three actions / owner / output / completion check / target time: to agree
Submission status / four deliverable links / roster finalised: not yet established
Changes since previous checkpoint: record here
```

### 0.4 Working across different assistants [TEAM]

- This pack does not depend on a particular assistant, paid plan, connector or coding integration. Cursor is a hackathon development requirement described in section 3; it does not restrict which assistant a teammate uses to read this pack and plan their work.
- If browsing is available, check current official information when a decision depends on dates, eligibility or an unresolved conflict. If it is unavailable, explain the dated evidence and ask for the relevant announcement or challenge text. Never claim a live check happened when it did not.
- If code or terminal access is unavailable, provide steps suited to the teammate's operating system and ask for sanitised results. If tools are available, agree the target environment and scope before consequential execution. Reading this pack is not proof of installation or permission to publish, submit or contact others.
- The setup sequence and known configuration are consolidated in sections 11 and 15. Detailed organiser commands, platform bundles, credentials and account-specific endpoints may still need the original guide or sponsor Resources. Request the specific missing item when needed; do not require the whole source folder before giving initial guidance or invent a missing command.
- Use sections 19–20 as the unresolved-issue register. Mark proposals as [TEAM], source-backed requirements with their source tag, and missing facts as [UNKNOWN]. The numbered reference sections below remain the detailed basis for guidance.

**Source tags:**

| Tag | Source | Priority |
|---|---|---|
| [RULES] | The official event page, hackathon.genai.works/event/open-agent-hackathon-2026, read 15 Oct 2026. The ten rule sections were re-read live and confirmed on 17 Oct; the FAQ remains the 15 Oct snapshot. It covers dates, tracks, prizes, judges, the 10 rule sections and the FAQ. The rules and FAQ text is saved in `Official_Rules_Extract.md` | 1 (binding) |
| [ORG] | The 18 organiser guides given to participants (listed below). Six say outright that the Official Rules win if they conflict: `faq.md`, `submission-requirements.md`, `technical-execution-requirements.md`, `disqualification-checklist.md`, `team-formation-rules.md` and `ai-usage-policy.md`. `official-rules.md` is labelled a WORKING DRAFT. `technical-execution-requirements.md` calls itself "recommended practice, not a rule" | 2 |
| [SETUP] | [Participant Setup Guide](<../02_Source_material/Organiser_guides/Open Agent Hackathon 2026 Participant Setup Guide 121026.md>), supplied separately from the 18 guides. Its internal update date is 15 Oct, despite `121026` in its filename; the local file was modified 16 Oct. It adds installation steps and the Data / Build / Power framework, but still contains organiser placeholders and conflicting eligibility language. Its publication authority has not been independently established | Supplementary setup guidance; does not silently override [RULES] |
| [CALL] | The Data Day call with Zetaris, with Sam Cummings (host, GenAI Works) and Michael Hay (CTO, Zetaris). The raw `Onboarding_Call_Transcript.md` records local metadata of 13 Oct 2026 at 16:27 Sydney, while the organiser calendar lists 12 Oct UTC without a time. These do not establish an exact live-event timezone conversion. The edited `Open_Agent_Hackathon_Data_Day_Zetaris_Transcript_15102026.md` is dated 15 Oct; do not use its editorial date as the event date | 3 |
| [VENDOR] | A sponsor's own website | 3 |
| [LIVE17] | Event page full rule sections plus visible dates, prizes and rubric, and [Zetaris installation guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md), checked 17 Oct 2026. The installation guide distinguishes platform entitlement from the recipes' Apache licence | Current evidence for the specific passages inspected |
| [TEAM] | Our own plan or suggestion, not a rule | |
| [UNKNOWN] | Not yet confirmed | |

The 18 organiser guides are:
- `hackathon-overview.md`
- `welcome-guide.md`
- `event-calendar.md`
- `faq.md`
- `participant-journey-map.md`
- `how-approach-solutioning-for-your-use-case.md`
- `official-rules.md` (draft)
- `submission-requirements.md`
- `submission-form-preview.md`
- `demo-video-guide.md`
- `technical-execution-requirements.md`
- `disqualification-checklist.md` (a pre-submission self-check)
- `strong-submission-examples.md`
- `weak-submission-examples.md`
- `vibe-coding-starter-guide.md`
- `team-formation-rules.md`
- `code-of-conduct.md`
- `ai-usage-policy.md`

**Rules for you, the LLM:**
1. Do not invent technical details marked [UNKNOWN]. Say what needs checking and where (section 19).
2. Check every idea against the hard constraints (section 3), the disqualification risks (section 4) and the three tests (section 8.1). Say plainly if a suggestion fails any of them.
3. All deadlines are UTC. Our team works in Sydney time (AEDT, UTC+11). Give both whenever you mention a time.
4. Once the team pastes in the HackOS challenge pages, they override the general track descriptions here. The live HackOS submission form overrides `submission-form-preview.md`.
5. When you write code, follow sections 11 to 13: environment variables only, sponsor calls behind adapters, timeouts and retries, JSONL traces, a sample mode, and a programmatic entry point. Never hardcode outputs.

**What changed on 17 Oct.** The new guide supplies a detailed Windows/WSL and Docker setup path, Zetaris connection details, two Nemotron provider routes, a readiness checklist and a smoke test. Sections 11, 15 and 18 now incorporate these. Sections 19 and 20 retain unresolved questions about mandatory Nemotron use, Meterless's required role and local deployment. Section 22 records what has actually been produced in this workspace.

## 1. Event at a glance

| Item | Detail | Source |
|---|---|---|
| Name and tagline | Open Agent Hackathon 2026: "Build an agent that does real work" | [RULES] |
| Organiser | GenAI Works (brand written "GenAI.Works") | [RULES] |
| Platforms | **HackOS**: announcements, challenge pages, Resources (one folder per sponsor), team-finding, mentor office hours, #help desk and sponsor Help channels, submission, and the results call [ORG]. **Discord**: the event page says "Kickoff, office hours, judging and results all happen online in Discord and on the platform", and that schedule changes are announced "on this page and in Discord", but joining Discord is optional [RULES]. **[TEAM]** Watch both HackOS Announcements and Discord | [RULES], [ORG] |
| Format | Fully online, 22 to 27 Oct 2026. Advertised as 144 hours; the exact published start-to-close interval is 143 hours 45 minutes. Free to enter | [RULES], [LIVE17] |
| Eligibility | Aged 16+ at the start of the build window; one account per person | [RULES] |
| Teams | 1 to 5 people. Solo entries compete in the same pool | [RULES] |
| Registered | 3,369 as of 15 Oct | [RULES] (event page) |
| Sponsors | SpaceX AI (written "Space XAI (with Cursor)" in the organiser guides), NVIDIA, Zetaris, Meterless. "Spex" in the raw transcript means SpaceX AI | [RULES], [ORG] |
| Judges | Michael Hay (CTO, Zetaris); Michael Armentano (Head of Technical Partnerships, SpaceXAI); Sam Cummings (Director of Education, GenAI Works); Shestakov Vladyslav (Head of Engineering, GenAI Works); Remus Ranca (Education Operations Lead, GenAI Works) | [RULES] (event page) |
| Prize pool | Up to $20,000: $13,000 cash plus $7,000 in-kind (section 6) | [RULES] |
| What it is not | "Prompt chains, chatbots, and UI-only demos do not meet the bar" | [ORG] |

**The mandate** [ORG]. Build agents that can:
- access relevant information
- understand context and relationships
- reason across multiple steps
- keep useful context
- turn that into a useful outcome for a defined user

**The quality bar** [ORG]: "A strong submission is not a polished UI or a clever prompt." It is "a working, reproducible agent system that shows real collaboration, integrates Zetaris and Meterless with a real role, and is easy for judges to run and understand".

**What does not meet the bar** [ORG, draft rules 7.3]:
- a fixed chain with no feedback
- prompt wrappers, or one agent with several labels
- hardcoded outputs or fabricated agent activity
- a UI with no working system behind it

## 2. Timeline

| Milestone | UTC | US Pacific | Sydney (AEDT) | Source |
|---|---|---|---|---|
| Registration opens | Fri 14 Aug, 00:00 | | | [RULES] |
| Data Day workshop: Zetaris, "serving internal data" (recording available) | 12 Oct in organiser calendar; no time supplied | Not established | Exact live-event date not established from recording metadata | [ORG], [CALL]; see section 20 |
| Build Day: Cursor ("build with"), GenAI Works ("how to build, vibe coding"), Meterless engines ("build faster") | To be confirmed | | | [ORG] |
| Power Day: NVIDIA ("cloud provider"), Meterless ("local and cloud provider") | To be confirmed | | | [ORG] |
| **Participant onboarding** (recorded) | **Wed 21 Oct, 12:00 to 13:30** | Wed 21 Oct, 05:00 to 06:30 | **Wed 21 Oct 23:00 to Thu 22 Oct 00:30** | [ORG] |
| **Build window opens** | **Thu 22 Oct, 00:00** | Wed 21 Oct, 17:00 | **Thu 22 Oct, 11:00** | [RULES] |
| **Registration closes** (hard; no new registrations after it) | **Thu 22 Oct, 23:45** | Thu 22 Oct, 16:45 | **Fri 23 Oct, 10:45** | [ORG]; see section 20 |
| Suggested mid-build self-check | Sat 24 Oct, 16:00 | Sat 24 Oct, 09:00 | Sun 25 Oct, 03:00 | [ORG] |
| Full judge-style validation (section 16) | 25 Oct ("day four") | | | [ORG] |
| Suggested final validation | Tue 27 Oct, 12:00 | Tue 27 Oct, 05:00 | Tue 27 Oct, 23:00 | [ORG] |
| **Submissions close** (hard; late entries are not evaluated) | **Tue 27 Oct, 23:45** | Tue 27 Oct, 16:45 | **Wed 28 Oct, 10:45** | [RULES], [ORG] |
| Judging | Opens straight after close (28 Oct) | | | [ORG] |
| Results: live call on HackOS, with certificates | Fri 6 Nov, 16:00 | Fri 6 Nov, 08:00 | Sat 7 Nov, 03:00 | [RULES], [ORG] |

- **Workshops.** Join through the GenAI Academy course: https://academy.genai.works/courses/open-agent-hackathon-2026/details. All workshops are recorded on HackOS.
- **Session dates.** The call mentioned sessions on 15, 19 and 20 Oct; the organiser guides still say "to be confirmed".
- **Onboarding agenda** [ORG]. It is delivered by the GenAI Works team and the Product Team, and covers:
  - welcome, timeline and prizes
  - the tracks and what strong looks like
  - how the sponsor tools fit
  - a HackOS walkthrough
  - submission and judging
  - Q&A

  "Additional challenges and prizes" are also presented. Joining details are on HackOS.
- **Challenge statements** are "announced on the day of" kickoff [CALL]. The full statements are on the HackOS challenge pages [ORG].
- **Time zones do not extend the window**, and nothing can be added or fixed after the deadline [RULES, ORG].

## 3. Hard constraints

1. **Integrate Zetaris and Meterless in the product, in every track** [RULES].
   - They must be "load-bearing, not decorative" [ORG].
   - **Removal test:** "if I removed Zetaris, would the agent still work? If yes, it isn't integrated yet" [ORG].
   - A sponsor named in the README but absent from the code "scores worse than not mentioning it" (`disqualification-checklist.md`) and "scores worse than an honest, smaller integration, because it reads as padding" (`weak-submission-examples.md`).
2. **Use Cursor as the development environment** [RULES]. Other AI coding assistants, such as terminal coding agents or autocomplete, "may be used alongside it" as development aids [ORG].
3. **Use NVIDIA technology wherever it contributes** [RULES], through hosted or cloud access so judges need no NVIDIA hardware [ORG].
   - **Conflicting setup wording [SETUP]:** the newer supplied guide says the product must run on NVIDIA Nemotron. Treat that as a requirement stated by that guide, pending confirmation of whether it supersedes the earlier rules (sections 19 and 20).
4. **Anything else is allowed** [RULES]: any language, framework, model or cloud, including closed-source APIs, paid APIs and sponsor credits. Pre-existing open-source libraries are fine within their licences.
   - [SETUP] offers Nemotron through either Meterless or NVIDIA directly, but also says Zetaris and Meterless must run on the participant's machine. Direct NVIDIA access alone does not establish compliance with the earlier Meterless integration requirement. Confirm the intended runtime and deployment requirements before committing to an architecture.
5. **Declare pre-existing work** [RULES, ORG].
   - Work committed before 22 Oct, 00:00 UTC is not eligible unless declared in the submission form.
   - Declare product code, prepared data, models or prior prototypes. Open-source libraries do not need declaring.
   - Wildcard teams also describe the state of their project before 22 Oct.
6. **The GitHub repository must be public** by the deadline [ORG: submission requirements, form preview, draft rules].
7. **Exactly one primary track**, chosen from the four including the Wildcard [RULES, ORG].
   - It sets your judging panel and prizes.
   - You can change it until the deadline.
   - Cross-track relevance "is not scored twice".
   - Name the same track in the README, deck and demo.
8. **Team rules** [RULES, ORG]:
   - Each person is in exactly one team and appears on one submission.
   - Every member must be registered by 22 Oct, 23:45 UTC.
   - The team locks when the first submission is **created**. After that, changes need organiser approval and are only for admin errors.
   - One account per person; duplicate accounts disqualify the whole team.
9. **Secrets come from environment variables only** [ORG].
   - Keep them in `.env` (gitignored) and commit a `.env.example` with placeholders.
   - Never put real keys in code, the README, notebooks, config, logs, screenshots, the video or the deck.
   - If a key is committed, **rotate it first**, then remove it from history.
   - Use sponsor credentials only for hackathon work, never share them, and report any compromise [ORG draft rules 19].
   - Do not bypass sponsor quotas or controls [ORG code of conduct].
10. **Data must be legal and appropriate** [ORG].
    - **Allowed:** public licensed data, small samples, login-free download scripts, public APIs, and labelled synthetic data.
    - **Not allowed:** confidential or restricted data, "personally identifiable information", or private or sensitive data.
    - Do not show personal data in the video, and do not use anyone's image, voice, name or likeness without permission.
11. **No hardcoded outputs, no fabricated logs, no misrepresentation** (section 5).
12. **The team must be able to explain its code** [ORG]. "The AI wrote it" is not an answer.

## 4. Disqualification and what costs points

**Disqualification triggers** [ORG: draft rules section 16 and AI usage policy section 12; the binding rules section 10 adds only that "Disqualification decisions are final and are communicated with a reason to the team lead"]. A submission may be disqualified if it:
- is late, or cannot be run or evaluated
- uses hardcoded outputs, has no real agent logic, or shows no evidence of how the agent reached its output
- does not integrate Zetaris and Meterless
- commits API keys, tokens or secrets
- includes unauthorised confidential, personal or restricted data, or assets used without permission
- includes undeclared pre-existing work or plagiarism
- contains malicious code
- misrepresents things: fabricated logs, a README or deck that overclaims, or false authorship
- belongs to a team that cannot explain its own solution
- comes from duplicate accounts, or someone on two teams
- breaks the code of conduct

**Organisers' predicted outcomes** [ORG `weak-submission-examples.md`]:

| Weakness | Predicted outcome |
|---|---|
| Zetaris or Meterless missing | "Fails a requirement" |
| Linear pipeline or prompt wrappers | "Low Technical and Innovation scores" |
| Single agent presented as many | "Low Technical score, integrity question" |
| Hardcoded outputs, committed keys, undeclared work | "Disqualification risk" |
| Private repo | "Cannot be judged properly" |
| UI only, no programmatic path | Low Technical score |
| Missing deck or over-length demo | "Incomplete submission, low Demo score" |
| No clear track fit | "Low Impact score" |

**Damage ranking** [ORG self-check]:
1. A judge cannot run it ("you're judged on your video alone").
2. The repo is private.
3. There are no traces.
4. Outputs are hardcoded.
5. Secrets are committed.
6. Sponsor tech is mentioned but not used.
7. The README overclaims.
8. It only works on your laptop.
9. It was submitted at 23:44.

**Hardcoding red flags** [ORG]:
- `if input_id == "example_1"`
- `# TODO: replace with real agent later`
- a `run_sql` that returns fixed rows and "pretends to call Zetaris"
- reading `output_examples/` at runtime
- every input returning the same answer

## 5. AI usage policy [ORG]

**Allowed and encouraged:**
- any model, including closed-source, open-weight and paid [ORG]; the mandatory-Nemotron wording in [SETUP] remains a source conflict (section 20)
- any framework
- AI-assisted and vibe coding
- debugging, tests, Dockerfiles and README drafting
- prompt engineering
- synthetic test data, labelled

**Not allowed:**
- hardcoded outputs presented as agent results: the same answer for any input, matching known inputs to stored outputs, detecting a judge's input, faked model calls, or a scripted "agent debate"
- fabricated or edited logs
- plagiarism
- undeclared pre-existing work
- committed secrets
- a README or deck that claims more than the system does, such as "real-time" when it uses cached data, "collaborating agents" when it is a fixed chain, "fine-tuned" when it is only prompted, or mocked sponsor integration
- "claiming production readiness without disclosing limitations"
- fabricated citations, data provenance or benchmarks

**The README should disclose:**
1. models and providers
2. frameworks
3. how Zetaris and Meterless are integrated, how Cursor was used, and where NVIDIA contributes
4. tools and libraries
5. data sources, and whether they are sample or synthetic
6. adapted open-source code
7. limitations
8. sample-mode behaviour

A "Third-Party Code and Licences" section is recommended.

**Compliance is checked** in repo inspection, execution, log review, demo and deck review, and judge Q&A. Reviewers look for "suspiciously identical outputs across different inputs" and for gaps between the README and the code.

## 6. Tracks and prizes (event page, 15 Oct)

| Track | Brief | Data that fits [ORG] | Cash 1st / 2nd / 3rd |
|---|---|---|---|
| 01 Solving Fragmented Intelligence | Discover and work across fragmented data sources | Three or four small sources that disagree | $1,600 / $1,200 / $900 |
| 02 The Agent That Can Explain Why | Investigate complex questions across sources, connect findings, give evidence-backed answers or recommendations | Documents for one bounded question; every conclusion traceable | $1,600 / $1,200 / $900 |
| 03 Reasoning Architecture | Turn data, knowledge, memory and reasoning into reliable decisions and actions | Records, rules or policies, and memory of past decisions | $1,500 / $1,200 / $900 |
| Wildcard [Tinkerer] (bonus) | Extend an existing project with Zetaris and Meterless; only new work is scored. It is one of the four track choices, **not** an add-on | Keep old and new work separate; show a before and after | $1,000 / $600 / $400 |

**In-kind awards** [RULES], $7,000 in total:
- **Best use of NVIDIA Nemotron:** an NVIDIA DGX Spark (Founder's Edition), worth $4,699.
- **Best use of Cursor-built product:** SpaceX Cursor API credits, worth $2,301.

**Other prize rules** [RULES, ORG]:
- The top project is featured in the community showcase.
- Cash is paid by bank transfer within 30 days.
- Cash is split equally unless the team submits a different split in writing.
- Taxes are the winner's responsibility.
- Staff of the organiser and of judging sponsors cannot win cash.
- The organiser may change prizes for operational reasons.

**Choosing a track by team size** [ORG]:
- **Solo:** Track 01 (three small sources), Track 02 (one bounded question), or the Wildcard **if you already have a working prototype**.
- **Two to three people:** Track 02 with a critic loop, Track 01 with reconciliation, or Track 03 with a domain expert.
- **Four to five people:** Tracks 01 to 03 with clear roles.

**[TEAM]** Zetaris (federated SQL plus a semantic layer) fits Tracks 01 and 02 naturally. Running model calls on Nemotron targets the DGX Spark.

## 7. Judging

Scored out of 100 by at least three judges per submission [RULES]. Judges may ask for clarification during judging, and the organiser guides say participants receive feedback [ORG].

| Criterion | Points | What judges look for | Evidence they expect [ORG strong examples] |
|---|---|---|---|
| Impact | 30 | Fit with the challenge statements; a meaningful problem for its users | README, deck and demo "name a real user, a real problem and the track it answers" |
| Technical | 20 | Implementation, reliability, architecture | "distinct roles, real interdependence and traceable behaviour. Failures are handled" |
| Innovation | 15 | Originality | "A thoughtful agent pattern, not a familiar chain with new labels" |
| Demo | 15 | How clearly the demo shows the solution and its value | A real run plus "a collaboration moment in the logs" |
| Product & UX | 10 | Intuitive, accessible, easy to use | "The output is something the intended user could act on" |
| Sponsor Tech | 10 | How well the sponsors' tech addresses the problem | Zetaris and Meterless shown doing real work |

Ties are resolved on the Impact score, "then on submission timestamp" [RULES]. The saved rule does not specify which direction wins; do not present an earlier-submission advantage as an explicit rule.

**Judges prioritise** [ORG]:
- agents doing real work
- clear applications
- thoughtful architecture
- several agent interactions
- outputs refined through iteration
- agents that challenge each other
- branching
- reliability
- clear logs
- usable outputs

**Judges discount** [ORG]:
- UI polish without depth
- single-agent systems
- hardcoded demo paths
- broad concepts with weak implementation
- unsupported claims
- sponsor tech bolted on

**Judges also:**
- test with their own inputs: "a project that only works on the three you shipped is a project that doesn't work"
- may not have your keys
- have limited time: "anything they cannot start, call or read counts against you"

**A UI** is welcome, but judges should also be able to drive the agent without it [ORG].

**Judges should be able to say** [ORG]: "I can run it without manual setup", "The logs prove real collaboration, not a linear chain", and "The team made thoughtful trade-offs and was honest about limits".

## 8. Agent system design [ORG]

### 8.1 Three tests

1. **Removal test.** If we removed Zetaris (or Meterless), would it still work? If yes, it is not integrated. A token `SELECT 1` scores near zero and damages credibility "across every criterion".
2. **Collaboration test.** "Does at least one agent critique, validate, revise, delegate, retry or escalate based on another agent's output?" If not, it is "task chaining, not collaboration".
3. **Hardcoding test.** "If a judge submits a new valid input that is not in my examples, will my system still produce a real answer?"

### 8.2 Patterns and minimums

- **Minimum:** "At least two clearly defined agents that genuinely interact". A strong system usually has **3 to 5** agents. "Quality of interaction matters more than number of agents."
- **Show at least three of these seven patterns:**
  - dynamic delegation
  - a critique loop
  - retry logic
  - shared state
  - escalation, or fallback to sample data
  - **role authority**: "Evaluator can block the Writer until every claim is supported"
  - **non-linear flow**: "branch on confidence, missing data or risk"
- **Weak:** `Agent A -> Agent B -> Agent C` ("three 'agents' in name, but it is only a pipeline"); prompt wrappers ("Naming a class 'Agent' does not make it one"); one prompt playing every role (an integrity issue).
- **Fix:** make one agent's output change what another does, and branch the control flow on agent outputs.
- **Strong flow:** Planner -> Researcher -> Planner -> Executor -> Evaluator -> Executor -> Risk Agent -> Planner -> Final Response. A bounded loop (for example `for attempt in range(2)`) has the Evaluator assess, the Planner revise and a Critic trigger rewrites.
- **Beginner default:** Planner <-> Executor <-> Evaluator. "A strong simple architecture beats a complex broken one."

### 8.3 Example architectures by track

These are organiser composites, "not templates you must copy".

- **Track 01, SupplyLens:**
  - Source Mapper -> Zetaris (ERP, ticket system, risk API) -> Reconciler -> Conflict Critic, with shared state.
  - The Critic sends "records disagree" back to the Reconciler and "source missing" back to the Mapper.
  - A Reporter gives one sourced answer: "every fact in the answer names its source".
- **Track 02, ChurnWhy:**
  - User: a customer success lead asking "why did churn rise this quarter?"
  - Agents: Planner, Data Retriever, Evidence Evaluator, Analyst, Explanation Writer and Final Reviewer, sharing state (question, hypotheses, evidence, scores).
  - The Evaluator returns untested hypotheses to the Planner and blocks unsupported claims; the Reviewer forces a "correlation, not proven causation" caveat.
  - **Unique sponsor use:** "The Evaluator uses Zetaris directly to check claims", re-querying to confirm the Analyst's numbers.
  - Meterless runs model calls on NVIDIA Nemotron: a larger model for the Analyst and Evaluator, a smaller one for planning.
- **Track 03, TriageDesk (clinic bookings):**
  - Intake -> Rules Checker (Zetaris: availability, policy, past decisions) -> Memory Keeper -> Priority Critic -> Scheduler.
  - The Critic rejects decisions inconsistent with past ones or "unsafe or unfair".
  - "every booking carries its reasoning".
- **Wildcard:**
  - A declared pre-22-Oct keyword search, extended with Zetaris (documents plus two databases), Meterless-run reasoning agents and an Evaluator.
  - "the demo shows the difference".
- **Example role names:**
  - Track 01: Source Mapper, Reconciler, Conflict Critic, Reporter.
  - Track 02: Research Planner, Retriever, Evidence Summarizer, Insight Critic.
  - Track 03: Intake, Rules Checker, Memory Keeper, Priority Critic, Decision Agent.
- **Honest output** carries:
  - per-finding `confidence` and `evidence`
  - `untested_factors`
  - `limitations`
  - `recommended_actions`
- **The architecture diagram** should show where decisions happen, where Zetaris and Meterless sit, shared state, loops and retries, the sample fallback, where logs go, and how the answer is produced.

**Frameworks** are open choice and not scored: LangGraph, CrewAI, AutoGen, OpenAI Agent SDK, LangChain or LlamaIndex, custom Python plus FastAPI, or a multimodal stack. In the Data Day call Michael mentioned LangGraph or LangChain, Databricks, a coding harness, or homegrown code [CALL].

## 9. Scoping: the APPROACH method [ORG]

| Step | Key question |
|---|---|
| **A**ssess | Is the problem clear, valuable and narrow? |
| **P**ick ambition | Is it realistic for our team? |
| **P**rove data | Is the data usable with no manual steps or private keys? |
| **R**educe | What is the smallest impressive version? |
| **O**utline | Do agents critique, retry or escalate? |
| **A**lign | Does it run reliably, with the sponsors integrated? |
| **C**onfirm | Does it fit the rubric? |
| **H**arden | Can we deliver the video, deck, repo and write-up? |

**Problem statement:**

> "We are building an agent that helps [user] solve [specific problem] by [agent capability] using [data source], producing [output]."

**Scope formula:** one user, one decision, one data slice, one strong output, and clear agent behaviour.

**Ambition levels:**
- **Focused:** 2 to 4 agents, 1 source, 3 to 5 sample inputs, 1 refinement loop. Suits solo builders, pairs and teams new to agents.
- **Ambitious:** 3 to 5 agents, 1 to 2 sources, a bounded domain, at least one branch or retry.
- **High-risk:** only with domain expertise. Narrow scope, curated data, strong caveats, "no heavy training or simulation at runtime", and a fallback.

**Self-score.** Score each of these 0 to 2:
1. Can we explain the problem in 30 seconds?
2. Do we know the user?
3. Is the data accessible?
4. Can we build it in 144 hours?
5. Does it run quickly?
6. Do Zetaris and Meterless have a real role?
7. Do agents interact more than once?
8. Is there critique or retry?
9. Can we show useful output in 1 to 4 minutes?
10. Can we document the limitations?

16 to 20 means go; 11 to 15 means reduce scope; 6 to 10 means simplify; 0 to 5 means pick another idea.

**Red flags:**
- a private key we lack
- a dataset needing manual approval
- multi-GB data with no sample plan
- GPU training
- a fixed sequence
- sponsors with no real role
- generic text output
- failing when an API is down
- manual steps
- no sample inputs and outputs
- no trace

**Hosts' framing [CALL]:**
- **Four lenses:**
  1. data entry (for example, photograph a table instead of uploading a CSV)
  2. prioritisation (insight, not information)
  3. insight retrieval
  4. prediction (for example, a pipeline leak)
- **Read the challenge as the "verb"**: the capability you improve versus the outcome it supports.
- **"The battle" is linking structured and unstructured data.**
- **"Most people are working on the wrong abstraction layer."** Value can come from the data, from building the agents, or from powering them with models and tools.
- **Prep split:** about 40% Zetaris, 40% Meterless, 20% use case; the Tinkerer track flips this toward integration.

**Responsible AI** [ORG draft rules 18], where relevant:
- input validation
- stated limitations
- human review for high-risk outputs
- disclaimers for medical, legal, financial or safety use
- no unauthorised autonomous actions

## 10. Deliverables and submission

### 10.1 The four deliverables [RULES]

Submit on HackOS by 27 Oct, 23:45 UTC (Wed 28 Oct, 10:45 Sydney). You can update until then.
1. **Demo video,** 1 to 4 minutes (section 10.3).
2. **Slide deck** covering:
   - the problem and target users
   - the solution
   - the agent workflow or architecture
   - the technical stack
   - how Zetaris and Meterless were used
   - what was unique about our use of the sponsor technologies
   - product visuals
   - future enhancements

   [ORG] Use one slide per point, consistent with the repo and demo: "Do not claim anything the code does not do".
3. **Public GitHub repository** with all code and a README covering setup from a clean clone, usage with sample inputs, and dependencies including the sponsor services. Include Colab links if used. Recommended: 3+ real sample inputs and outputs, traces, `.env.example` and a sample mode.
4. **Sponsor technology explanation** [ORG template]. Write one concrete paragraph per technology, never one line:
   - **Zetaris:** how it is integrated and its role.
   - **Meterless:** how it is integrated and its role.
   - **Cursor:** how it was used. Example: "used its Agent chat to scaffold the repository, write the Zetaris adapter and generate tests, and reviewed every change before committing".
   - **NVIDIA:** where it contributes.
   - Finish with what was unique.

### 10.2 The submission form [ORG `submission-form-preview.md`]

The preview is not the form: "If the form on HackOS and this preview differ, follow the form and the Official Rules." **The team's primary contact submits once for the team.** Solo builders are the only member and the primary contact.

| # | Item | What to give |
|---|---|---|
| 1 | Project name and description | "One clear sentence, plus a short paragraph": who it is for, what it does, what it produces. Not "An AI agent platform for business" |
| 2 | Track | Exactly one of the four |
| 3 | Team members | For each person: full name, HackOS account email, GitHub username, role, and primary contact (yes for one member). Contributors only; GitHub usernames must match the repo contributors |
| 4 | GitHub repository URL | `https://github.com/<user-or-org>/<repo>`. Public; test it while logged out. Never a local path or zip |
| 5 | Demo video | Uploaded or linked |
| 6 | Slide deck | Required |
| 7 | Sponsor technology explanation | Section 10.1, item 4 |
| 8 | Pre-existing components | Code, prepared data, models or prior prototypes; Wildcard: the state before 22 Oct |
| 9 | Colab links | Only if used (also in the README) |

- **One package.** The submission is judged as one package; "Submit only when every part is complete, accessible and consistent".
- **Roster accuracy.** Listing someone without consent, or leaving out a real contributor, is a code of conduct matter.
- **Prize split.** Agree it before submitting.
- **[UNKNOWN]** Field length limits, deck format and size, video size limit and host, and whether there is a field for a non-equal prize split.

### 10.3 Demo video [ORG `demo-video-guide.md`, strong examples]

- **Length:** 1 to 4 minutes; aim for **2:30 to 3:30**. Over 4 minutes "does not meet the requirement". It is "not judged on production quality".
- **Must show:**
  - the track, the problem and the user
  - at least two agents with clear roles, and real collaboration ("a moment where one agent changes another's work")
  - a live or recorded run on real or synthetic data, saying which. You may cut waiting, "but the input and output must be real"
  - Zetaris and Meterless doing real work, not just logos; NVIDIA if used
  - key features, the final output and why it is useful

**Storyboard** (merging the organiser's timings, which do not quite add up):

| Time | Segment | Show |
|---|---|---|
| 0:00 to 0:20 | Problem | "Our entry is for [track]", the user and the pain point |
| 0:20 to 0:45 | Solution and architecture | What goes in, what processes it and what comes out; the architecture diagram; whether data is real, public or synthetic |
| 0:45 to 1:25 | Agents and collaboration | Roles, messages, feedback loops, validation, and retries or shared memory |
| 1:25 to 2:15 | Live run | `curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json`, `python run.py --input input_examples/example_1.json`, or a UI backed by the real system |
| 2:15 to 2:45 | Sponsor technology | Trace lines querying Zetaris and the data returned; model calls via Meterless; NVIDIA; "built in Cursor" |
| 2:45 to 3:30 | Output and impact | The final output, a collaboration trace snippet, and confidence, evidence or limitations |

- **File:** MP4, 1080p, 16:9, audio required; captions are optional. Name it `OAH2026-TeamName-Track-Demo.mp4`.
- **A shared link must** open in a private window without a permission request, play with audio, and stay live until judging ends.
- **Recording:** use a larger terminal font, browser zoom at 110 to 125%, a visible cursor and a headset.
- **Secrets:** clear terminal history, hide `.env`, never open API key pages, check terminal frames, and show only masked values (`KEY=***`).
- **Backup, ready before 27 Oct:**
  - a second copy hosted somewhere different
  - the local MP4
  - a teammate's copy
  - the link in the README under `## Demo Video`

  If the upload fails, post in #help desk with the team, track, links, repo, error and the time in UTC.

## 11. Engineering standard [ORG technical guide: "recommended practice, not a rule"; and examples]

| Standard | Meaning |
|---|---|
| **Runnable** | Starts from a clean checkout with one documented command |
| **Reachable** | `run.py` and/or `POST /run` (FastAPI on `0.0.0.0:$PORT`, default 8000), not only a UI. The UI should be "a thin layer" calling `/run` |
| **Reproducible** | Docker or a fully documented environment; installs at build time; no runtime installs or model downloads |
| **Portable** | No local GPU; NVIDIA through hosted or cloud access |
| **Bounded** | Timeouts (external API 10 to 30 s; model call 30 to 90 s; loop iteration 1 to 3 min; full run 5 to 10 min); capped loop iterations; controlled errors |
| **Secure** | Environment variables only; masked in logs; validate required variables at startup with a clear error |
| **Data-conscious** | A light repo; small samples in `data/`; documented sources and licences; process only the submitted input |
| **Observable** | stdout plus `logs/trace-<id>.jsonl` |
| **Integrated** | Zetaris and Meterless behind adapters (`app/adapters/`), each with a timeout, retry and logged fallback |
| **Agentic** | Traces show handoffs, critique and retries |

**Request and response contract.** "There is no mandated structure" [ORG]; the two guides use different field names. [TEAM] Combine them:
- **Request:** `{"run_id", "input": {"query", "context"}, "options": {"sample_mode"}}`.
- **Response:** `{"run_id", "trace_id", "status", "output": {answer, evidence, confidence, limitations, recommended_actions}, "agents_used", "collaboration": {feedback_loop_completed, revision_count, evaluator_findings}, "log_path", "execution_time_seconds"}`.
- **Failure:** return a structured error, `{"status": "error", "error": {"type", "message", "recoverable"}}`. Bad input gets `400`.

**Trace lines** (JSONL, one object per line):
- **Fields:** `timestamp`, `run_id` or `trace_id`, `agent_name`, `action`, `input_summary`, `output_summary`, `target_agent`, `confidence`, `retry_count`, `status`, plus `model` where relevant.
- **Status values used** in the examples: `success`, `needs_revision`, `retrying`, `needs_validation`, `partial_success` and `fallback`.
- **Logs alone should let a judge follow the workflow.** Log every Zetaris and Meterless call and its result.
- **Never hand-write or edit traces.**

**Failure handling** (organiser pattern):

| Failure | Response |
|---|---|
| Zetaris timeout | Retry narrower, then fall back to sample data |
| Empty result | The Planner broadens the query |
| Unsupported claim | The Evaluator blocks it |
| Model failure | Retry once, then return a structured error |

Example settings: tenacity `stop_after_attempt(3)` with `wait_exponential(min=1, max=8)`, `requests` with a timeout, and fallbacks logged as `status="fallback"`.

**Sample mode** (`SAMPLE_MODE=true`):
- **What the guides say:**
  - It "runs the whole thing with no live credentials" and works "without any network access".
  - It "still runs real agent logic on cached data, rather than replaying a saved output".
  - It "must not load prewritten final answers, fake agent interaction, or pretend a sponsor service was called".
  - Test it from a fresh clone with an empty `.env`.
- **[UNKNOWN]** The guides do not say how model reasoning runs with no keys. [TEAM] Options include a small local model, possibly through Meterless's local engine. Decide on Day 1 and label any cached component honestly in the logs, for example `source: sample_data`, never as a Zetaris call.

**Zetaris REST call** [ORG `vibe-coding-starter-guide.md`]. See the HackOS Zetaris folder for "the full API reference".
- **Endpoint:** `POST {ZETARIS_REST_URL}/sql-editor/sqls/run`.
- **Headers:** `Authorization: Bearer {ZETARIS_API_KEY}`, `X-Org-ID: {ZETARIS_ORG_ID}`, and a fresh UUID in `X-Request-ID`.
- **Body:** `{"queryId": "<uuid>", "sql": "...", "source": "SqlEditor", "limit": 100}`.
- **Rows:** read them from `response.json().get("data", [])`.
- **Defaults:** `ZETARIS_REST_URL=http://localhost:8888/api/v1.0` and `ZETARIS_ORG_ID=1`. The local GUI is on port 3000.
- **JDBC [SETUP]:** `jdbc:zetaris:lightning@localhost:10000`, with Java 11+ and the Zetaris JDBC driver from the platform download. These supplied settings have not been tested on this machine.
- **API reference [SETUP]:** the local instance serves `http://localhost:8888/redoc/index.html`. Port 8889 is internal; use the exposed REST service on 8888. The guide says username/password are needed for downloading the API specification, while SQL calls use the API key.

**Model client** [ORG]: the `openai` package with `MODEL_BASE_URL`, `MODEL_API_KEY` and `MODEL_NAME`; raise if the key is missing; `timeout=60.0`, `max_retries=1`, `temperature=0.2`. The strong example labels the key "your-meterless-or-provider-key", which suggests Meterless can be the model endpoint.

**Configuration alignment [SETUP, TEAM].** The setup guide uses `NEMOTRON_MODEL` instead of `MODEL_NAME`. Use `NEMOTRON_MODEL` for its smoke test; if reusing an older example, explicitly map that value to `MODEL_NAME` in configuration. Keep the provider address, key and model ID from the same route. The direct NVIDIA address supplied by the guide is `https://integrate.api.nvidia.com/v1`; the Meterless event address is still an organiser placeholder. Copy the exact available model ID from the selected provider rather than assuming both routes expose the same models.

**`.env.example`** (placeholders only):

```bash
MODEL_BASE_URL=https://api.your-provider.example/v1   # or the Meterless endpoint, once confirmed
MODEL_API_KEY=your-meterless-or-provider-key-here
NEMOTRON_MODEL=exact-model-id-from-your-selected-provider
# MODEL_NAME is used by older examples; map it explicitly if retaining them.
MODEL_REASONING=your-larger-model                    # optional: larger model for analysis or evaluation
MODEL_FAST=your-smaller-model                        # optional: smaller model for planning
ZETARIS_REST_URL=http://localhost:8888/api/v1.0
ZETARIS_API_KEY=your-key-here
ZETARIS_ORG_ID=1
# The selected provider key goes in MODEL_API_KEY. Add separate sponsor keys
# only if an additional integration actually consumes them.
SOURCE_TIMEOUT_SECONDS=20
MAX_RETRIES=2
SAMPLE_MODE=false
LOG_LEVEL=INFO
PORT=8000
```

**`.gitignore`** should cover `.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `credentials.json`, `secrets.toml`, `secrets/` and `credentials/`.

## 12. Repo scaffold [ORG, plus TEAM docs]

```text
/project-root
├── app/agents/            # one file per agent (planner, executor or analyst, evaluator, reporter)
├── app/orchestration/     # graph.py (control flow), state.py (shared state)
├── app/adapters/          # zetaris.py, meterless.py, sample_data.py (each: timeout, retry, logged fallback)
├── app/config.py          # env validation
├── app/schemas.py         # request and response models
├── app/tracing.py         # JSONL trace writer
├── semantic_layer/        # [TEAM] Zetaris DDL and binding SQL
├── data/sample/  data/README.md   # small samples; source, licence, subset, count, regeneration, limits
├── scripts/               # helpers; optional download script
├── run.py                 # entry point (CLI and FastAPI)
├── requirements.txt  Dockerfile  .env.example  .gitignore
├── input_examples/        # 3+ inputs that vary the task type (for example explain, predict, evaluate)
├── output_examples/       # real outputs saved after runs; documentation only, never loaded at runtime
├── logs/                  # trace-<id>.jsonl
├── README.md
└── docs/                  # [TEAM] ARCHITECTURE.md, SPONSOR_TECH.md, CURSOR_LOG.md, PREEXISTING.md, WORKING_AGREEMENT.md
```

**README sections** [ORG strong example]:
- a header with the track, sponsor technology and run command
- the problem and user
- the architecture diagram
- an agents table with a "Can block or retry?" column
- "What makes this an agent system"
- setup and usage
- sample mode
- a failure-handling table
- AI and model usage
- data sources
- third-party licences
- pre-existing components (even when the answer is "None")
- limitations
- `## Demo Video`
- a `## Track` block

## 13. Vibe coding in Cursor [ORG `vibe-coding-starter-guide.md`]

- **Stance.** Vibe coding is "allowed and encouraged, and generated code is expected", but you must ship "a real working system that you can explain". It is covered in the Build Day workshop.
- **Setup:**
  - Activate the Cursor credit from the "Space XAI and Cursor" folder in HackOS Resources.
  - [SETUP] The supplied setup guide has no redemption instructions yet; its Cursor credit, Meterless prompt library and workshop details are organiser placeholders. The prompt library is optional.
  - Use Composer for fast everyday coding and Grok for harder, longer tasks.
  - Smoke-test that the Agent can edit files and use the terminal.
  - **Keep the product's model key out of Cursor settings.**
- **Loop:** Describe, Generate, Inspect, Run, Log, Test, Refine, Document. "Do not accept generated code blindly." "Do not ask for the entire final app at once."
- **Build order:** entry point, model call, Zetaris and Meterless, agents, logs, Docker, README, then an optional UI. One feature at a time.
- **Prompts:**
  - State the track, user, named agents and constraints, and end with "Generate the smallest working implementation first".
  - Avoid "Build a hackathon-winning agent app" ("encourages fake complexity").
  - Debug prompts should say: do not remove the Zetaris or Meterless integration, and do not replace a real call with a hardcoded response.
- **Review every generation.** Does `run.py` start? Are the model calls real? Does the Zetaris adapter really call Zetaris? Is Meterless real, not a stub? Are outputs generated from the input? Are logs written? Is there a feedback loop?
- **Honesty checks:**
  - Run `grep -R "return {" app/ run.py` and `grep -R "output_examples" app/ run.py`.
  - Run two unrelated queries and compare the outputs.
  - Have Cursor audit for fake functionality and return a table of file, line, risk and fix.
  - Audit the README and deck against the code, because AI "may invent features".
- **Generated tests should check:** different inputs give different outputs; logs show 3+ agents and a critique event; Zetaris is really called in normal mode; there are no keys; `output_examples/` is never loaded.
- **Output examples** come from real runs, for example `curl ... -d @input_examples/example_1.json > output_examples/example_1.json`.

## 14. Team process [ORG team rules]

- **Primary contact and backup.** This is an admin role, not ownership. The contact creates the team, keeps the roster, confirms the track, and submits the form.
- **Working agreement**, ideally before 22 Oct and at the latest on Day 1. It should cover:
  - **the prize split** (fill this in first)
  - roles, ownership, hours and time zones
  - what happens if someone goes quiet for 24 hours or joins late
  - who confirms the split
  - the technical direction
  - the daily check-in and time-zone handover
  - the channel and code review
  - who owns the demo and deck
  - how decisions are made
- **Settle the roster before 22 Oct.** Merges are impossible once either team has **created** a submission, and the cap stays at five.
- **The roster must match** across HackOS, repo contributors, README credits and demo credits.
- **The project must not depend on one person's keys or machine.**
- **Organisers do not settle contribution disputes.** Removing someone late to avoid sharing a prize is a conduct issue.
- **Students:** universities can request a cohort code by emailing hackathons@genai.works [RULES FAQ].

## 15. Sponsor technology primer

**Access** [ORG]:
- Each sponsor's HackOS Resources folder has access steps and any credits.
- Ask in Help Zetaris, Help Meterless, Help Cursor or Help NVIDIA.
- General questions go to #help desk.
- You pay for any paid API you choose, unless sponsor credits cover it.

### 15.1 Zetaris AI Data Harness [CALL unless marked]

- **What it is.** A federated SQL query engine with a GUI design studio, built on "zero copy": data stays where it lives, and agents get governed, permissioned context. Data Day focus: "serving internal data" [ORG].
- **Programming.** ANSI SQL plus extensions to attach REST APIs, Postgres over JDBC, Kafka and PDF content. Salesforce and Workday also come up.
- **Unified Semantic Layer (USL).**
  1. Define it in DDL.
  2. Bind it to sources with SQL.
  3. Query it like one table.

  Use it for "consistent, trusted answers". A coding agent such as Cursor can build it.
- **Access.** JDBC or REST; the organiser code uses REST (section 11). The agent loop runs separately and calls the USL.
- **Efficiency claim.** In Michael's hobby pipeline, about 100 lines of networking code are not needed with Zetaris. Data-quality code ("about 500 lines per data product" in the raw transcript; "hundreds of lines" in the edited one) becomes "one line of SQL" for an equivalent rule.
- **Deployment and access.** The call described free-forever distributions, but [LIVE17] requires a Zetaris licence or evaluation entitlement and distinguishes the platform from the Apache-licensed recipes. Confirm the team's actual entitlement; do not promise indefinite free platform use.
  - **AWS:** the call discussed approximately 4 vCPU, 8 GB and possible onboarding credits. The current vendor guide gives a different instance example. Treat call sizing and promotional details as historical; verify the selected deployment's current resources and cost before provisioning.
  - **Local Docker:** the setup guide allocates 4 CPUs, 8 GB RAM and at least 15 GB disk. Local hosting avoids an AWS infrastructure bill, but does not establish an unlimited platform licence. Windows uses WSL 2 integration; Apple Silicon setup may require Rosetta.
- **Install.** Use the more detailed [SETUP] sequence in section 15.6: configure the administrator before the first start, then run preflight, pull/start, verification and the first queries. The earlier call's brief installation outline omitted these intermediate steps.
- **Resources.** The Getting Started repo (Apache licensed; README, Start Here, connection guides for Cursor, Codex, Claude Code and SQL IDEs; worked examples), three YouTube videos, a blog post, and the HackOS Zetaris folder.
- **Support.** The Zetaris team will be in the HackOS channel around the clock during the build; a built-in help agent is explained at kickoff.
- **Contact.** Michael is on LinkedIn and X as "MiH42" (raw transcript) or "MI42" (edited transcript); unverified.

### 15.2 Meterless (required)

- **[ORG]** Build Day ("Meterless engines: build faster") and Power Day ("local and cloud provider").
- **[VENDOR] Nightshift.** One OpenAI-compatible base URL and key for local and cloud models (about 193 models).
- **Editions:** a free web edition; a Mac edition needing M5 or later; DGX Spark coming.
- **[ORG]** The strong example uses Meterless as the Nemotron runtime, while the vibe guide also mentions a separate adapter, a library and prompt files.
- **[SETUP]** Separates three offerings: an optional prompt library for building in Cursor; a provider route for running Nemotron on Meterless credit; and an optional AI hotspot. The guide supplies neither the hotspot setup nor the event provider details.
- **[UNKNOWN]** The Meterless sign-up/credit link, provider base URL and confirmation of OpenAI-format requests remain placeholders. Product claims about Nightshift above do not verify the event endpoint.
- **Eligibility conflict.** The earlier rules require meaningful Meterless integration; [SETUP] offers direct NVIDIA inference and says the prompt library is optional, while its introduction still requires Meterless locally. Do not assume a prompt file or unused installation satisfies the runtime integration requirement. Ask Help Meterless or the organisers what role is required when using direct NVIDIA inference.

### 15.3 Cursor (with SpaceX AI)

- The required development environment, with credit in the HackOS "Space XAI and Cursor" folder.
- [SETUP] Distinguishes development credit from runtime credit: use Cursor's included coding models for development and the selected Nemotron provider for product runs and tests. Keep the product provider key out of Cursor's model settings. The guide names Composer and Grok; actual access depends on the participant's account.
- **[TEAM]** Keep `docs/CURSOR_LOG.md` for the write-up and the Cursor-built product award.

### 15.4 NVIDIA

- [RULES, ORG] Use it where it contributes, through hosted or cloud access (Power Day: "cloud provider"). [SETUP] instead states Nemotron is mandatory; this difference is unresolved.
- **Best use of NVIDIA Nemotron** wins a DGX Spark.
- The strong example reaches Nemotron through Meterless.
- [SETUP] Supplies two inference routes: Meterless credit or NVIDIA's rate-limited API for prototyping. For the direct route, participants create their own account and key at `build.nvidia.com`; the guide says NVIDIA is not issuing event keys. Account limits and available models still need checking.
- [SETUP] Describes Super for general agent reasoning/tool use, Nano for efficient helper calls and Ultra for deeper reasoning. These are the guide's selection categories, not a verified list of models available to our account. It gives `nvidia/nemotron-3-super-120b-a12b` as a point-in-time example; copy the current ID from the selected provider before use.
- **Switching routes** changes `MODEL_BASE_URL`, `MODEL_API_KEY` and `NEMOTRON_MODEL` together. A successful direct NVIDIA call does not resolve the Meterless eligibility question.

### 15.5 SpaceX AI

- A sponsor partnered with Cursor; its partnerships head is a judge.
- Using SpaceX AI products beyond Cursor is optional.

### 15.6 Practical installation sequence [SETUP]

The supplied guide organises preparation into **Data** (Zetaris), **Build** (Cursor and an optional Meterless prompt library) and **Power** (Nemotron via the selected provider). Its detailed commands are in the [Participant Setup Guide](<../02_Source_material/Organiser_guides/Open Agent Hackathon 2026 Participant Setup Guide 121026.md>), sections 1.1 to 1.9. The sequence below is preparation guidance, not a record of completed installation.

1. **Prepare Windows and Docker.** Run the Zetaris shell commands in WSL 2 with Docker Desktop's WSL integration enabled. The guide allocates 8 GB RAM and 4 CPUs to Docker, plus at least 15 GB free disk; its preflight threshold is 6 GB RAM. It estimates 30–45 minutes for the first download/start. Confirm the Docker engine and Compose are available before continuing.
2. **Get the platform bundle and registry access.** Obtain `zetaris-platform.zip` and credentials through the Zetaris/organiser access route, unpack it, sign in to the supplied registry and run `./preflight.sh`. The guide names `zetarishackathon.azurecr.io`; use the actual organiser-issued registry command if it differs.
3. **Configure the platform before first startup.** Set `ZETARIS_ADMIN_EMAIL`, `ZETARIS_ADMIN_PASSWORD` and `ZETARIS_ADMIN_ORG` in the platform's own `.env`. The guide specifies a minimum eight-character password with upper/lowercase letters, a digit and an allowed symbol (`$ @ ! % * ? &`). Its laptop settings include `ZSPARK_DRIVER_MEM=2g`, `ZSPARK_DRIVER_CORES=2`, `ZSPARK_MASTER_URL=local[2]`, `ZETARIS_API_MAX_HEAP=1g`, `UI_PORT=3000`, an empty `COMPOSE_PROFILES` and `ZETARIS_SEED_TPCH=true`. Keep supplied settings unless the installation instructions require a change. Editing these later does not reset an existing administrator account.
4. **Validate and start.** From the platform folder, protect `.env`, run `docker compose config --quiet`, pull the images and start them with `docker compose up -d`. The guide expects `postgres`, `driver`, `api`, `ui` and `ai-datasteward` running, with the one-time `init` and `bootstrap` jobs at `Exited (0)`. Run `./verify.sh`; the guide expects nine passing checks.
5. **Prove data access.** Sign into the GUI and run `SELECT 1 AS one;`. Then follow the Getting Started PokéAPI recipe, one complete SQL statement at a time, to create its database, schemastore container, REST table and abilities view. The guide expects Pikachu's two ability rows; check the source if results differ. Its recipe-readiness note marks PUDL as failing at the time of writing.
6. **Connect the application.** Create the user API key in the Zetaris UI and save it privately in the application's `.env`. This is separate from the platform `.env`; the Getting Started helpers use `.env.local`. Use the REST contract in section 11. The guide supplies organisation ID `1` for a local install; use the value for the actual instance.
7. **Set up Build and Power.** Confirm Cursor can create and run a small file using its own coding credit. Choose a Nemotron route and save the matching provider address, key and exact model ID. Meterless credit/access and Cursor redemption details still need the organiser links.

**Storage and lifecycle.** Source files must be reachable by the Zetaris server, for example through supported storage or an appropriately configured mount; a path on the host laptop is not automatically available inside its containers. The guide suggests S3 for uploaded files. `docker compose stop` / `start` preserves the existing deployment. Its `down -v` reset removes volumes, including data and encryption keys; it is not the normal stop command.

**Deployment conflict.** The setup guide says everyone runs Zetaris locally and its introduction requires both Zetaris and Meterless on the participant's machine. It also mentions an AWS alternative, and the earlier call discusses both deployment routes. Confirm whether local installation is an eligibility requirement or simply the workshop's setup path. Judge access to the submitted service remains a separate question.

### 15.7 Readiness checks [SETUP, TEAM]

The guide requests these checks at least two days before kickoff:

| Check | Evidence to retain | Current workspace status |
|---|---|---|
| Data | Nine passing `verify.sh` checks, the GUI `SELECT 1` result and the PokéAPI query result | Not established |
| Build | Cursor creates and runs a small Python file using its coding credit | Not established |
| Data and Power | A reachable Zetaris GUI, a successful REST `SELECT 1` and a reply from the chosen Nemotron provider | Not established |

The supplied `smoke_test.py` checks these three connections independently. It does **not** demonstrate Nemotron choosing a tool, using Zetaris results, agent collaboration or meaningful Meterless integration. A true product run still needs the feedback loop and traces described in sections 8 and 11.

[TEAM] Before turning the Markdown example into an executable check, restore its escaped underscores and formatting, validate configuration without printing secrets, set a bounded model timeout, and return a non-zero process status when a check fails. The guide's example prints PASS/FAIL but does not explicitly set a failure exit status. Do not treat its sample code or expected results as a completed run.

## 16. Test it like a judge [ORG], on 25 Oct

```bash
git clone <repo-url> final-check && cd final-check
ls run.py README.md .env.example input_examples/ output_examples/
docker build -t oah-submission .
cp .env.example .env    # fill in keys
docker run --rm -p 8000:8000 --env-file .env oah-submission
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json   # then examples 2 and 3
ls logs/ && cat logs/* | head -50
grep -RIn --exclude-dir=.git -E "(sk-|nvapi-|api[_-]?key|secret|token|password)" .
git ls-files | grep -E "(\.env$|\.pem$|\.key$|credentials|secrets)"
rm .env && docker run --rm -p 8000:8000 -e SAMPLE_MODE=true oah-submission   # then curl again: how a judge without keys sees it
```

**Then check:**
- outputs differ across inputs
- a new, unseen input works
- the README can be followed cold
- every claim is real
- the repo and video links open while logged out
- examples and traces match our track

**Submit only when** all checks pass, with **hours to spare, not minutes**.

## 17. Support and conduct [ORG]

| Need | Go to |
|---|---|
| Track scope | HackOS challenge pages |
| Sponsor setup | The sponsor's Resources folder, then its Help channel |
| Technical or submission questions | #help desk |
| Design and debugging | Mentor office hours (mentors unblock; they do not build) |
| Rules, roster after the lock, anything sensitive | hackathons@genai.works (one working day) |
| Official updates and schedule changes | HackOS Announcements and Discord (event page) |

- **During judging** (28 Oct to 6 Nov), monitor Announcements and be ready to answer judges' questions or verification requests.
- **Asking well:** give the goal, expected and actual behaviour, the error, the stack, whether it fails locally or in Docker, and sanitised logs. Never post keys.
- **Conduct:**
  - Be respectful across time zones and languages.
  - Critique work, not people.
  - Do not cross-post.
  - If a key leaks, delete it, tell a moderator and rotate it.
  - Do not record people without consent.
  - No offensive-security testing.
  - Credit others accurately.
  - Report concerns privately.

## 18. Build plan and Day 1

**Build rhythm** [ORG, with TEAM details]:

| UTC day | Focus |
|---|---|
| 22 Oct | Confirm the track, user and output; connect Zetaris and Meterless; a basic agent loop; log from day one |
| 23 Oct | A minimal working loop end to end |
| 23 to 24 Oct | Critique, retries, branching, shared memory, traces. Self-check at 24 Oct, 16:00 UTC |
| 25 Oct | Data, tools, retrieval, failures and fallbacks; **the full judge-style test** |
| 26 Oct | Freeze features; generate real output examples; README; deck; record the video |
| 27 Oct | Final checks (12:00 UTC is 23:00 Sydney); declare pre-existing work; submit early |

**Before Day 1 (by Wed 21 Oct; [SETUP] asks for connection checks at least two days before kickoff):**
- [ ] Everyone registered, with one account each, on our HackOS team.
- [ ] Contact and backup chosen; working agreement written, with the prize split.
- [ ] Public repo planned, with all members added.
- [ ] Data Day recording watched; Build Day and Power Day attended or watched; onboarding attended (Wed 21 Oct, 23:00 Sydney) or the recording watched.
- [ ] Zetaris installation path confirmed; on Windows, WSL 2 and Docker integration ready, with the resources in section 15.6.
- [ ] Zetaris preflight and all nine verification checks pass; GUI `SELECT 1`, the PokéAPI example and REST SQL tested.
- [ ] **Meterless access and required product role confirmed**, including the event endpoint and whether direct NVIDIA inference changes any integration obligation.
- [ ] Nemotron provider address, API key and exact model ID obtained from the same route; a real response received. Resolve the guide's mandatory-Nemotron wording with the organisers.
- [ ] Cursor installed by everyone, with credit activated; model keys kept out of Cursor.
- [ ] Platform and application secrets kept in separate private environment files; the supplied Data/Power smoke test adapted and run with results retained.
- [ ] Optional Meterless prompt library and workshop joining details obtained if using them; their links are not populated in the supplied setup guide.
- [ ] Track shortlist; APPROACH self-score done. Anything prepared now gets declared.

**Day 1 (Thu 22 Oct, Sydney):**

| Time | Activity |
|---|---|
| 11:00 | **First 30 minutes [ORG]:** HackOS Announcements and Resources; confirm the track and team; find the help channels and mentor schedule; read the sponsor folders; create the repo with `.gitignore` and `.env.example`; set up Cursor; define the agents and feedback loop; write the first test input |
| 11:30 | Paste the HackOS challenge page into an LLM loaded with this context pack; fill in the APPROACH worksheet; finalise the working agreement |
| 12:30 | Architecture (section 8), demo storyline, roles |
| 13:30 | Scaffold (section 12): `run.py`, config validation, adapters with sample fallback, JSONL tracing, Dockerfile. Verify Zetaris REST and the chosen Nemotron provider route; confirm and demonstrate Meterless's required role. Separate calls are connectivity checks, not proof of meaningful integration |
| 15:30 | First USL over 2+ sources; the Planner, Executor and Evaluator loop answers one real question with a trace |
| 18:00 | Check-in; blockers go to #help desk or the Help channels |

- **Plan for the earlier registration cutoff: Fri 23 Oct at 10:45 Sydney [ORG].** The event page gives 10:59; the discrepancy remains unresolved (section 20).
- **Do not create the submission entry until the roster is final.**
- **Day 1 is done when:**
  - one logged end-to-end run works
  - sample mode is stubbed
  - `docker build` works
  - the README skeleton, `.env.example`, `data/README.md` and `docs/PREEXISTING.md` exist
  - the demo storyline is written

**Roles** [ORG]:
- agent orchestration
- data pipeline and sponsor integration
- domain logic
- evaluation and testing
- demo, deck and docs

## 19. Open questions

| Question | Where to check |
|---|---|
| Full challenge statements | HackOS challenge pages; onboarding or kickoff |
| "Additional challenges and prizes" | Onboarding, 21 Oct |
| Build Day and Power Day dates | Announcements, GenAI Academy, Discord |
| Whether the setup guide's mandatory Nemotron and local-install wording supersedes the earlier rules | Organisers / #help desk, current Official Rules and HackOS challenge pages |
| Meterless sign-up/credit link, event base URL, OpenAI-format support, and required product role if inference uses NVIDIA directly | HackOS Meterless folder, Help Meterless; [SETUP] still has placeholders |
| Exact Nemotron models and account limits; Meterless credits if using that route | Selected provider's account/model list, HackOS NVIDIA/Meterless folders and Help channels. The direct NVIDIA self-service key route is now documented in [SETUP] |
| Cursor credit redemption, Meterless prompt library link, workshop date/time/link, AI hotspot details and help-channel link | HackOS sponsor folders and Announcements; these are explicit [SETUP] placeholders |
| Whether judges can reach the Zetaris instance and how the deployment is reproduced | HackOS Zetaris folder and Help Zetaris. [SETUP] now supplies local JDBC details and the local REST reference address; actual connections remain untested |
| How agents reason in sample mode with no keys | #help desk, mentor office hours |
| Submission form limits (field lengths, file sizes, video host, prize-split field) | The live HackOS form |

## 20. Conflicts between sources, and how they are resolved

| Item | What differs | Resolution |
|---|---|---|
| Data Day date | Organiser calendar gives 12 Oct UTC without a time; raw recording metadata gives 13 Oct at 16:27 Sydney | Do not infer a Sydney event date or label 12 Oct as a US date. The one-page summary identifies the recording without a date conversion |
| Nemotron requirement | Earlier [RULES]/[ORG]: any model is allowed and use NVIDIA where it contributes. [SETUP]: the product must run on Nemotron | Unresolved. Keep the source distinction and confirm whether this is an updated eligibility rule before selecting the runtime |
| Meterless role and direct NVIDIA | Earlier rules require meaningful Zetaris and Meterless integration. [SETUP] allows direct NVIDIA inference, makes the Meterless prompt library optional, yet requires Meterless locally in its introduction | Unresolved. A direct NVIDIA test is technically described, but is not evidence that Meterless may be omitted. Confirm the required role; do not count an unused install or prompt file as runtime integration |
| Local deployment | [SETUP] says everyone runs Zetaris locally and both sponsor tools must run on the participant's machine, but also mentions AWS; [CALL] offers local Docker or AWS | Unresolved eligibility wording. Local Docker is the detailed workshop path; confirm whether hosted alternatives qualify and how judges obtain access |
| Provider model variable | Earlier code uses `MODEL_NAME`; [SETUP] uses `NEMOTRON_MODEL` | Use the latter for the setup test, or map it explicitly in an older adapter; keep model, key and base URL aligned |
| Setup guide completeness | Detailed commands coexist with missing credit, endpoint, library, hotspot, workshop and help-channel links | Import the supplied details, retain placeholders as open questions and verify account-specific values before executing |
| Zetaris free-forever claim | The call describes free-forever distributions; the vendor installation guide checked 17 Oct requires a licence/evaluation entitlement | Keep the call as historical testimony, but confirm actual entitlement before making a cost or duration promise. The recipes' Apache licence does not cover the platform images |
| Build duration | Event marketing says 144 hours; published start and close are 22 Oct 00:00 and 27 Oct 23:45 UTC | Use six days in summaries, and the exact timestamps for scheduling; the interval is 143 hours 45 minutes |
| Tie-break direction | Saved rules say Impact, then submission timestamp, without stating which timestamp wins | Retain the rule's wording; do not assert an earlier-entry advantage |
| Registration close | Event page, also checked 17 Oct: 22 Oct, 23:59 UTC. Organiser guides: **23:45 UTC** | Plan for 23:45 UTC (23 Oct 10:45 Sydney), and label it the earlier guide cutoff. The website gives 10:59 Sydney |
| Judging opens | Event page, also checked 17 Oct: 27 Oct, 00:00 UTC. Guides: 28 Oct, straight after close | Unresolved schedule conflict. Submission deadline is unchanged; do not present 28 Oct as an uncontested official date |
| Prizes | Guides and draft rules: $15,000 cash and $5,000 in-kind. Event page on 15 Oct: **$13,000 and $7,000**, with named awards | Use the event page; watch onboarding |
| Public repo | Event page: "GitHub repository". Guides and form preview: **public** | Treat public as required |
| `official-rules.md` | A working draft | The event page is binding |
| Kickoff | The call: "Kickoff is the 22nd", with challenges revealed then. Guides call 21 Oct onboarding the "official participant kick-off" | Attend onboarding on 21 Oct (12:00 UTC); expect challenge statements by 22 Oct |
| Discord | Guides: HackOS runs operations, Discord is community space. Event page: kickoff, office hours, judging and results happen "in Discord and on the platform"; schedule changes are announced there; joining is optional | Watch both |
| Workshop dates | The call: 15, 19 and 20 Oct. Guides: "to be confirmed" | Check Announcements |
| Demo timings | The guide's segment table sums to more than its 3:30 structure | Use the storyboard in section 10.3 |
| Field names | Technical guide: `run_id`. Vibe and strong guides: `request_id` and `trace_id` | "No mandated structure"; carry both IDs |
| Michael's handle | "MiH42" (raw) versus "MI42" (edited) | Unverified |
| Third-party guides | Some show a 15 to 20 Oct build | Ignore them |

## 21. Glossary

- **HackOS:** the hackathon platform for Announcements, challenge pages, Resources, help channels, team-finding, the submission form and the results call.
- **Zetaris AI Data Harness:** a federated SQL engine with a GUI that queries data in place for agents.
- **Unified Semantic Layer (USL):** a named model of tables and relationships (DDL), bound to sources with SQL, and queried as one table.
- **Meterless / Nightshift:** a required sponsor tool serving local and cloud models through an OpenAI-compatible endpoint.
- **Data Day, Build Day, Power Day:** the sponsor workshops, recorded on HackOS.
- **Wildcard [Tinkerer]:** one of the four track choices, for existing projects; only new work is scored.
- **APPROACH:** the organiser's scoping method (section 9).
- **`SAMPLE_MODE`:** runs on cached sample data with no live credentials, using real agent logic and honest labels.
- **Trace:** a JSONL log of agent actions, handoffs, critiques, retries and sponsor calls for one run.
- **Removal, collaboration and hardcoding tests:** the organisers' three self-tests (section 8.1).

## 22. Project status and handover as of 19 Oct 2026

**Scope of this status:** the local reference materials and folder organisation are recorded below. Event sources were last reviewed on 17 Oct. Team decisions and product progress after that review have not been supplied; obtain the latest checkpoint before assigning work.

**Sharing and onboarding update, 19 Oct:** the current one-page PDF, detailed guide PDF and this single master Markdown pack are grouped in `01_Share_with_colleagues`. Section 0 now provides a model-neutral starting workflow, proposed work areas and a portable team checkpoint. These additions are team guidance, not new organiser requirements. The prior context version is retained in `90_Archive/Context_versions`.

**Completed materials visible in this workspace:**
- The onboarding/Data Day recording, raw transcript, edited Zetaris transcript and highlights.
- The 18 organiser guides, saved official-rules extract and this consolidated context pack.
- Onboarding summary decks and figures through v3; participant guide decks and PDFs through v11; one-page summaries through v7; the associated presentation-generation scripts and assets.
- The additional Participant Setup Guide, now incorporated into this pack's sponsor guidance, configuration, readiness checklist and conflict register.

**Planning already captured:** four track options, judging criteria, the APPROACH scoping method, example agent architectures, a proposed repository layout, a six-day build rhythm, and submission/demo checks. These are plans and examples, not an implemented hackathon entry.

**Still to establish:** the team's selected use case and track, roster and responsibilities, sponsor account access, actual installation/test results, and a working end-to-end product. The files reviewed do not establish that these are complete. The `Build_Scripts` folders generate presentation materials; their presence is not evidence that the product has been built.

**Next decisions:** resolve the setup guide's three eligibility conflicts; confirm a narrow user/problem/data combination; then record the Data, Build and Power checks from section 15.7. Declare any product code or prepared data created before the build window under the pre-existing-work rules.

**Presentation currency:** the 36-slide v11 guide and matching PDF in `01_Share_with_colleagues/` (PDF `02_Detailed_guide_v11.pdf`; PowerPoint `Editable_slides/Detailed_guide_v11.pptx`) incorporate the Participant Setup Guide and the 17 Oct source review. They retain the v10 design, add setup connections, coding/runtime credit, provider routes and readiness checks, and flag unresolved eligibility and schedule conflicts. The separate v8 one-page summary in `01_Share_with_colleagues/` (PDF `01_Quick_overview_v8.pdf`; PowerPoint and PNG in its subfolders) is also updated, with editable PowerPoint, PDF and PNG versions. It retains the four-column structure and now follows the detailed guide's Poppins/Aptos typography, amber and black palette, and square section labels. It retains the corrections to setup order, the six-day description, schedule qualifications and tie-break wording; it distinguishes coding/inference credit and flags model, integration and hosting questions. Source references and qualifications are recorded in the PowerPoint notes. Every slide was rendered and visually reviewed; both PowerPoints passed package, font and layout checks, and their PDFs were rendered and checked. These are document checks, not evidence of a working product or completed sponsor setup. The v7 accuracy audit also removes the unsupported Data Day timezone conversion, distinguishes recommended samples and no-key mode from requirements, identifies track values as total pools, and anchors cash payment to the results announcement. The v10 guide and v5/v6 one-page summaries remain historical exports.

**Quick-guide update, 19 Oct:** v8 replaces v7 in the sharing folder, including the PDF, editable PowerPoint and chat image. The prior v7 files are archived. All ten live official-rule sections and visible dates, prizes and scoring were rechecked on 19 Oct for this quick-guide update; its source disagreements remain labelled. Sydney time conversions and prize/scoring arithmetic were verified. This targeted review does not re-date the full detailed guide or every source in this context pack.
