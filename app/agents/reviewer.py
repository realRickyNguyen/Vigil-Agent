"""Reviewer: checks every Analyst finding against Zetaris and the label, then reviews the reasoning.
Code checks come first and cannot be overruled by the model: a finding with wrong numbers, no
evidence, a label term that is not in the label, or an inconsistent priority is rejected.
The model then accepts, rejects (with an objection the Analyst must answer), or marks a finding
unresolved when the evidence available cannot settle it."""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.adapters.meterless import MeterlessError, MeterlessUnauthorized, NightshiftClient
from app.adapters.zetaris import ZetarisError
from app.agents.analyst import BATCH, MAX_TOKENS, context_notes, screen_table
from app.agents.skeptic import compact
from app.data import uncertainty
from app.data.faers import DataClerk
from app.data.label import EFFECT, META, effect_text, excerpt_block, label_sentence, norm, search
from app.data.sources import compact as sources_compact
from app.schemas import CONTEXT, COVERAGE, PRIORITY, Finding, Signal, Verdict

UNPICKED_ROWS = 15
UNREVIEWED = "passed code checks; model review unavailable (Nightshift error), reasoning not reviewed"
NO_VERDICT = "passed code checks; the Reviewer's reply gave no valid verdict for it, reasoning not reviewed"
RECHECK_FAILED = "numbers not verified: the Zetaris re-check query failed"

SYSTEM = """You are the Reviewer in a drug-safety review team. The Analyst has assessed FAERS reactions for one drug: what kind of term each is ("context"), whether the current label covers it ("label_coverage"), and how urgently an analyst should look at it ("review_priority"). FAERS statistics show reporting patterns, not causation.

Code has already re-run each finding's numbers on the database, found the label sentence for each "label_term" (in "label_quote"), and checked that the fields are consistent; see "checks". Your job is the reasoning.

For each finding, decide:
- "accept": the context, coverage and priority are defensible from the evidence shown.
- "reject": something is wrong and the Analyst can fix it. Examples: the label_quote does not describe the reaction; the label text shown does describe a reaction marked not_found; the reaction is plainly the treated condition; a vague term is marked review_next; the reasoning claims the drug causes the reaction.
- "unresolved": the evidence available here cannot settle it either way (for example only a narrower label term exists). Say what is missing.

A treated condition that the label says the drug may cause or worsen (for example low blood pressure with a blood-pressure drug) is correctly "covered". A symptom, sign, measure or complication of the treated disease is "treated_condition" even when the label does not mention it; reject it as a clinical_event sent for review just because the label does not list it. A condition named only in the contraindications is one the drug must not be used in, not an effect of the drug; reject "covered" when that is the only support. The same holds for a Limitation of Use, drug interactions, pharmacokinetics and pharmacology. A reaction the label names only as an expected effect of the drug (mechanism_of_action or pharmacodynamics) is "unclear", not "covered" or "not_found". Each reaction's "Code search" line says which sections code searched and where it found the name; a "not_found" must agree with it.

Some findings carry "co_reported_drugs": the Skeptic's check of the drugs most often reported alongside this one, computed from database counts. "adjusted_prr" is this drug's PRR after adjusting for that co-drug; below 2 means the pattern may come from the co-drug rather than this drug. "combination_partner" means the co-drug is sold in one product with this drug, so many reports name both by construction; a signal that falls below 2 when adjusted for a combination partner may belong to the partner. Two fields are context only: "shared_with_co_drugs" means the reaction is also disproportionate for most co-drugs, which is common because the co-drugs go to the same patients; "possible_interaction" means reports naming both drugs show more of the reaction than either alone predicts, which sicker patients on several drugs can also cause. "attenuated_by" is context too: co-drugs that lower the PRR by 30% or more without taking it below 2. Decide whether the finding's priority and reasoning still hold given this evidence. If they do not, reject with an objection that names the co-drug and the numbers, or mark it unresolved. This evidence is about reporting patterns, not proof either way.

Some review_next findings carry "report_sources", where their reports come from, computed from database counts. "one_country" means one country holds most reports with a known country, well above the drug's usual share, which often means copies of one case re-filed by many companies. "lawyer_reports" means lawyers filed 20% or more of the reports that say who reported, as in litigation. "few_health_professionals" means under half of them came from health professionals. "unknown" means too few reports say. These describe evidence quality, not whether the pattern is real. Name a raised flag in your objection or next_check, but never reject a finding for a flag alone. "unknown" can also mean the counts could not be fetched, and a "status" in place of flags means the check had not finished or failed.

FAERS counts have no denominator: reject reasoning or a next_check that compares a PRR or report count with an incidence or clinical-trial frequency, unless the check names another data source with a denominator. Do not make that comparison in your own objection or next_check either.

Each finding's "uncertainty" is worked out in code from the database counts. When "thin_evidence" is true, the reasoning must describe it as thin evidence. Reject reasoning that calls it statistically significant, strong or robust, or cites its chi2 as strength. Thin evidence alone is not a reason to reject; the wording is.

For every finding give "objection": the strongest objection to it as it stands (an alternative explanation, a data limitation, or a wording gap), even when you accept it. Give "next_check": the single most useful check an analyst could run next.

Then list up to 3 "missing" reactions from the rows nobody has assessed yet that a reviewer would expect to see. Leave "missing" empty if nothing important is missing.

Reply with only a JSON object:
{"verdicts": [{"reaction": str, "decision": "accept" or "reject" or "unresolved", "reason": str, "objection": str, "next_check": str}], "missing": [{"reaction": str, "why": str}], "summary": str}"""


