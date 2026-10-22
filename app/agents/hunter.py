"""Hunter: picks the reactions that matter from the disproportionality screen, then classifies
them against the current label. Revises its findings when the Judge rejects them.

Kept small per call: Nightshift ends a provider call after about 45 s, and Nemotron Lightning
spends most of its budget on hidden reasoning when a call is large. So picking and classifying are
separate calls, easy reactions are settled by rules (app/agents/rules.py), the model sees only the
label sentences relevant to each reaction, and classify calls run in small parallel batches."""
import json
from concurrent.futures import ThreadPoolExecutor

from app.adapters.meterless import MeterlessError, NightshiftClient
from app.agents.rules import route
from app.data.label import excerpt_block
from app.schemas import Finding, Signal

# Includes reasoning tokens. Ultra used 2,100 to 4,100 per classify call on 22 Oct; 4,000 truncated one reply.
MAX_TOKENS = 6000
MAX_PICKS = 10
BATCH = 3  # reactions per classify call

PICK_SYSTEM = f"""You are the Hunter in a drug-safety review team. You read a screen of FDA Adverse Event Reporting System (FAERS) statistics for one drug.

Choose up to {MAX_PICKS} reactions a drug-safety reviewer should look at. Prefer strong signals (high PRR backed by many reports) and anything that could be a safety problem, including reactions that may simply be the disease the drug treats, so they can be ruled out. Cover different body systems rather than many terms for the same thing. Skip administrative terms such as product use issues.

Use only reactions from the table, spelled exactly as in the table. Reply with only a JSON object:
{{"picked": [{{"reaction": str, "why": str}}]}}"""

CLASSIFY_SYSTEM = """You are the Hunter in a drug-safety review team. Classify each listed FAERS reaction for one drug against the drug's current label.

Rules:
- Use only the data in the message. Never invent numbers, reactions or label text.
- Copy "reaction", "a" and "prr" exactly from the table.
- Give each reaction exactly one classification:
  - "on_label": the label already describes this reaction or a clearly equivalent event. Give "label_section" (the bracketed section name, e.g. boxed_warning) and "label_term": the word or short phrase (1 to 4 words) the label uses for it, spelled as in the label.
  - "possible_new_signal": the label does not describe it.
  - "likely_indication_or_disease": it is the condition the drug treats, or a feature of that condition, so the reports probably reflect the patients' illness rather than the drug.
  - "not_meaningful": an administrative or non-clinical term.
- "evidence" lists the query IDs your finding relies on.
- "reasoning" is one short plain sentence. "summary" is at most two sentences.

Reply with only a JSON object:
{"findings": [{"reaction": str, "a": int, "prr": float, "classification": str, "label_section": str or null, "label_term": str or null, "reasoning": str, "evidence": [str]}], "summary": str}"""


def screen_table(signals: list[Signal], limit: int) -> str:
    lines = ["reaction | a (reports with drug) | PRR | chi2"]
    lines += [f"{s.reaction} | {s.a} | {s.prr} | {s.chi2}" for s in signals[:limit]]
    return "\n".join(lines)


class Hunter:
    name = "hunter"

    def __init__(self, llm: NightshiftClient, model: str, parallel: int = 2):
        self.llm = llm
        self.model = model
        self.parallel = parallel

    def header(self, ctx: dict) -> str:
        return (f"Drug: {ctx['drug']}\n"
                f"FAERS reports mentioning the drug: {ctx['totals']['drug_reports']} of {ctx['totals']['all_reports']} "
                f"(openFDA data updated {ctx['totals']['data_last_updated']}; query {ctx['totals']['query_id']}).")

    def pick(self, ctx: dict) -> list[str]:
        try:
            return self._pick(ctx)
        except MeterlessError as e:
            fallback = [s.reaction for s in ctx["passing"][:MAX_PICKS]]
            self.llm.tracer.event(self.name, "degraded", step="pick", error=str(e)[:200],
                                  fallback="top reactions by chi2", reactions=fallback)
            return fallback

    def _pick(self, ctx: dict) -> list[str]:
        user = (f"{self.header(ctx)}\n\nDisproportionality screen (query {ctx['screen_qid']}). Rows pass the Evans "
                f"screen (PRR >= 2, chi2 >= 4, at least 3 reports), strongest evidence (chi2) first, top {ctx['screen_shown']} of "
                f"{ctx['screen_passing']}:\n{ctx['screen_table']}")
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": PICK_SYSTEM},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS)
        known = {s.reaction for s in ctx["passing"]}
        picked = [p["reaction"] for p in out.get("picked", []) if isinstance(p, dict) and p.get("reaction") in known]
        self.llm.tracer.event(self.name, "picked", reactions=picked,
                              dropped=[p for p in out.get("picked", []) if isinstance(p, dict)
                                       and p.get("reaction") not in known])
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
            f, s = self._classify_batch(ctx, batch, fb)
            return f, s, []
        except MeterlessError as e:
            # Smaller calls succeed more often; a reaction that still fails is reported, not guessed.
            self.llm.tracer.event(self.name, "degraded", step="classify", batch=batch, error=str(e)[:200],
                                  fallback="one reaction per call")
            found, failed = [], []
            for r in batch:
                try:
                    found += self._classify_batch(ctx, [r], fb)[0]
                except MeterlessError as e2:
                    failed.append(r)
                    self.llm.tracer.event(self.name, "unclassified", reaction=r, error=str(e2)[:200])
            return found, "", failed

    def _classify_batch(self, ctx: dict, reactions: list[str], feedback: dict | None) -> tuple[list[Finding], str]:
        rows = [s for s in ctx["passing"] if s.reaction in set(reactions)]
        user = (f"{self.header(ctx)}\n\nReactions to classify (from query {ctx['screen_qid']}):\n"
                f"{screen_table(rows, len(rows))}\n\n{excerpt_block(reactions, ctx['label'], ctx['label_qid'])}")
        if feedback:
            user += ("\n\nThe Judge reviewed your earlier findings for these reactions. Fix the rejected ones and "
                     "classify the missing ones it named:\n" + json.dumps(feedback, indent=1))
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": CLASSIFY_SYSTEM},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS)
        wanted = set(reactions)
        findings = [Finding.from_dict(d) for d in out.get("findings", []) if isinstance(d, dict)]
        return [f for f in findings if f.reaction in wanted], str(out.get("summary", ""))

    def run(self, ctx: dict) -> tuple[list[Finding], str]:
        return self.classify(ctx, self.pick(ctx))

    def revise(self, ctx: dict, rejected: list[Finding], feedback: dict) -> tuple[list[Finding], str]:
        """Re-classify only the rejected findings and the newly named missing reactions."""
        names = [f.reaction for f in rejected] + [m["reaction"] for m in feedback.get("missing", [])]
        return self.classify(ctx, list(dict.fromkeys(names)), feedback)
