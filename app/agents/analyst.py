"""Analyst: picks the reactions that matter from the disproportionality screen, then classifies
them against the current label. Revises its findings when the Reviewer rejects them.

Kept small per call: Nightshift ends a provider call after about 45 s, and Nemotron Lightning
spends most of its budget on hidden reasoning when a call is large. So picking and classifying are
separate calls, easy reactions are settled by rules (app/agents/rules.py), the model sees only the
label sentences relevant to each reaction, and classify calls run in small parallel batches."""
import json
from concurrent.futures import ThreadPoolExecutor

from app.adapters.meterless import MeterlessError, MeterlessUnauthorized, NightshiftClient
from app.agents.rules import route
from app.data.label import excerpt_block, norm
from app.schemas import Finding, Signal

# Includes reasoning tokens. Ultra used 2,100 to 4,100 per classify call on 22 Oct; 4,000 truncated one reply.
MAX_TOKENS = 6000
MAX_PICKS = 10
BATCH = 3  # reactions per classify call

PICK_SYSTEM = f"""You are the Analyst in a drug-safety review team. You read a screen of FDA Adverse Event Reporting System (FAERS) statistics for one drug.

Choose up to {MAX_PICKS} reactions a drug-safety reviewer should look at. Prefer strong signals (high PRR backed by many reports) and anything that could be a safety problem, including reactions that may simply be the disease the drug treats, so they can be ruled out. Cover different body systems rather than many terms for the same thing. Skip administrative terms such as product use issues.

Use only reactions from the table, spelled exactly as in the table. Reply with only a JSON object:
{{"picked": [{{"reaction": str, "why": str}}]}}"""

CLASSIFY_SYSTEM = """You are the Analyst in a drug-safety review team. For one drug, you help a human drug-safety analyst decide which reported drug-reaction patterns deserve a closer look. FAERS statistics show reporting patterns, not that the drug causes anything.

Answer three separate questions for each listed reaction:

1. "context": what kind of term is it?
   - "non_clinical": about the product, its use, exposure or the report, not a clinical event.
   - "treated_condition": the condition the drug treats, a symptom, sign, measure or complication of it, or an outcome the drug is given to prevent.
   - "clinical_event": any other clinical event.
2. "label_coverage": does the current label describe this reaction as something the drug may cause or worsen?
   - "covered": the label uses the same event, a synonym, or a broader term that clearly contains it. Give "label_section" (the bracketed section name, e.g. boxed_warning) and "label_term" (1 to 4 words, spelled exactly as in the label).
   - "unclear": the label only has a related or narrower term (for example a specific lab abnormality for a vague lab term).
   - "not_found": nothing in the label text shown describes it.
   - "not_assessed": the term is non_clinical or the treated condition.
3. "review_priority":
   - "review_next": a clinical_event that is not_found or unclear in the label, with enough reports to be worth an analyst's time.
   - "insufficient_evidence": not covered, but the term is too vague or the numbers too thin to act on.
   - "lower_priority": covered by the label, the treated condition, or non_clinical.

Also give "reasoning" (one sentence: why this priority) and "next_check" (one concrete check an analyst could run next, for example a specific breakdown of the reports or a label section to compare).

Rules: use only the data in the message; never invent numbers, reactions or label text; copy "reaction", "a" and "prr" exactly from the table; "evidence" lists the query IDs you relied on; "summary" is at most two sentences.

Reply with only a JSON object:
{"findings": [{"reaction": str, "a": int, "prr": float, "context": str, "label_coverage": str, "review_priority": str, "label_section": str or null, "label_term": str or null, "reasoning": str, "next_check": str, "evidence": [str]}], "summary": str}"""


def screen_table(signals: list[Signal], limit: int) -> str:
    lines = ["reaction | a (reports with drug) | PRR | chi2"]
    lines += [f"{s.reaction} | {s.a} | {s.prr} | {s.chi2}" for s in signals[:limit]]
    return "\n".join(lines)


