"""Reviewer: checks every Analyst finding against Zetaris and the label, then reviews the reasoning.
Code checks come first and cannot be overruled by the model: a finding with wrong numbers, no
evidence, a label term that is not in the label, or an inconsistent priority is rejected.
The model then accepts, rejects (with an objection the Analyst must answer), or marks a finding
unresolved when the evidence available cannot settle it."""
import json
from concurrent.futures import ThreadPoolExecutor

from app.adapters.meterless import MeterlessError, NightshiftClient
from app.agents.analyst import BATCH, MAX_TOKENS, context_notes, screen_table
from app.agents.skeptic import compact
from app.data.faers import DataClerk
from app.data.label import INDICATION, META, SAFETY, excerpt_block, find_term, label_sentence, norm
from app.schemas import CONTEXT, COVERAGE, PRIORITY, Finding, Signal, Verdict

UNPICKED_ROWS = 15
UNREVIEWED = "passed code checks; model review unavailable (Nightshift error), reasoning not reviewed"
NO_VERDICT = "passed code checks; the Reviewer's reply gave no valid verdict for it, reasoning not reviewed"

SYSTEM = """You are the Reviewer in a drug-safety review team. The Analyst has assessed FAERS reactions for one drug: what kind of term each is ("context"), whether the current label covers it ("label_coverage"), and how urgently an analyst should look at it ("review_priority"). FAERS statistics show reporting patterns, not causation.

Code has already re-run each finding's numbers on the database, found the label sentence for each "label_term" (in "label_quote"), and checked that the fields are consistent; see "checks". Your job is the reasoning.

For each finding, decide:
- "accept": the context, coverage and priority are defensible from the evidence shown.
- "reject": something is wrong and the Analyst can fix it. Examples: the label_quote does not describe the reaction; the label text shown does describe a reaction marked not_found; the reaction is plainly the treated condition; a vague term is marked review_next; the reasoning claims the drug causes the reaction.
- "unresolved": the evidence available here cannot settle it either way (for example only a narrower label term exists). Say what is missing.

A treated condition that the label says the drug may cause or worsen (for example low blood glucose with a diabetes drug) is correctly "covered". A condition named only in the contraindications is one the drug must not be used in, not an effect of the drug; reject "covered" when that is the only support.

Some findings carry "co_reported_drugs": the Skeptic's check of the drugs most often reported alongside this one, computed from database counts. "adjusted_prr" is this drug's PRR after adjusting for that co-drug; below 2 means the pattern may come from the co-drug rather than this drug. "combination_partner" means the co-drug is sold in one product with this drug, so many reports name both by construction; a signal that falls below 2 when adjusted for a combination partner may belong to the partner. Two fields are context only: "shared_with_co_drugs" means the reaction is also disproportionate for most co-drugs, which is common because the co-drugs go to the same patients; "possible_interaction" means reports naming both drugs show more of the reaction than either alone predicts, which sicker patients on several drugs can also cause. "attenuated_by" is context too: co-drugs that lower the PRR by 30% or more without taking it below 2. Decide whether the finding's priority and reasoning still hold given this evidence. If they do not, reject with an objection that names the co-drug and the numbers, or mark it unresolved. This evidence is about reporting patterns, not proof either way.

FAERS counts have no denominator: reject reasoning or a next_check that compares a PRR or report count with an incidence or clinical-trial frequency, unless the check names another data source with a denominator. Do not make that comparison in your own objection or next_check either.

For every finding give "objection": the strongest objection to it as it stands (an alternative explanation, a data limitation, or a wording gap), even when you accept it. Give "next_check": the single most useful check an analyst could run next.

Then list up to 3 "missing" reactions from the rows nobody has assessed yet that a reviewer would expect to see. Leave "missing" empty if nothing important is missing.

Reply with only a JSON object:
{"verdicts": [{"reaction": str, "decision": "accept" or "reject" or "unresolved", "reason": str, "objection": str, "next_check": str}], "missing": [{"reaction": str, "why": str}], "summary": str}"""


def code_checks(f: Finding, fresh: Signal | None, label: dict, evidence_ids: set[str]) -> dict:
    """Deterministic checks. Returns {check: (passed, detail)}. Fills f.label_quote from the label."""
    c = {}
    c["valid_fields"] = (f.label_coverage in COVERAGE and f.context in CONTEXT and f.review_priority in PRIORITY,
                         f"{f.context} / {f.label_coverage} / {f.review_priority}")
    if fresh is None:
        c["in_database"] = (False, "reaction not found in the screen for this drug")
    else:
        c["in_database"] = (True, f"a={fresh.a}, prr={fresh.prr}, chi2={fresh.chi2}")
        c["numbers_match"] = (f.a == fresh.a and abs(f.prr - fresh.prr) <= max(0.05, 0.01 * fresh.prr),
                              f"claimed a={f.a}, prr={f.prr}")
        if f.review_priority == "review_next":
            c["passes_screen"] = (fresh.a >= 3 and fresh.prr >= 2 and fresh.chi2 >= 4, "Evans: a>=3, PRR>=2, chi2>=4")
    cited = [e for e in f.evidence if e in evidence_ids]
    c["cites_evidence"] = (bool(cited), ", ".join(f.evidence) or "none")
    if f.label_coverage == "covered":
        section = label.get(f.label_section or "") or " ".join(
            v for k, v in label.items() if k not in META)
        f.label_quote = label_sentence(section, f.label_term or "")
        c["term_in_label"] = (f.label_quote is not None, f"term '{f.label_term}' in {f.label_section}")
    if f.label_coverage == "not_found":
        # A name in the contraindications is a condition the drug must not be used in, not an effect,
        # so "not_found" stays possible for it (metformin DIABETIC KETOACIDOSIS).
        named = find_term(f.reaction, label, only=(INDICATION,) + SAFETY) is not None
        c["not_named_in_label"] = (not named, f"label text {'contains' if named else 'does not contain'} "
                                              f"'{f.reaction.lower()}'")
    if f.review_priority == "review_next":
        # Only an unlabelled clinical event can be sent for review, and it must say what to check.
        c["priority_consistent"] = (f.context == "clinical_event" and f.label_coverage in ("not_found", "unclear"),
                                    "review_next needs a clinical_event that is not_found or unclear in the label")
        c["has_next_check"] = (bool(f.next_check), "review_next needs a next_check")
    return c


