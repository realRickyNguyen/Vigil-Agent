"""Offline checks on the agents' prompts. Run: python -I -m pytest tests"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.analyst import CLASSIFY_SYSTEM, PICK_SYSTEM  # noqa: E402
from app.agents.reviewer import SYSTEM as REVIEW_SYSTEM  # noqa: E402


def test_reviewer_gives_its_objection_before_its_decision():
    """On 23 Oct the Reviewer accepted dyspnoea as a montelukast signal to review, though its own objection
    called it an asthma symptom. It had written its decision first, so the objection came too late to count."""
    reply_format = REVIEW_SYSTEM[REVIEW_SYSTEM.index('{"verdicts"'):]
    assert reply_format.index('"objection"') < reply_format.index('"decision"')


def test_both_agents_count_symptoms_of_the_treated_condition_as_the_treated_condition():
    """The Reviewer must reject what the Analyst is told is the treated condition, so both use one definition."""
    definition = "a symptom, sign, measure or complication"
    assert definition in CLASSIFY_SYSTEM and definition in REVIEW_SYSTEM


def test_prompts_name_no_gold_drug_or_reaction():
    """Examples in prompts come from drugs outside the gold set. Otherwise the evaluation would score the
    prompt's own answers back to it."""
    gold = [json.loads(line) for line in (ROOT / "eval" / "gold_v1.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    names = {g["drug"] for g in gold} | {g["reaction"] for g in gold}
    for prompt in (PICK_SYSTEM, CLASSIFY_SYSTEM, REVIEW_SYSTEM):
        assert [n for n in names if re.search(rf"\b{re.escape(n.lower())}\b", prompt.lower())] == []
