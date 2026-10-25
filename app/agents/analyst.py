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
from app.agents.skeptic import compact
from app.data import uncertainty
from app.data.label import excerpt_block, norm
from app.schemas import Finding, Signal

# Includes reasoning tokens. Ultra used 2,100 to 4,100 per classify call on 22 Oct; 4,000 truncated one reply.
MAX_TOKENS = 6000
# Selection (changed 23 Oct): the strongest rows by chi-squared are always assessed, and the model may add a few
# from the rest of the shown rows. Before, the model chose 10 of the top 30 and the 22 Oct evaluation found only
# 27 of 80 clear reference items were assessed in round 1. A fixed rule is transparent and names no drug.
TOP_ALWAYS = 15
EXTRA_PICKS = 5
BATCH = 1  # reactions per model call: on 23 Oct, 3-reaction calls often passed Nightshift's ~50 s deadline
COMBINATION_NOTE_AT = 0.05  # combination share above which the agents are told about partner drugs
THIN_NOTE = (f"Expected a is the count if drug and reaction were independent. Thin evidence means fewer than "
             f"{uncertainty.THIN_REPORTS} reports, or IC025 at or below 0, worked out in code from the same counts.")

PICK_SYSTEM = """You are the Analyst in a drug-safety review team. You read a screen of FDA Adverse Event Reporting System (FAERS) statistics for one drug.

The strongest rows are already being assessed. From the further rows shown, choose up to EXTRA more reactions a drug-safety reviewer should also see: anything that could be a safety problem, especially in body systems the strongest rows do not cover. Skip administrative terms such as product use issues. Choose none if nothing stands out.

Use only reactions from the table, spelled exactly as in the table. Reply with only a JSON object:
{"picked": [{"reaction": str, "why": str}]}"""

CLASSIFY_SYSTEM = """You are the Analyst in a drug-safety review team. For one drug, you help a human drug-safety analyst decide which reported drug-reaction patterns deserve a closer look. FAERS statistics show reporting patterns, not that the drug causes anything.

Answer three separate questions for each listed reaction:

1. "context": what kind of term is it?
   - "non_clinical": about the product, its use, exposure or the report, not a clinical event.
   - "treated_condition": the condition the drug treats, a symptom, sign, measure or complication of it, or an outcome the drug is given to prevent.
   - "clinical_event": any other clinical event.
2. "label_coverage": does the current label describe this reaction as something the drug may cause or worsen?
   - "covered": the label uses the same event, a synonym, or a broader term that clearly contains it. Give "label_section" (the bracketed section name, e.g. boxed_warning) and "label_term" (1 to 4 words, spelled exactly as in the label). Only sections that say what the drug may cause count. A condition named only in the contraindications is one the drug must not be used in, not an effect of the drug, so it is not "covered" on that basis; nor is a Limitation of Use or the drug_interactions, pharmacokinetics or pharmacology sections.
   - "unclear": the label only has a related or narrower term (for example a specific lab abnormality for a vague lab term), or names it only as an expected effect of the drug in mechanism_of_action or pharmacodynamics. Call that an expected effect of the drug in "reasoning", not an adverse effect the label warns about.
   - "not_found": nothing in the label text shown describes it, and the code search names it nowhere that counts.
   - "not_assessed": the term is non_clinical, or it is the treated condition and the label does not say the drug may cause or worsen it.
   Decide "context" first, from what the term is, whatever the label says: a symptom, sign, measure or complication of the treated disease stays "treated_condition" even when the label does not mention it. Then, for a treated condition, check whether the label warns that the drug can cause or worsen it (for example low blood pressure with a blood-pressure drug). If it does, coverage is "covered"; if not, "not_assessed". Never mark a treated condition "not_found".
3. "review_priority":
   - "review_next": a clinical_event that is not_found or unclear in the label, with enough reports to be worth an analyst's time.
   - "insufficient_evidence": not covered, but the term is too vague or the numbers too thin to act on.
   - "lower_priority": covered by the label, the treated condition, or non_clinical.

Also give "reasoning" (one sentence: why this priority) and "next_check" (one concrete check an analyst could run next, for example a specific breakdown of the reports or a label section to compare).

FAERS counts have no denominator. Never compare a PRR or a report count with an incidence or a clinical-trial frequency, and never propose that comparison as a next_check unless the check names another data source that has a denominator.

Each row also shows, worked out in code, the expected count, the PRR's 95% interval, IC025 and whether it is thin evidence. For a row marked thin, say in "reasoning" that it is thin evidence. Never call a thin row statistically significant, strong or robust, and never cite its chi2 as strength.

Rules: use only the data in the message; never invent numbers, reactions or label text; copy "reaction", "a" and "prr" exactly from the table; "evidence" lists the query IDs you relied on; "summary" is at most two sentences.

Reply with only a JSON object:
{"findings": [{"reaction": str, "a": int, "prr": float, "context": str, "label_coverage": str, "review_priority": str, "label_section": str or null, "label_term": str or null, "reasoning": str, "next_check": str, "evidence": [str]}], "summary": str}"""