class Analyst:
    name = "analyst"

    def __init__(self, llm: NightshiftClient, model: str, parallel: int = 2):
        self.llm = llm
        self.model = model
        self.parallel = parallel

    def header(self, ctx: dict) -> str:
        return (f"Drug: {ctx['drug']}\n"
                f"FAERS reports mentioning the drug: {ctx['totals']['drug_reports']} of {ctx['totals']['all_reports']} "
                f"(openFDA data updated {ctx['totals']['data_last_updated']}; query {ctx['totals']['query_id']}).")

    def pick(self, ctx: dict) -> list[str]:
        fallback = [s.reaction for s in ctx["passing"][:MAX_PICKS]]
        try:
            picked = self._pick(ctx)
        except MeterlessUnauthorized:
            raise  # a bad Runtime token fails every call; stop the run instead of degrading
        except MeterlessError as e:
            self.llm.tracer.event(self.name, "degraded", step="pick", error=str(e)[:200],
                                  fallback="top reactions by chi2", reactions=fallback)
            return fallback
        if not picked and fallback:
            # An empty pick would end the run with an empty dossier, so fall back as for a failed call.
            self.llm.tracer.event(self.name, "degraded", step="pick", error="no reactions from the table were picked",
                                  fallback="top reactions by chi2", reactions=fallback)
            return fallback
        return picked

    def _pick(self, ctx: dict) -> list[str]:
        user = (f"{self.header(ctx)}\n\nDisproportionality screen (query {ctx['screen_qid']}). Rows pass the Evans "
                f"screen (PRR >= 2, chi2 >= 4, at least 3 reports), strongest evidence (chi2) first, top {ctx['screen_shown']} of "
                f"{ctx['screen_passing']}:\n{ctx['screen_table']}")
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": PICK_SYSTEM},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS)
        # Match names case- and space-insensitively, and keep the table's spelling.
        known = {norm(s.reaction): s.reaction for s in ctx["passing"]}
        replies = [p for p in out.get("picked", []) if isinstance(p, dict)]
        picked = [known[norm(str(p.get("reaction") or ""))] for p in replies
                  if norm(str(p.get("reaction") or "")) in known]
        self.llm.tracer.event(self.name, "picked", reactions=picked,
                              dropped=[p for p in replies if norm(str(p.get("reaction") or "")) not in known])
        return list(dict.fromkeys(picked))[:MAX_PICKS]

    def classify(self, ctx: dict, reactions: list[str], feedback: dict | None = None) -> tuple[list[Finding], str]:
        """Rules first, then the model in small parallel batches. Reactions the model could not classify
        after every fallback are added to ctx["unclassified"], not guessed."""
        rows = {s.reaction: s for s in ctx["passing"]}
        rejected = {r["reaction"] for r in (feedback or {}).get("rejected", [])}
        evidence = [ctx["screen_qid"]] + ([ctx["label_qid"]] if ctx["label_qid"] else [])
        routed, for_model = [], []
        for r in reactions:
            # A rejected rule finding goes to the model; the rule would only repeat itself.
            f = route(rows[r], ctx["label"], evidence) if r in rows and r not in rejected else None
            if f:
                routed.append(f)
                self.llm.tracer.event(self.name, "routed", reaction=r, classification=f.classification,
                                      reasoning=f.reasoning)
            else:
                for_model.append(r)

        batches = [for_model[i:i + BATCH] for i in range(0, len(for_model), BATCH)]
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            results = list(pool.map(lambda b: self._classify_with_fallback(ctx, b, feedback), batches))
        findings, summaries = list(routed), []
        for f, s, failed in results:
            findings += f
            summaries.append(s)
            ctx.setdefault("unclassified", []).extend(failed)
        return findings, " ".join(x for x in summaries if x)

    def _classify_with_fallback(self, ctx: dict, batch: list[str], feedback: dict | None):
        fb = None
        if feedback:
            fb = {"rejected": [r for r in feedback.get("rejected", []) if r["reaction"] in batch],
                  "missing": [m for m in feedback.get("missing", []) if m.get("reaction") in batch]}
            fb = fb if fb["rejected"] or fb["missing"] else None
        try:
            found, summary = self._classify_batch(ctx, batch, fb)
            failed = []
        except MeterlessUnauthorized:
            raise
        except MeterlessError as e:
            # Smaller calls succeed more often; a reaction that still fails is reported, not guessed.
            self.llm.tracer.event(self.name, "degraded", step="classify", batch=batch, error=str(e)[:200],
                                  fallback="one reaction per call")
            found, failed, summary = [], [], ""
            for r in batch:
                try:
                    found += self._classify_batch(ctx, [r], fb)[0]
                except MeterlessUnauthorized:
                    raise
                except MeterlessError as e2:
                    failed.append(r)
                    self.llm.tracer.event(self.name, "unclassified", reaction=r, error=str(e2)[:200])
        # A reaction the reply left out is reported as unclassified too, instead of disappearing.
        got = {f.reaction for f in found}
        for r in batch:
            if r not in got and r not in failed:
                failed.append(r)
                self.llm.tracer.event(self.name, "unclassified", reaction=r, error="the model's reply had no finding for it")
        return found, summary, failed

    def _classify_batch(self, ctx: dict, reactions: list[str], feedback: dict | None) -> tuple[list[Finding], str]:
        rows = [s for s in ctx["passing"] if s.reaction in set(reactions)]
        user = (f"{self.header(ctx)}\n\nReactions to classify (from query {ctx['screen_qid']}):\n"
                f"{screen_table(rows, len(rows))}\n\n{excerpt_block(reactions, ctx['label'], ctx['label_qid'])}")
        if feedback:
            user += ("\n\nThe Reviewer reviewed your earlier findings for these reactions. For each rejected one, "
                     "answer its objection: change your answer if the objection holds, or keep it and say why in "
                     "\"reasoning\". Classify the missing ones it named:\n" + json.dumps(feedback, indent=1))
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": CLASSIFY_SYSTEM},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS)
        # Match names case- and space-insensitively and keep the table's spelling; the first finding per reaction wins.
        wanted = {norm(r): r for r in reactions}
        findings: dict[str, Finding] = {}
        for d in out.get("findings", []):
            if isinstance(d, dict):
                f = Finding.from_dict(d)
                name = wanted.get(norm(f.reaction))
                if name and name not in findings:
                    f.reaction = name
                    findings[name] = f
        return list(findings.values()), str(out.get("summary", ""))

    def run(self, ctx: dict) -> tuple[list[Finding], str]:
        ctx["picked"] = self.pick(ctx)
        return self.classify(ctx, ctx["picked"])

    def revise(self, ctx: dict, rejected: list[Finding], feedback: dict) -> tuple[list[Finding], str]:
        """Re-classify only the rejected findings and the newly named missing reactions."""
        names = [f.reaction for f in rejected] + [m["reaction"] for m in feedback.get("missing", [])]
        return self.classify(ctx, list(dict.fromkeys(names)), feedback)
