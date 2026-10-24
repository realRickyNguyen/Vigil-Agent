# Submission Requirements

**OPEN AGENT HACKATHON 2026 | Build an agent that does real work**

Everything you need to submit, how to submit it, and what judges will check. All times are in **UTC**.

> Where this document and the Official Rules on the event page disagree, the Official Rules apply.

---

## 1. Key Facts

| Item | Detail |
|---|---|
| **Where to submit** | HackOS |
| **Build window** | 22 October, 00:00 UTC to 27 October 2026, 23:45 UTC |
| **Submissions close** | **27 October 2026, 23:45 UTC** (hard deadline) |
| **Judging opens** | 28 October 2026, immediately after submissions close |
| **Results announced** | 6 November 2026, 16:00 UTC |
| **Tracks** | Select exactly one primary track per submission |
| **Team lock** | Team composition locks when your first submission is created |

The deadline is final. Time zones do not extend it, and nothing can be added or fixed after it.

---

## 2. What You Must Submit

Every submission includes the following four components.

| Component | Requirement |
|---|---|
| **Demo video** | 1–4 minutes, showing the main workflow, how the agent solves the selected challenge, its key features, and how Zetaris and Meterless are integrated |
| **Slide deck** | The problem and target users, the solution, the agent workflow or architecture, the technical stack, how Zetaris and Meterless were used, what was unique about your use of the sponsor technologies, product visuals, and future enhancements |
| **GitHub repository** | A public repository with all source code and a README covering setup, usage and dependencies. If your agents run in Google Colab, include the Colab links |
| **Sponsor technology explanation** | How Zetaris was integrated; which Meterless Engine(s) you implemented, what each does and the test showing it works; how your app connects to Meterless Nightshift; where NVIDIA technology contributes; and what was unique about your use of the sponsor technologies |

You will also confirm your project name, description, team members and selected track in the submission form, and declare any pre-existing components.

---

## 3. Component Guidance

### 3.1 Demo Video (1–4 minutes)

The demo is worth 15 points. Show the agent working, not slides about it.

**Cover:**

- The problem and who it is for
- The main workflow, run live or recorded from a real run
- How the agent solves the selected challenge
- Its key features
- How Zetaris and Meterless are integrated: your agent querying Zetaris, the feature your Meterless Engine powers, and one real request passing through Nightshift and returning a result

**Avoid:**

- Going over 4 minutes
- Showing API keys, tokens, credentials or personal data on screen
- A demo path that only works once or is hardcoded

### 3.2 Slide Deck

The deck explains what the demo cannot. Include:

1. The problem and target users
2. The solution
3. The agent workflow or architecture
4. The technical stack
5. How Zetaris and Meterless were used
6. What was unique about your use of the sponsor technologies
7. Product visuals
8. Future enhancements

### 3.3 GitHub Repository

The repository must be **public** so judges can open it without requesting access.

Your README should cover:

- **Setup:** how to install and run the project from a clean clone
- **Usage:** how to run the agent, with sample inputs
- **Dependencies:** what the project needs, including Zetaris and Meterless Nightshift
- **Colab links**, if your agents run in Google Colab

Recommended:

- At least three sample inputs and their outputs
- Logs or traces showing how the agent reached its output, including which model handled each request
- The test or conformance check showing your Meterless Engine works
- A `.env.example` with placeholder values only
- A `SAMPLE_MODE=true` fallback so the project runs if Zetaris, Nightshift or another service is unavailable

**Never commit API keys or credentials.** Keep secrets in a local `.env` file and add it to `.gitignore`. Your NVIDIA API key belongs in Nightshift's Providers tab, not in your project.

### 3.4 Sponsor Technology Explanation

Sponsor Tech is worth 10 points. Explain clearly:

| Sponsor | What to Explain |
|---|---|
| **Zetaris** | How it is integrated and what role it plays as your agent's data layer |
| **Meterless** | Which Meterless Engine(s) you implemented, what each does in your project, the feature it powers and the test result; and how your app uses Meterless Nightshift as its AI provider |
| **NVIDIA** | Where NVIDIA technology contributes to your project, workflow or use case, including any Nemotron model you used through Nightshift |
| **Cursor (with Space XAI)** | Optional: if you built with Cursor, how you used it |

Finish with what was unique about your use of the sponsor technologies.

---

## 4. Sponsor Technology Requirements