def screen_table(signals: list[Signal], limit: int, severity: dict | None = None) -> str:
    """The screen rows, each with its expected count, PRR interval, IC025 and thin-evidence mark worked out in code
    from the same counts (app/data/uncertainty.py), so a row with few reports does not look more certain than it
    is. With severity, also the share of each row's reports flagged serious or reporting a death. Severity is shown
    only where the model chooses which rows to look at (the pick step), never where it classifies them (see
    _classify_batch)."""
    pct = lambda v: "n/a" if v is None else f"{v:.0%}"  # noqa: E731
    head = "reaction | a (reports with drug) | PRR | chi2" + (" | serious | death" if severity else "")
    head += " | expected a | PRR 95% CI | IC025 | thin evidence"
    if severity:
        head += ("  (serious / death: share of the a reports flagged serious / reporting a death; the flag is for "
                 "the whole report, not this reaction)")
    lines = [head]
    for s in signals[:limit]:
        u = uncertainty.of(s)
        cells = [s.reaction, s.a, s.prr, s.chi2]
        if severity:
            cells += [pct(severity.get(s.reaction, {}).get(f"{k}_share")) for k in ("serious", "death")]
        cells += [u["expected"], "n/a" if u["prr_ci95"] is None else f"{u['prr_ci95'][0]} to {u['prr_ci95'][1]}",
                  u["ic025"], "yes" if u["thin_evidence"] else "no"]
        lines.append(" | ".join(map(str, cells)))
    lines.append(THIN_NOTE)
    return "\n".join(lines)


def context_notes(ctx: dict) -> str:
    """Facts about the data that change how a reaction should be read, for both agents' prompts."""
    c = ctx.get("combination")
    if not c or c["share"] < COMBINATION_NOTE_AT:
        return ""
    return (f"\nAbout {c['share']:.0%} of these reports name {ctx['drug']} inside a combination product (most "
            f"often {', '.join(p['name'] for p in c['top_products'][:3])}; partner drugs: "
            f"{', '.join(c['partners'][:3])}). A reaction may belong to a partner drug rather than {ctx['drug']}; "
            f"say so where it applies.")