def failed(checks: dict) -> list[str]:
    return [f"{k}: {d}" for k, (ok, d) in checks.items() if not ok]


class Reviewer:
    name = "reviewer"

    def __init__(self, llm: NightshiftClient, model: str, clerk: DataClerk, parallel: int = 2):
        self.llm = llm
        self.model = model
        self.clerk = clerk
        self.parallel = parallel

    def review(self, ctx: dict, findings: list[Finding], seen: set[str]) -> tuple[list[Verdict], list[dict], str]:
        """Check and review findings. `seen` holds every reaction already attempted, so "missing" only
        names reactions nobody has looked at yet."""
        verdicts, checked = [], []
        for f in findings:
            res, fresh = self.clerk.signal(ctx["drug"], f.reaction, agent=self.name)
            checks = code_checks(f, fresh, ctx["label"], ctx["evidence_ids"] | {res.query_id})
            checked.append((f, checks, res.query_id))

        skeptic = ctx.get("skeptic", {})
        payload = [{**f.to_dict(), "checks": {k: {"passed": ok, "detail": d} for k, (ok, d) in ch.items()},
                    "recheck_query": qid,
                    **({"co_reported_drugs": compact(skeptic[f.reaction])} if f.reaction in skeptic else {})}
                   for f, ch, qid in checked]
        done = {norm(r) for r in seen} | {norm(f.reaction) for f in findings}
        unpicked = [s for s in ctx["passing"] if norm(s.reaction) not in done][:UNPICKED_ROWS]

        # Small parallel batches for the same reason as the Analyst's; only the first looks for missing reactions.
        batches = [payload[i:i + BATCH] for i in range(0, len(payload), BATCH)]
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            outs = list(pool.map(lambda ib: self._review_batch(ctx, ib[1], unpicked if ib[0] == 0 else None),
                                 enumerate(batches)))
        llm, missing, summaries = {}, [], []
        for i, out in enumerate(outs):
            llm.update({norm(v.get("reaction")): v for v in out.get("verdicts", []) if isinstance(v, dict)})
            if i == 0:
                missing = [m for m in out.get("missing", []) if isinstance(m, dict) and m.get("reaction")]
            summaries.append(str(out.get("summary", "")))

        for f, checks, _ in checked:
            bad = failed(checks)
            v = llm.get(norm(f.reaction), {})
            extra = {"objection": str(v.get("objection") or ""), "next_check": str(v.get("next_check") or "")}
            if bad:
                verdicts.append(Verdict(f.reaction, "reject", "failed code checks: " + "; ".join(bad), checks,
                                        objection=extra["objection"] or "; ".join(bad), next_check=extra["next_check"]))
            elif v.get("decision") in ("reject", "unresolved", "unreviewed"):
                reason = UNREVIEWED if v["decision"] == "unreviewed" else str(v.get("reason", ""))
                verdicts.append(Verdict(f.reaction, v["decision"], reason, checks, **extra))
            elif v.get("decision") == "accept":
                verdicts.append(Verdict(f.reaction, "accept", str(v.get("reason") or "passed code checks"), checks,
                                        **extra))
            else:
                # The reply left this finding out or gave an unknown decision: passing code checks is not a review.
                verdicts.append(Verdict(f.reaction, "unreviewed", NO_VERDICT, checks, **extra))
        return verdicts, missing, " ".join(s for s in summaries if s)

    def _review_batch(self, ctx: dict, batch: list[dict], unpicked: list[Signal] | None) -> dict:
        extra = (f"Strongest screen rows nobody has classified yet (query {ctx['screen_qid']}):\n"
                 f"{screen_table(unpicked, UNPICKED_ROWS)}\n\n" if unpicked else
                 "Another batch reviews missing reactions; return \"missing\": [].\n\n")
        names = [p["reaction"] for p in batch]
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content":
                     f"Drug: {ctx['drug']}{context_notes(ctx)}\n\n{extra}{excerpt_block(names, ctx['label'], ctx['label_qid'])}\n\n"
                     f"Analyst findings with code checks:\n{json.dumps(batch, indent=1)}"}]
        try:
            return self.llm.chat_json(self.name, self.model, messages, max_tokens=MAX_TOKENS,
                                      fail_fast=len(batch) > 1)
        except MeterlessError as e:
            if len(batch) > 1:
                # Smaller calls succeed more often: review one finding per call before giving up.
                self.llm.tracer.event(self.name, "degraded", step="review", batch=names, error=str(e)[:200],
                                      fallback="one finding per call")
                outs = [self._review_batch(ctx, [p], unpicked if i == 0 else None) for i, p in enumerate(batch)]
                return {"verdicts": [v for o in outs for v in o.get("verdicts", [])],
                        "missing": outs[0].get("missing", []),
                        "summary": " ".join(o.get("summary", "") for o in outs)}
            self.llm.tracer.event(self.name, "degraded", step="review", batch=names, error=str(e)[:200],
                                  fallback="code checks only")
            return {"verdicts": [{"reaction": r, "decision": "unreviewed", "reason": UNREVIEWED} for r in names]}