| Sponsor | Requirement |
|---|---|
| **Zetaris** | Required: every submission must use Zetaris as its data layer |
| **Meterless** | Required: every submission must implement at least one Meterless Engine (H-MEM, Markovian, World Model or Scout Intent) in a working feature, and use Meterless Nightshift as its primary AI provider |
| **Cursor (with Space XAI)** | Optional: recommended AI coding tool. You can build with any coding tool |
| **NVIDIA** | Integrate wherever it contributes to your project, workflow or use case. Connect NVIDIA models through Nightshift |

These requirements apply to every track, including Wildcard [Tinkerer].

Mentioning a sponsor technology, copying a prompt or adding an unused dependency does not meet these requirements. The integration must work in your submitted project.

**NVIDIA award:** to compete for the NVIDIA DGX Spark, use at least one NVIDIA Nemotron model through Meterless Nightshift in a working feature, and show which model handled the request.

Setup steps for each sponsor technology are in the Participant Setup Guide in the Resource Center on HackOS.

---

## 5. Pre-Existing Work

- Work committed before the build window opens (22 October, 00:00 UTC) is not eligible, except for clearly declared pre-existing components.
- Pre-existing open-source libraries are fine.
- Pre-existing product code must be declared in the submission form.
- Data prepared before the build window must be declared as a pre-existing component.
- **Wildcard [Tinkerer]** is designed for existing projects and is scored on the new work built during the hackathon. Make the before and after clear in your demo and slide deck.

Generated code is allowed and expected. You own the result and are accountable for it.

---

## 6. Teams and Your Submission

| Rule | Detail |
|---|---|
| **Team size** | 1–5 builders; solo entries compete in the same pool as teams |
| **Solo builders** | You still need to create a team on HackOS, with just yourself in it, to submit |
| **One team** | A participant may belong to exactly one team and appear on one submission |
| **Team lock** | Team composition locks when your first submission is created. Confirm your roster before you create it |
| **Track** | Select exactly one primary track. You can change it any time before the submission deadline from your team workspace |
| **Updates** | You can update your submission up to the deadline |

---

## 7. How Submissions Are Judged

Each submission is reviewed by at least three judges against the published criteria. Wildcard [Tinkerer] is scored on the new work rather than prior development.

| Criterion | Points | What Judges Look For |
|---|---:|---|
| Impact | 30 | Consistency with the challenge statements: how effectively the solution addresses a meaningful real-world problem for its intended users |
| Technical | 20 | How well the solution is built, including its technical implementation, reliability and architecture |
| Innovation | 15 | How original or creative the approach to solving the problem is |
| Demo | 15 | How clearly the demo shows the solution, its functionality, and the value it provides to its intended users |
| Product & UX | 10 | How intuitive, accessible, and easy to use the product is for its intended users |
| Sponsor Tech | 10 | How effectively the solution uses the sponsors' technology to address the problem and enhance the overall product |
| **Total** | **100** | |

Ties are resolved on the Impact score, then on submission timestamp.

A submission judges cannot run or open cannot be scored properly. Test a clean setup from scratch before you submit.

---

## 8. Final Submission Checklist

### Components

- [ ] Demo video (1–4 minutes) uploaded
- [ ] Slide deck complete, covering all eight points
- [ ] GitHub repository is public, with a README covering setup, usage and dependencies
- [ ] Colab links included, if your agents run in Google Colab
- [ ] Sponsor technology explanation covers Zetaris, Meterless and NVIDIA

### Requirements

- [ ] Zetaris integrated as the data layer
- [ ] At least one Meterless Engine working in a feature, with a passing test
- [ ] Meterless Nightshift is the app's primary AI provider
- [ ] One primary track selected
- [ ] Pre-existing components declared in the submission form
- [ ] Roster correct before the first submission was created

### Quality

- [ ] Project runs from a clean clone with no manual steps
- [ ] No API keys or credentials committed or shown on screen
- [ ] Sample inputs and outputs included
- [ ] Logs show how the agent reached its output

### Deadline

- [ ] Submitted on HackOS before **27 October 2026, 23:45 UTC**

---

## 9. Where to Get Help

| Need Help With | Go To |
|---|---|
| Setting up sponsor tools | Participant Setup Guide in the Resource Center on HackOS |
| Submission questions | #help desk channel on HackOS |
| Sponsor technology | That sponsor's Help channel on HackOS (Help Zetaris, Help Meterless, Help Cursor, Help NVIDIA) |
| Agent design and debugging | Mentor office hours |
| Rules questions | hackathons@genai.works (reply within one working day) |
| Official updates | Announcements on HackOS |

Submit early. Do not rely on last-minute fixes.