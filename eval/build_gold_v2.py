"""Builds eval/gold_v2.jsonl: the v1 decisions, re-checked against the 23 Oct data (see eval/LABELLING_RULES.md).

Why v2: on 23 Oct the drug search changed to generic name OR active substance, which changes each drug's top 20,
and the Data Clerk now picks the newest single-ingredient prescription label, which changes the label text the
agents see (metformin no longer gets the ZITUVIMET combination label). v1 stays as it was, for comparison.

How: rows still in a drug's new top 20 keep their v1 decision unless the new label no longer supports it; those
changes and the new rows are listed below with their evidence. Labelled from the label text and screen only,
before looking at any output of the 23 Oct evaluation runs.

  python -I eval/build_gold_v2.py <worksheet_dir>
The worksheet dir holds <drug>_top20.json and <drug>_label.json, exported from Zetaris on 23 Oct 2026.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = {"O": "on_label", "I": "likely_indication_or_disease", "N": "not_meaningful", "S": "possible_new_signal"}
LABELLED_BY = ("Claude (AI), 23 Oct 2026, per eval/LABELLING_RULES.md (v2 section), before seeing the 23 Oct "
               "evaluation outputs; not yet reviewed by a person")

# v1 rows whose decision or evidence changes with the new label: (reaction, code, ambiguous, evidence)
CHANGED = {
    "montelukast": [
        ("PNEUMONIA", "S", 1, "searched 'pneumonia': no hits in this label (583a9499, 10 mg tablets); v1's label listed "
                              "it in pediatric adverse reactions; respiratory infections are common in the treated population"),
        ("BRONCHITIS", "S", 1, "searched 'bronchit': no hits in this label; v1's label listed 'acute bronchitis'"),
    ],
    "metformin": [
        ("ACUTE KIDNEY INJURY", "S", 1, "searched 'acute kidney|renal failure': no hits; renal impairment appears only as a "
                                        "lactic-acidosis risk factor and contraindication; v1's combination label (sitagliptin) "
                                        "named acute renal failure"),
        ("WEIGHT DECREASED", "S", 1, "not in the adverse-reaction or warning sections; clinical_studies report small mean "
                                     "weight loss"),
    ],
    "sertraline": [
        ("INTENTIONAL OVERDOSE", "O", 1, "boxed_warning: suicidal thoughts and behaviors; this label lacks v1's sentence "
                                         "about prescribing small quantities to reduce the risk of overdose"),
        ("PARANOIA", "O", 1, "adverse_reactions (postmarketing): 'psychosis'; 'paranoid reaction' is not in this label"),
        ("DRUG ABUSE", "N", 1, "misuse circumstance; drug_abuse_and_dependence: not a controlled substance"),
    ],
}

# Reactions new to a drug's top 20 with the two-field search
NEW = {
    "atorvastatin": [
        ("ACUTE KIDNEY INJURY", "O", 0, "warnings: 'renal failure secondary to rhabdomyolysis' (as v1 RENAL FAILURE)"),
        ("DRUG INTERACTION", "N", 1, "no named clinical event; label has a drug interactions section"),
        ("END STAGE RENAL DISEASE", "S", 1, "label names renal failure secondary to rhabdomyolysis (acute) only; chronic "
                                            "kidney disease is common in the treated population (as v1 CKD)"),
        ("ATRIAL FIBRILLATION", "S", 1, "searched 'atrial fibrillation|arrhythmia': no hits; common in the older "
                                        "cardiovascular population"),
        ("CHEST PAIN", "I", 0, "indications: reduce the risk of 'angina'; symptom of coronary heart disease"),
        ("ACUTE MYOCARDIAL INFARCTION", "I", 0, "indications: 'To reduce the risk of: Myocardial infarction (MI)'"),
    ],
    "metformin": [
        ("PANCREATITIS", "S", 1, "searched 'pancreat': no hits; raised in the diabetic population and with co-prescribed "
                                 "incretin drugs"),
    ],
    "sertraline": [
        ("RESTLESSNESS", "O", 1, "adverse_reactions (postmarketing): 'akathisia'; agitation is labelled; 'restlessness' "
                                 "itself is not named"),
    ],
    "isotretinoin": [
        ("MOOD SWINGS", "O", 0, "warnings: assess for 'mood disturbance' (broader term)"),
        ("EPISTAXIS", "O", 0, "adverse_reactions (Respiratory): 'epistaxis'"),
    ],
}

CODE = {v: k for k, v in C.items()}


def main(worksheets: Path, out: Path) -> None:
    v1 = [json.loads(l) for l in (HERE / "gold_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, notes = [], Counter()
    for drug in sorted({r["drug"] for r in v1}):
        top = {r["reaction"]: r for r in json.loads((worksheets / f"{drug}_top20.json").read_text(encoding="utf-8"))}
        label = json.loads((worksheets / f"{drug}_label.json").read_text(encoding="utf-8"))
        decisions = {r["reaction"]: (CODE[r["gold"]], int(r["ambiguous"]), r["evidence"], "kept from v1")
                     for r in v1 if r["drug"] == drug and r["reaction"] in top}
        for reaction, code, amb, ev in CHANGED.get(drug, []):
            assert reaction in decisions, (drug, reaction)
            decisions[reaction] = (code, amb, ev, "re-checked against the new label")
        for reaction, code, amb, ev in NEW.get(drug, []):
            assert reaction not in decisions, (drug, reaction)
            decisions[reaction] = (code, amb, ev, "new in the top 20")
        assert set(decisions) == set(top), (drug, set(decisions) ^ set(top))
        for reaction, t in top.items():
            code, amb, ev, origin = decisions[reaction]
            notes[origin] += 1
            rows.append({"drug": drug, "reaction": reaction, "gold": C[code], "ambiguous": bool(amb), "evidence": ev,
                         "origin": origin, "a": t["a"], "prr": t["prr"], "chi2": t["chi2"],
                         "label_set_id": label.get("set_id"), "label_effective": label.get("effective_time"),
                         "faers_search": "generic_name OR activesubstancename", "faers_data_updated": "2026-07-30",
                         "labelled_by": LABELLED_BY})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(len(rows), "rows;", dict(Counter(r["gold"] for r in rows)), "; ambiguous", sum(r["ambiguous"] for r in rows),
          ";", dict(notes))


if __name__ == "__main__":
    main(Path(sys.argv[1]), HERE / "gold_v2.jsonl")