class Analyst:
    name = "analyst"

    def __init__(self, llm: NightshiftClient, model: str, parallel: int = 2, top: int = TOP_ALWAYS,
                 extra: int = EXTRA_PICKS):
        self.llm = llm
        self.model = model
        self.parallel = parallel
        self.top = top
        self.extra = extra

    def header(self, ctx: dict) -> str:
        return (f"Drug: {ctx['drug']}\n"
                f"FAERS reports mentioning the drug: {ctx['totals']['drug_reports']} of {ctx['totals']['all_reports']} "
                f"(openFDA data updated {ctx['totals']['data_last_updated']}; query {ctx['totals']['query_id']})."
                f"{context_notes(ctx)}")

    def pick(self, ctx: dict) -> list[str]:
        """Up to self.extra more reactions from the shown rows below the always-assessed top."""
        rows = ctx["passing"][self.top:ctx["screen_shown"]]
        if not rows or not self.extra:
            return []
        try:
            return self._pick(ctx, rows)
        except MeterlessUnauthorized:
            raise  # a bad Runtime token fails every call; stop the run instead of degrading
        except (MeterlessError, ValueError) as e:
            self.llm.tracer.event(self.name, "degraded", step="pick", error=str(e)[:200],
                                  fallback="no extra picks; the top rows by chi2 are still assessed")
            return []

    def _pick(self, ctx: dict, rows: list[Signal]) -> list[str]:
        top = ", ".join(s.reaction for s in ctx["passing"][:self.top])
        user = (f"{self.header(ctx)}\n\nAlready being assessed (the {self.top} strongest rows by chi2): {top}\n\n"
                f"Further rows of the disproportionality screen (query {ctx['screen_qid']}). Rows pass the Evans "
                f"screen (PRR >= 2, chi2 >= 4, at least 3 reports), strongest evidence (chi2) first:\n"
                f"{screen_table(rows, len(rows), ctx.get('seriousness'))}")
        system = PICK_SYSTEM.replace("EXTRA", str(self.extra))
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": system},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS)
        # Match names case- and space-insensitively, and keep the table's spelling.
        known = {norm(s.reaction): s.reaction for s in rows}
        replies = [p for p in out.get("picked") or [] if isinstance(p, dict)]
        picked = [known[norm(str(p.get("reaction") or ""))] for p in replies
                  if norm(str(p.get("reaction") or "")) in known]
        self.llm.tracer.event(self.name, "picked", reactions=picked,
                              dropped=[p for p in replies if norm(str(p.get("reaction") or "")) not in known])
        return list(dict.fromkeys(picked))[:self.extra]

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
            # A reply that leaves a reaction out must not make it vanish from the queue: ask once more for
            # that reaction alone, then report it as failed.
            failed = []
            for r in [r for r in batch if r not in {x.reaction for x in f}]:
                self.llm.tracer.event(self.name, "omitted", reaction=r, fallback="one reaction per call")
                try:
                    again = self._classify_batch(ctx, [r], fb)[0]
                except MeterlessUnauthorized:
                    raise
                except (MeterlessError, ValueError):
                    again = []
                f += again
                if not again:
                    failed.append(r)
                    self.llm.tracer.event(self.name, "unclassified", reaction=r, error="omitted from the reply")
            return f, s, failed
        except MeterlessUnauthorized:
            raise  # a bad Runtime token fails every call; stop the run instead of marking every item failed
        except (MeterlessError, ValueError) as e:  # ValueError: no JSON object even after the repair request
            if len(batch) == 1:  # already as small as it gets; the client has used its retry
                self.llm.tracer.event(self.name, "unclassified", reaction=batch[0], error=str(e)[:200])
                return [], "", list(batch)
            # Smaller calls succeed more often; a reaction that still fails is reported, not guessed.
            self.llm.tracer.event(self.name, "degraded", step="classify", batch=batch, error=str(e)[:200],
                                  fallback="one reaction per call")
            found, failed = [], []
            for r in batch:
                try:
                    found += self._classify_batch(ctx, [r], fb)[0]
                except MeterlessUnauthorized:
                    raise
                except (MeterlessError, ValueError) as e2:
                    failed.append(r)
                    self.llm.tracer.event(self.name, "unclassified", reaction=r, error=str(e2)[:200])
            return found, "", failed

    def _classify_batch(self, ctx: dict, reactions: list[str], feedback: dict | None) -> tuple[list[Finding], str]:
        rows = [s for s in ctx["passing"] if s.reaction in set(reactions)]
        # No serious or death shares here: on 24 Oct, with them in the table, the Analyst escalated treated-disease
        # terms (metformin HYPERGLYCAEMIA, DIABETIC KETOACIDOSIS) to review_next citing "93% serious, 7% death",
        # and accuracy on the three drugs fell from 88% to 80%. They stay in the pick step and the dossier.
        user = (f"{self.header(ctx)}\n\nReactions to classify (from query {ctx['screen_qid']}):\n"
                f"{screen_table(rows, len(rows))}\n\n{excerpt_block(reactions, ctx['label'], ctx['label_qid'])}")
        skeptic = {r: compact(ctx["skeptic"][r]) for r in reactions if r in ctx.get("skeptic", {})}
        if skeptic:
            user += ("\n\nThe Skeptic checked the drugs most often reported alongside this one (adjusted_prr: this "
                     "drug's PRR adjusted for the co-drug; shared_with_co_drugs: the reaction is also "
                     "disproportionate for most co-drugs, context only; possible_interaction: more reports with both "
                     "drugs than either alone predicts, context only; attenuated_by: co-drugs that lower the PRR by 30% or more "
                     "without taking it below 2, context only). Take it into account and cite its query IDs in \"evidence\" if you "
                     "rely on it:\n" + json.dumps(skeptic, indent=1))
        if feedback:
            user += ("\n\nThe Reviewer reviewed your earlier findings for these reactions. For each rejected one, "
                     "answer its objection: change your answer if the objection holds, or keep it and say why in "
                     "\"reasoning\". Classify the missing ones it named:\n" + json.dumps(feedback, indent=1))
        out = self.llm.chat_json(self.name, self.model, [{"role": "system", "content": CLASSIFY_SYSTEM},
                                                         {"role": "user", "content": user}], max_tokens=MAX_TOKENS,
                                 fail_fast=len(reactions) > 1)
        # Match names case- and space-insensitively and keep the table's spelling; the first finding per reaction wins.
        wanted = {norm(r): r for r in reactions}
        findings: dict[str, Finding] = {}
        for d in out.get("findings") or []:  # "or []": a reply with "findings": null must not crash the run
            if isinstance(d, dict):
                f = Finding.from_dict(d)
                name = wanted.get(norm(f.reaction))
                if name and name not in findings:
                    f.reaction = name
                    findings[name] = f
        return list(findings.values()), str(out.get("summary") or "")

    def run(self, ctx: dict, on_selection=None) -> tuple[list[Finding], str]:
        """The top rows are classified while the pick call chooses the extras, then the extras are classified:
        the pick no longer holds up classification (1 to 3 minutes on 23 Oct). on_selection(reactions) is called
        once the reactions to assess are fixed, before the extras are classified, so work that needs only their
        names can start."""
        always = [s.reaction for s in ctx["passing"][:self.top]]
        with ThreadPoolExecutor(max_workers=1) as pool:
            picking = pool.submit(self.pick, ctx)
            findings, summary = self.classify(ctx, always)
            chosen = picking.result()
        ctx["selection"] = {"always": always, "chosen": chosen,
                            "rule": f"the {self.top} strongest rows by chi2, plus up to {self.extra} chosen by the model"}
        self.llm.tracer.event(self.name, "selection", **ctx["selection"])
        ctx["picked"] = list(dict.fromkeys(always + chosen))
        if on_selection:
            on_selection(ctx["picked"])
        extra =[r for r in ctx["picked"] if r not in always]
        if extra:
            more, more_summary = self.classify(ctx, extra)
            findings += more
            summary = " ".join(x for x in (summary, more_summary) if x)
        return findings, summary

    def revise(self, ctx: dict, rejected: list[Finding], feedback: dict) -> tuple[list[Finding], str]:
        """Re-classify only the rejected findings and the newly named missing reactions."""
        names = [f.reaction for f in rejected] + [m["reaction"] for m in feedback.get("missing", [])]
        return self.classify(ctx, list(dict.fromkeys(names)), feedback)
