"""Offline checks on the agents' prompts. Run: python -I -m pytest tests"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.analyst import CLASSIFY_SYSTEM, PICK_SYSTEM  # noqa: E402
from app.agents.reviewer import SYSTEM as REVIEW_SYSTEM  # noqa: E402


def test_prompts_name_no_gold_drug_or_reaction():
    """Examples in prompts come from drugs outside the gold set. Otherwise the evaluation would score the
    prompt's own answers back to it."""
    gold = [json.loads(line) for line in (ROOT / "eval" / "gold_v1.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    names = {g["drug"] for g in gold} | {g["reaction"] for g in gold}
    for prompt in (PICK_SYSTEM, CLASSIFY_SYSTEM, REVIEW_SYSTEM):
        assert [n for n in names if re.search(rf"\b{re.escape(n.lower())}\b", prompt.lower())] == []
