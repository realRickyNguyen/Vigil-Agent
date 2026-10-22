"""Builds eval/gold_v1.jsonl from the hand-made decisions below (see eval/LABELLING_RULES.md).

The decisions are the gold labels; this script only adds the screen numbers and label metadata from the
worksheets (top-20 screen rows and label JSON per drug, exported from Zetaris on 22 Oct 2026).

  python -I eval/build_gold_v1.py <worksheet_dir>
"""
import json
import sys
from collections import Counter
from pathlib import Path

C = {"O": "on_label", "I": "likely_indication_or_disease", "N": "not_meaningful", "S": "possible_new_signal"}
LABELLED_BY = "Claude (AI), 22 Oct 2026, per eval/LABELLING_RULES.md; not yet reviewed by a person"

# (reaction, category code, ambiguous, evidence)
GOLD = {
    "montelukast": [
        ("ASTHMA", "I", 0, "indications_and_usage: 'Prophylaxis and chronic treatment of asthma'"),
        ("WHEEZING", "I", 0, "asthma symptom; not described as a drug effect"),
        ("OBSTRUCTIVE AIRWAYS DISORDER", "I", 0, "airway obstruction is the treated condition (asthma, bronchoconstriction)"),
        ("DYSPNOEA", "I", 0, "asthma symptom; searched 'dyspn|shortness of breath': no hits"),
        ("SLEEP DISORDER DUE TO A GENERAL MEDICAL CONDITION", "O", 1,
         "boxed_warning: 'sleep disturbances'; the MedDRA term attributes it to a medical condition"),
        ("COUGH", "O", 0, "adverse_reactions: 'upper respiratory infection, fever, headache, pharyngitis, cough'"),
        ("SPUTUM DISCOLOURED", "I", 1,
         "searched 'sputum': no hits; sign of airway infection or exacerbation in the treated population"),
        ("FULL BLOOD COUNT ABNORMAL", "S", 1,
         "label names eosinophilia and thrombocytopenia only; narrower terms do not cover this vague term"),
        ("PRODUCTIVE COUGH", "O", 0, "adverse_reactions lists 'cough' (broader term)"),
        ("LOSS OF PERSONAL INDEPENDENCE IN DAILY ACTIVITIES", "N", 0, "MedDRA social-circumstance term"),
        ("SINUSITIS", "O", 0, "adverse_reactions: '... rhinorrhea, sinusitis, otitis'"),
        ("THERAPEUTIC PRODUCT EFFECT INCOMPLETE", "N", 0, "product/efficacy term"),
        ("PNEUMONIA", "O", 0, "adverse_reactions (pediatric list): '... varicella, pneumonia, dermatitis'"),
        ("CHEST DISCOMFORT", "I", 0, "asthma symptom (chest tightness); searched 'chest': no hits"),
        ("BRONCHITIS", "O", 0, "adverse_reactions: 'acute bronchitis'"),
        ("UPPER RESPIRATORY TRACT INFECTION", "O", 0, "adverse_reactions: 'upper respiratory infection'"),
        ("BLOOD COUNT ABNORMAL", "S", 1, "as FULL BLOOD COUNT ABNORMAL"),
        ("NASAL CONGESTION", "I", 0, "symptom of allergic rhinitis, an indication"),
        ("SEASONAL ALLERGY", "I", 0, "seasonal allergic rhinitis is an indication"),
        ("CHRONIC OBSTRUCTIVE PULMONARY DISEASE", "I", 1,
         "not an indication but a closely related airway disease of the treated population; "
         "searched 'COPD|chronic obstructive': no hits"),
    ],
    "atorvastatin": [
        ("TYPE 2 DIABETES MELLITUS", "O", 1,
         "warnings 5.4: 'Increases in HbA1c and fasting serum glucose levels have been reported with statins'; "
         "diabetes itself not named; litigation-heavy"),
        ("MYALGIA", "O", 0, "adverse_reactions: myalgia"),
        ("BLOOD CHOLESTEROL INCREASED", "I", 0, "the treated condition (hyperlipidaemia)"),
        ("MYOCARDIAL INFARCTION", "I", 0, "indications: 'To reduce the risk of: Myocardial infarction'"),
        ("CORONARY ARTERY DISEASE", "I", 0, "indications: coronary heart disease population"),
        ("BLOOD CREATINE PHOSPHOKINASE INCREASED", "O", 0, "warnings: 'elevated creatine kinase [CK]'"),
        ("PAIN IN EXTREMITY", "O", 0, "adverse_reactions: 'pain in extremity'"),
        ("MUSCULAR WEAKNESS", "O", 0, "warnings: myopathy 'muscle pain, tenderness, or weakness'"),
        ("RHABDOMYOLYSIS", "O", 0, "warnings 5.1 Myopathy and Rhabdomyolysis"),
        ("CEREBROVASCULAR ACCIDENT", "I", 1,
         "indications: reduce risk of stroke; warnings 5.5 only covers hemorrhagic stroke after recent hemorrhagic stroke"),
        ("MUSCLE SPASMS", "O", 0, "adverse_reactions: 'Muscle spasms'"),
        ("DRUG HYPERSENSITIVITY", "O", 0, "contraindications: 'Hypersensitivity reactions, including anaphylaxis'"),
        ("CHRONIC KIDNEY DISEASE", "S", 1,
         "label names renal failure secondary to rhabdomyolysis (acute) only; CKD is common in the treated population"),
        ("DIABETES MELLITUS", "O", 1, "as TYPE 2 DIABETES MELLITUS"),
        ("CORONARY ARTERY OCCLUSION", "I", 0, "coronary heart disease, the outcome the drug is given to prevent"),
        ("CARDIAC FAILURE CONGESTIVE", "I", 0, "indications: reduce 'hospitalization for congestive heart failure'"),
        ("MACULAR DEGENERATION", "S", 0, "label names 'vision blurred' only; searched 'macular|vision|eye'"),
        ("ASTHENIA", "O", 0, "adverse_reactions: 'fatigue', 'muscle fatigue'"),
        ("FALL", "S", 1, "searched 'fall': no hits; common in the older treated population"),
        ("RENAL FAILURE", "O", 0, "warnings: 'renal failure secondary to rhabdomyolysis'"),
    ],
    "metformin": [
        ("LACTIC ACIDOSIS", "O", 0, "boxed_warning: 'WARNING: LACTIC ACIDOSIS'"),
        ("BLOOD GLUCOSE INCREASED", "I", 0, "measure of the treated condition (type 2 diabetes)"),
        ("ACUTE KIDNEY INJURY", "O", 0,
         "warnings 5.4: 'Acute Renal Failure ... postmarketing reports of worsening renal function'"),
        ("HYPOGLYCAEMIA", "O", 0, "warnings: 'Hypoglycemia with Concomitant Use with Insulin or Insulin Secretagogues'"),
        ("METABOLIC ACIDOSIS", "O", 0, "lactic acidosis is a metabolic acidosis (boxed warning)"),
        ("GLYCOSYLATED HAEMOGLOBIN INCREASED", "I", 0, "measure of the treated condition"),
        ("DIABETIC KETOACIDOSIS", "I", 0, "complication of diabetes; label names it only as a contraindication"),
        ("BLOOD GLUCOSE DECREASED", "O", 0, "hypoglycemia warning"),
        ("DIABETES MELLITUS INADEQUATE CONTROL", "I", 0, "the treated condition"),
        ("WEIGHT DECREASED", "S", 0, "searched 'weight': no hits in this (combination) label"),
        ("HYPERKALAEMIA", "S", 1,
         "searched 'hyperkal|potassium': no hits; often secondary to renal failure in diabetes"),
        ("DIARRHOEA", "O", 0, "adverse_reactions: 'diarrhea'"),
        ("HYPERGLYCAEMIA", "I", 0, "the treated condition"),
        ("BLOOD GLUCOSE ABNORMAL", "I", 0, "measure of the treated condition"),
        ("DIABETES MELLITUS", "I", 0, "the treated condition"),
        ("BLOOD GLUCOSE FLUCTUATION", "I", 0, "measure of the treated condition"),
        ("DECREASED APPETITE", "S", 0, "searched 'appetite|anorexia': no hits"),
        ("VOMITING", "O", 0, "adverse_reactions: 'nausea/vomiting'"),
        ("IMPAIRED GASTRIC EMPTYING", "I", 1,
         "diabetic gastroparesis is a complication of diabetes; reports may come from co-prescribed GLP-1 drugs"),
        ("RENAL FAILURE ACUTE", "O", 0, "warnings 5.4 'Acute Renal Failure'"),
    ],
    "sertraline": [
        ("SEROTONIN SYNDROME", "O", 0, "warnings: 'Serotonin Syndrome'"),
        ("DEPRESSION", "O", 1,
         "treated condition, but label warns of clinical worsening and lists depression among adverse events"),
        ("ANXIETY", "O", 0, "warnings: 'anxiety, agitation, panic attacks, insomnia'"),
        ("SUICIDAL IDEATION", "O", 0, "boxed_warning: suicidal thinking and behavior"),
        ("INTENTIONAL SELF-INJURY", "O", 0, "boxed_warning: suicidal behavior"),
        ("DRUG INTERACTION", "N", 1, "no named clinical event; label has interaction precautions"),
        ("SUICIDE ATTEMPT", "O", 0, "boxed_warning: suicidality"),
        ("INTENTIONAL OVERDOSE", "O", 1, "warnings: prescribe small quantities 'to reduce the risk of overdose'"),
        ("TREMOR", "O", 0, "adverse_reactions: Tremor"),
        ("INSOMNIA", "O", 0, "adverse_reactions and warnings: insomnia"),
        ("COMPLETED SUICIDE", "O", 0, "boxed_warning: suicidality"),
        ("AGITATION", "O", 0, "warnings: agitation"),
        ("CONFUSIONAL STATE", "O", 0, "precautions: 'confusion'"),
        ("SOMNOLENCE", "O", 0, "adverse_reactions: Somnolence"),
        ("SEXUAL DYSFUNCTION", "O", 0, "adverse_reactions: ejaculation failure, libido decreased"),
        ("FALL", "O", 0, "precautions (hyponatremia): 'unsteadiness, which may lead to falls'"),
        ("PANIC ATTACK", "O", 0, "warnings: 'panic attacks'"),
        ("PARANOIA", "O", 0, "adverse_reactions: 'paranoid reaction'"),
        ("DRUG ABUSE", "N", 1, "misuse circumstance; searched 'abuse|dependence': no hits"),
        ("APATHY", "O", 0, "adverse_reactions: 'apathy'"),
    ],
    "isotretinoin": [
        ("INFLAMMATORY BOWEL DISEASE", "O", 0,
         "warnings: 'associated with inflammatory bowel disease (including regional ileitis)'"),
        ("UNINTENDED PREGNANCY", "N", 1, "exposure circumstance; the boxed warning is about pregnancy"),
        ("COLITIS ULCERATIVE", "O", 0, "warnings: inflammatory bowel disease; adverse_reactions: colitis"),
        ("PREGNANCY", "N", 1, "exposure circumstance; the boxed warning is about pregnancy"),
        ("ABORTION INDUCED", "N", 1, "procedure following pregnancy exposure; label names spontaneous abortion only"),
        ("IRRITABLE BOWEL SYNDROME", "S", 0, "searched 'irritable bowel': no hits"),
        ("DEPRESSION", "O", 0, "warnings: 'may cause depression, psychosis'"),
        ("BLOOD TRIGLYCERIDES INCREASED", "O", 0, "warnings: Lipids, hypertriglyceridemia"),
        ("MOOD ALTERED", "O", 0, "warnings: 'mood disturbance'"),
        ("SUICIDAL IDEATION", "O", 0, "warnings: 'suicidal ideation'"),
        ("CROHN^S DISEASE", "O", 0, "warnings: inflammatory bowel disease 'including regional ileitis'"),
        ("EXPOSURE DURING PREGNANCY", "N", 0, "exposure circumstance"),
        ("DRUG EXPOSURE DURING PREGNANCY", "N", 0, "exposure circumstance"),
        ("DRY SKIN", "O", 0, "adverse_reactions: 'dry skin'"),
        ("ADVERSE DRUG REACTION", "N", 0, "non-specific reporting term"),
        ("TREATMENT NONCOMPLIANCE", "N", 0, "use/compliance term"),
        ("INTESTINAL OBSTRUCTION", "S", 1, "searched 'obstruction': no hits; possible complication of labelled IBD"),
        ("RECTAL HAEMORRHAGE", "O", 0, "warnings: 'rectal bleeding'"),
        ("COLITIS", "O", 0, "adverse_reactions: 'colitis'"),
        ("BLOOD CHOLESTEROL INCREASED", "O", 0, "warnings: 'about 7% showed an increase in cholesterol levels'"),
    ],
}


def main(worksheets: Path, out: Path) -> None:
    rows = []
    for drug, items in GOLD.items():
        top = {r["reaction"]: r for r in json.loads((worksheets / f"{drug}_top20.json").read_text(encoding="utf-8"))}
        label = json.loads((worksheets / f"{drug}_label.json").read_text(encoding="utf-8"))
        names = {i[0] for i in items}
        assert names == set(top), (drug, names ^ set(top))
        for reaction, code, amb, evidence in items:
            t = top[reaction]
            rows.append({"drug": drug, "reaction": reaction, "gold": C[code], "ambiguous": bool(amb),
                         "evidence": evidence, "a": t["a"], "prr": t["prr"], "chi2": t["chi2"],
                         "label_set_id": label.get("set_id"), "label_effective": label.get("effective_time"),
                         "faers_data_updated": "2026-07-30", "labelled_by": LABELLED_BY})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(len(rows), "rows;", dict(Counter(r["gold"] for r in rows)), "; ambiguous", sum(r["ambiguous"] for r in rows))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(__file__).resolve().parent / "gold_v1.jsonl")