def code_checks(f: Finding, fresh: Signal | None, label: dict, evidence_ids: set[str]) -> dict:
    """Deterministic checks. Returns {check: (passed, detail)}. Fills f.label_quote from the label."""
    c = {}
    c["valid_fields"] = (f.label_coverage in COVERAGE and f.context in CONTEXT and f.review_priority in PRIORITY,
                         f"{f.context} / {f.label_coverage} / {f.review_priority}")
    # A treated condition is covered (the label warns the drug can cause or worsen it) or not assessed; a
    # non-clinical term is never assessed against the label.
    allowed = {"treated_condition": ("covered", "not_assessed"), "non_clinical": ("not_assessed",)}
    if f.context in allowed:
        c["coverage_fits_context"] = (f.label_coverage in allowed[f.context],
                                      f"{f.context} must be {' or '.join(allowed[f.context])}")
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
        # Coverage rests only on text that says what the drug may cause, never on the contraindications, a
        # Limitation of Use, the interactions, the pharmacokinetics or the pharmacology, and for a Medication Guide
        # or patient leaflet only on its side-effect parts. A section the label lacks, or none, means any of them.
        sec = f.label_section or ""
        not_effect = sec in label and sec not in META and sec not in EFFECT
        if not_effect:
            c["coverage_section"] = (False, f"{sec} never counts as coverage on its own")
        f.label_quote = None if not_effect else label_sentence(effect_text(label, sec if sec in label else None),
                                                               f.label_term or "")
        c["term_in_label"] = (f.label_quote is not None, f"term '{f.label_term}' in {f.label_section}")
    if f.label_coverage == "not_found":
        # A name in the contraindications is a condition the drug must not be used in, not an effect,
        # so "not_found" stays possible for it (metformin DIABETIC KETOACIDOSIS). The code search's "named_in"
        # holds the parts that make it wrong (label.search).
        named = search(f.reaction, label)["named_in"]
        c["not_named_in_label"] = (not named, f"label text {'names' if named else 'does not name'} "
                                              f"'{f.reaction.lower()}'" + (f", or a related term, in {', '.join(named)}"
                                                                           if named else ""))
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
    source_wait = 45  # seconds a review waits, in all, for report-source checks before going on without them

    def __init__(self, llm: NightshiftClient, model: str, clerk: DataClerk, parallel: int = 2):
        self.llm = llm
        self.model = model
        self.clerk = clerk
        self.parallel = parallel

    def review(self, ctx: dict, findings: list[Finding], seen: set[str]) -> tuple[list[Verdict], list[dict], str]:
        """Check and review findings. `seen` holds every reaction already attempted, so "missing" only
        names reactions nobody has looked at yet."""
        verdicts, checked = [], []
        if not findings:  # an empty re-check would fetch the drug's whole screen
            return [], [], ""
        try:
            res, fresh = self.clerk.recheck(ctx["drug"], [f.reaction for f in findings], agent=self.name)
        except ZetarisError as e:
            # Without the re-check the numbers cannot be verified, so no finding is reviewed (no crash).
            self.llm.tracer.event(self.name, "degraded", step="recheck", error=str(e)[:200], fallback="not reviewed")
            return ([Verdict(f.reaction, "unreviewed", f"{RECHECK_FAILED} ({str(e)[:200]})", {}) for f in findings],
                    [], "")
        for f in findings:
            checks = code_checks(f, fresh.get(f.reaction), ctx["label"], ctx["evidence_ids"] | {res.query_id})
            checked.append((f, checks, res.query_id))

        skeptic = ctx.get("skeptic", {})
        # "uncertainty" from the re-checked counts, so the Reviewer can hold a thin row's wording to account.
        payload = [{**f.to_dict(), "checks": {k: {"passed": ok, "detail": d} for k, (ok, d) in ch.items()},
                    "recheck_query": qid,
                    **({"uncertainty": uncertainty.of(fresh[f.reaction])} if f.reaction in fresh else {}),
                    **({"co_reported_drugs": compact(skeptic[f.reaction])} if f.reaction in skeptic else {})}
                   for f, ch, qid in checked]
        done = {norm(r) for r in seen} | {norm(f.reaction) for f in findings}
        unpicked = [s for s in ctx["passing"] if norm(s.reaction) not in done][:UNPICKED_ROWS]
        # review_next findings last, so their report-source checks (started with this round) have time to finish.
        # One deadline for the whole review, never past the run's budget, so waits cannot stack across batches.
        payload.sort(key=lambda p: p.get("review_priority") == "review_next")
        deadline = min(time.monotonic() + self.source_wait, ctx.get("run_ends", math.inf))

        # Small parallel batches for the same reason as the Analyst's; only the first looks for missing reactions.
        batches = [payload[i:i + BATCH] for i in range(0, len(payload), BATCH)]
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            outs = list(pool.map(lambda ib: self._review_batch(ctx, ib[1], unpicked if ib[0] == 0 else None, deadline),
                                 enumerate(batches)))
        llm, missing, summaries = {}, [], []
        for i, out in enumerate(outs):
            # "or []" because a reply with "verdicts": null must not crash the run.
            llm.update({norm(v.get("reaction")): v for v in out.get("verdicts") or [] if isinstance(v, dict)})
            if i == 0:
                missing = [m for m in out.get("missing") or [] if isinstance(m, dict) and m.get("reaction")]
            summaries.append(str(out.get("summary") or ""))

        for f, checks, _ in checked:
            bad = failed(checks)
            v = llm.get(norm(f.reaction), {})
            decision = str(v.get("decision") or "").strip().lower()
            extra = {"objection": str(v.get("objection") or ""), "next_check": str(v.get("next_check") or "")}
            if bad:
                verdicts.append(Verdict(f.reaction, "reject", "failed code checks: " + "; ".join(bad), checks,
                                        objection=extra["objection"] or "; ".join(bad), next_check=extra["next_check"]))
            elif decision in ("reject", "unresolved", "unreviewed"):
                reason = UNREVIEWED if decision == "unreviewed" else str(v.get("reason", ""))
                verdicts.append(Verdict(f.reaction, decision, reason, checks, **extra))
            elif decision == "accept":
                verdicts.append(Verdict(f.reaction, "accept", str(v.get("reason") or "passed code checks"), checks,
                                        **extra))
            else:
                # The reply left this finding out or gave an unknown decision: passing code checks is not a review.
                verdicts.append(Verdict(f.reaction, "unreviewed", NO_VERDICT, checks, **extra))
        return verdicts, missing, " ".join(s for s in summaries if s)

    def report_sources(self, ctx: dict, reaction: str, deadline: float | None = None) -> dict | None:
        """The item's report-source check (app/data/sources.py) for the prompt, waiting for it until the review's
        deadline; None if the item has none."""
        fut = ctx.get("sources", {}).get(reaction)
        if fut is None:
            return None
        try:
            wait = self.source_wait if deadline is None else max(0.0, deadline - time.monotonic())
            return sources_compact(fut.result(timeout=wait))
        except FutureTimeout:
            return {"status": "not finished in time for this review"}
        except Exception as e:  # context only, so no failure of this check may stop the review
            return {"status": f"failed: {str(e)[:200]}"}

    def _review_batch(self, ctx: dict, batch: list[dict], unpicked: list[Signal] | None,
                      deadline: float | None = None) -> dict:
        for p in batch:
            if "report_sources" not in p and (ev := self.report_sources(ctx, p["reaction"], deadline)) is not None:
                p["report_sources"] = ev
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
        except MeterlessUnauthorized:
            raise  # a bad Runtime token fails every call; stop the run instead of marking items not reviewed
        except (MeterlessError, ValueError) as e:  # ValueError: no JSON object even after the repair request
            if len(batch) > 1:
                # Smaller calls succeed more often: review one finding per call before giving up.
                self.llm.tracer.event(self.name, "degraded", step="review", batch=names, error=str(e)[:200],
                                      fallback="one finding per call")
                outs = [self._review_batch(ctx, [p], unpicked if i == 0 else None, deadline)
                        for i, p in enumerate(batch)]
                return {"verdicts": [v for o in outs for v in o.get("verdicts") or []],
                        "missing": outs[0].get("missing") or [],
                        "summary": " ".join(str(o.get("summary") or "") for o in outs)}
            self.llm.tracer.event(self.name, "degraded", step="review", batch=names, error=str(e)[:200],
                                  fallback="code checks only")
            return {"verdicts": [{"reaction": r, "decision": "unreviewed", "reason": UNREVIEWED} for r in names]}
