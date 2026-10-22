"""Judge: checks every Hunter finding against Zetaris and the label, then reviews the reasoning.
Code checks come first and cannot be overruled by the model: a finding with wrong numbers,
no evidence, or a label quote that is not in the label is rejected."""
import json
from concurrent.futures import ThreadPoolExecutor

from app.adapters.meterless import MeterlessError, NightshiftClient
from app.agents.hunter import BATCH, MAX_TOKENS, screen_table
from app.data.faers import Clerk
from app.data.label import META, excerpt_block, label_sentence, named_in_label, norm
from app.schemas import CLASSIFICATIONS, Finding, Signal, Verdict

UNPICKED_ROWS = 15
UNREVIEWED = "passed code checks; model review unavailable (Nightshift error), reasoning not reviewed"

SYSTEM = """You are the Judge in a drug-safety review team. The Hunter has classified FAERS reactions for one drug. Code has already re-run each finding's numbers on the database, found the label sentence for each "label_term" (in "label_quote"), and checked whether the label names each claimed new signal; those results are in "checks". Your job is the reasoning.

For each finding that passed the checks, decide "accept" or "reject":
- Reject "on_label" if the label_quote does not actually describe that reaction or an equivalent event.
- Reject "possible_new_signal" if the label text shown does describe it, or if the reaction is plainly the treated disease.
- Reject "likely_indication_or_disease" if the reaction is not related to what the drug treats.
- Reject reasoning that claims the drug causes the reaction. FAERS shows association only.
Then list up to 3 "missing" reactions from the rows nobody has classified yet that a reviewer would expect to see. Leave "missing" empty if nothing important is missing.

Reply with only a JSON object:
{"verdicts": [{"reaction": str, "decision": "accept" or "reject", "reason": str}], "missing": [{"reaction": str, "why": str}], "summary": str}"""


def code_checks(f: Finding, fresh: Signal | None, label: dict, evidence_ids: set[str]) -> dict:
    """Deterministic checks. Returns {check: (passed, detail)}. Fills f.label_quote from the label."""
    c = {}
    c["classification"] = (f.classification in CLASSIFICATIONS, f.classification)
    if fresh is None:
        c["in_database"] = (False, "reaction not found in the screen for this drug")
    else:
        c["in_database"] = (True, f"a={fresh.a}, prr={fresh.prr}, chi2={fresh.chi2}")
        c["numbers_match"] = (f.a == fresh.a and abs(f.prr - fresh.prr) <= max(0.05, 0.01 * fresh.prr),
                              f"claimed a={f.a}, prr={f.prr}")
        if f.classification == "possible_new_signal":
            c["passes_screen"] = (fresh.a >= 3 and fresh.prr >= 2 and fresh.chi2 >= 4, "Evans: a>=3, PRR>=2, chi2>=4")
    cited = [e for e in f.evidence if e in evidence_ids]
    c["cites_evidence"] = (bool(cited), ", ".join(f.evidence) or "none")
    if f.classification == "on_label":
        section = label.get(f.label_section or "") or " ".join(
            v for k, v in label.items() if k not in META)
        f.label_quote = label_sentence(section, f.label_term or "")
        c["term_in_label"] = (f.label_quote is not None, f"term '{f.label_term}' in {f.label_section}")
    if f.classification == "possible_new_signal":
        c["not_named_in_label"] = (not named_in_label(f.reaction, label),
                                   f"label text {'contains' if named_in_label(f.reaction, label) else 'does not contain'} "
                                   f"'{f.reaction.lower()}'")
    return c


def failed(checks: dict) -> list[str]:
    return [f"{k}: {d}" for k, (ok, d) in checks.items() if not ok]


class Judge:
    name = "judge"

    def __init__(self, llm: NightshiftClient, model: str, clerk: Clerk, parallel: int = 2):
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

        payload = [{**f.to_dict(), "checks": {k: {"passed": ok, "detail": d} for k, (ok, d) in ch.items()},
                    "recheck_query": qid} for f, ch, qid in checked]
        done = {norm(r) for r in seen} | {norm(f.reaction) for f in findings}
        unpicked = [s for s in ctx["passing"] if norm(s.reaction) not in done][:UNPICKED_ROWS]

        # Small parallel batches for the same reason as the Hunter's; only the first looks for missing reactions.
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
            if bad:
                verdicts.append(Verdict(f.reaction, "reject", "failed code checks: " + "; ".join(bad), checks))
            elif v.get("decision") == "reject":
                verdicts.append(Verdict(f.reaction, "reject", str(v.get("reason", "")), checks))
            elif v.get("decision") == "unreviewed":
                verdicts.append(Verdict(f.reaction, "unreviewed", UNREVIEWED, checks))
            else:
                verdicts.append(Verdict(f.reaction, "accept", str(v.get("reason") or "passed code checks"), checks))
        return verdicts, missing, " ".join(s for s in summaries if s)

    def _review_batch(self, ctx: dict, batch: list[dict], unpicked: list[Signal] | None) -> dict:
        extra = (f"Strongest screen rows nobody has classified yet (query {ctx['screen_qid']}):\n"
                 f"{screen_table(unpicked, UNPICKED_ROWS)}\n\n" if unpicked else
                 "Another batch reviews missing reactions; return \"missing\": [].\n\n")
        names = [p["reaction"] for p in batch]
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content":
                     f"Drug: {ctx['drug']}\n\n{extra}{excerpt_block(names, ctx['label'], ctx['label_qid'])}\n\n"
                     f"Hunter findings with code checks:\n{json.dumps(batch, indent=1)}"}]
        try:
            return self.llm.chat_json(self.name, self.model, messages, max_tokens=MAX_TOKENS)
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
