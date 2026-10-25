"""Label text helpers for sentence lookup, per-reaction retrieval and the code search of every section.
Pure functions, no I/O.

Agents get the few label sentences that mention words from each reaction, instead of a truncated
copy of the whole label: shorter prompts (fewer Nightshift timeouts) and nothing cut off at the end.
Before any model call, search() also looks for each reaction's name in every section the Data Clerk
fetched, so a "not found" can say what was searched."""
import math
import re

META = ("effective_time", "set_id")
INDICATION = "indications_and_usage"
CONTRAINDICATIONS = "contraindications"
# Sections that describe what the drug may cause or worsen.
SAFETY = ("boxed_warning", "warnings_and_cautions", "warnings", "precautions", "adverse_reactions")
# Sections searched for a literal reaction name, after the indications section.
SECTIONS = SAFETY + (CONTRAINDICATIONS,)
# Patient labelling. Effect statements too, so they can support coverage. Sertraline's "panic attacks" is only
# in its Medication Guide. The two leaflets also say who should not take the drug and what to tell the doctor
# first, so only their side-effect parts count (leaflet_parts).
PATIENT = ("information_for_patients", "spl_medguide", "spl_patient_package_insert")
LEAFLETS = ("spl_medguide", "spl_patient_package_insert")
# The only sections that can support coverage.
EFFECT = SAFETY + PATIENT
# The drug's expected pharmacological effects (Ozempic "reduces body weight"). Shown and quoted, never coverage.
PHARMACOLOGY = ("mechanism_of_action", "pharmacodynamics")
# Never coverage on their own, since they give a condition the drug must not be used in, what other drugs do, or
# drug levels.
NOT_COVERAGE = (CONTRAINDICATIONS, "drug_interactions", "pharmacokinetics")
ORDER = (INDICATION,) + EFFECT + PHARMACOLOGY + NOT_COVERAGE
KIND = {INDICATION: "indication", **{s: "effect" for s in EFFECT}, **{s: "expected_effect" for s in PHARMACOLOGY}}

# MedDRA uses British spelling; US labels do not.
UK_US = [("oesophag", "esophag"), ("oedem", "edem"), ("haemorrh", "hemorrh"), ("haem", "hem"),
         ("anaem", "anem"), ("diarrhoea", "diarrhea"), ("dyspnoea", "dyspnea"), ("paed", "ped"),
         ("tumour", "tumor"), ("leukaem", "leukem"), ("ischaem", "ischem"), ("oestr", "estr"),
         ("faec", "fec"), ("glycaem", "glycem"), ("colour", "color"), ("behaviour", "behavior")]
STOP = {"a", "an", "and", "of", "the", "to", "due", "in", "on", "with", "without", "general", "medical",
        "condition", "disorder", "abnormal", "increased", "decreased", "nos", "syndrome", "type", "other",
        "site", "full", "count", "test", "level"}
# MedDRA lab and vital-sign terms whose label wording shares no word with them: on 23 Oct both agents were shown
# blood-lactate sentences for metformin BLOOD GLUCOSE DECREASED instead of the hypoglycemia warning.
# (pattern on the US-spelled, lower-case term, extra word prefixes to search for)
SYNONYMS = [
    (r"glucose (decreased|low)", ["hypoglyc"]), (r"glucose (increased|high)", ["hyperglyc"]),
    (r"potassium (decreased|low)", ["hypokal"]), (r"potassium (increased|high)", ["hyperkal"]),
    (r"sodium (decreased|low)", ["hyponat"]), (r"sodium (increased|high)", ["hypernat"]),
    (r"calcium (decreased|low)", ["hypocalc"]), (r"calcium (increased|high)", ["hypercalc"]),
    (r"magnesium (decreased|low)", ["hypomag"]),
    (r"platelet count decreased", ["thrombocytop"]),
    (r"(white blood cell|leukocyte) count decreased", ["leukop", "neutrop"]),
    (r"neutrophil count decreased", ["neutrop", "agranul"]),
    (r"(hemoglobin|haematocrit|hematocrit|red blood cell count) decreased", ["anemi"]),
    (r"blood pressure (increased|high)", ["hypertens"]), (r"blood pressure (decreased|low)", ["hypotens"]),
    (r"heart rate (increased|high)", ["tachycard"]), (r"heart rate (decreased|low)", ["bradycard"]),
    (r"(transaminase|aminotransferase|hepatic enzyme|liver function test)s? (increased|abnormal)",
     ["transam", "hepat", "liver"]),
]
SYNONYM_WEIGHT = 2
# Phrases a label uses for exactly the same event as a MedDRA term, for the code search (pattern on the US-spelled,
# lower-case term, phrases). On 24 Oct sertraline WITHDRAWAL SYNDROME went to review next as not found, though its
# label covers "discontinuation syndrome".
NAMED_AS = [(r"^(drug )?withdrawal (syndrome|symptoms?)$|^(antidepressant )?discontinuation syndrome$",
             ["discontinuation syndrome"]),
            (r"^acute kidney injury$", ["acute renal failure"])]
# Words in a MedDRA term that give a direction, and the words a label uses for a change that way. A term with a
# direction also matches a sentence that has all its other words and one of these ("reduces body weight" for
# WEIGHT DECREASED). Verbs and nouns only, because "when blood glucose is high" describes a state, not an effect.
DIRECTIONS = {"decreased": ("decreas", "reduc", "lower", "loss", "lose", "losing", "lost", "declin", "diminish"),
              "reduced": ("decreas", "reduc", "lower", "loss", "lose", "losing", "lost", "declin", "diminish"),
              "increased": ("increas", "rais", "elevat", "gain"), "elevated": ("increas", "rais", "elevat", "gain")}
# Words left out when every word of a term must appear in one sentence. Much shorter than STOP, as FULL BLOOD COUNT
# ABNORMAL must not match any sentence that says "blood".
GRAMMAR = {"a", "an", "and", "of", "the", "to", "due", "in", "on", "with", "without", "nos", "or", "by", "for"}
EXCERPTS_PER_REACTION = 3
SENTENCE_CHARS = 300
INDICATION_CHARS = 600
BOXED_CHARS = 1500


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def us(word: str) -> str:
    for uk, am in UK_US:
        word = word.replace(uk, am)
    return word


def stems(reaction: str) -> list[str]:
    """Word prefixes for a MedDRA term: 'NIGHTMARE' -> ['nightm'], 'ABNORMAL DREAMS' -> ['dream']."""
    return list(dict.fromkeys(word_stems(reaction, STOP) + synonym_stems(reaction)))


def word_stems(reaction: str, skip: set[str]) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", us(norm(reaction))):
        if len(w) < 3 or w in skip:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w[:6] if len(w) > 6 else w)
    return out


def synonym_stems(reaction: str) -> list[str]:
    term = us(norm(reaction))
    return [extra for pattern, extras in SYNONYMS if re.search(pattern, term) for extra in extras]


# Synonym stems too broad to name a reaction on their own ("hepatic impairment" is no liver enzyme rise).
BROAD_SYNONYMS = {"hepat", "liver"}


def related_in(reaction: str, text: str) -> str | None:
    """The first word in text that a curated synonym stem names (SYNONYMS, less BROAD_SYNONYMS), such as
    "hypoglycemia" for BLOOD GLUCOSE DECREASED. On 25 Oct, without this, semaglutide's search line showed only the
    pharmacology's glucose lowering and the Analyst marked the hypoglycaemia warning's reaction unclear."""
    t = us(norm(text))
    for stem in synonym_stems(reaction):
        m = re.search(rf"\b{re.escape(stem)}[a-z]*", t) if stem not in BROAD_SYNONYMS else None
        if m:
            return m.group(0)
    return None


def sections(label: dict) -> dict:
    return {k: v for k, v in label.items() if k not in META and v}


def sentences(label: dict) -> list[tuple[str, str]]:
    return [(sec, s.strip()) for sec, text in sections(label).items()
            for s in re.split(r"(?<=[.;])\s+", text) if len(s.strip()) > 10]


def window(t: str, start: int, stop: int, i: int, n: int, limit: int = SENTENCE_CHARS) -> str:
    """t[start:stop] if it fits in `limit` characters, otherwise `limit` characters of it that contain t[i:i + n],
    marked with '...' where cut. Adverse-reaction lists are one long sentence, so cutting from the start can
    lose the very term a quote or excerpt is for (22 Oct: PNEUMONIA in montelukast's paediatric list)."""
    if stop - start <= limit:
        return t[start:stop]
    limit -= 6  # room for both "..." marks, so a quote never exceeds the original limit
    lo = max(start, min(i - (limit - n) // 2, stop - limit))
    hi = min(stop, lo + limit)
    return ("..." if lo > start else "") + t[lo:hi] + ("..." if hi < stop else "")


def label_sentence(text: str, term: str) -> str | None:
    """The sentence in text that contains term (case-insensitive), or None. A long sentence is cut to
    SENTENCE_CHARS around the term, so the quote always contains it: on 23 Oct metformin's DIARRHOEA quote
    was the first 300 characters of a long adverse-reactions sentence and never said diarrhea."""
    t, n = norm(text), norm(term)
    i = t.find(n) if term else -1
    if i < 0:
        return None
    dot = t.rfind(". ", 0, i)
    start = dot + 2 if dot >= 0 else 0
    end = t.find(". ", i)
    return window(t, start, end + 1 if end >= 0 else len(t), i, len(n))


def around(sentence: str, words: list[str]) -> str:
    """At most SENTENCE_CHARS of a sentence, around the first of the given word stems it contains, trying them in
    the order given. retrieve() passes the strongest first, so a common word such as "blood" cannot pull the
    window away from "hypoglyc"."""
    low = sentence.lower()
    i, n = next(((m.start(), len(w)) for w in words for m in [re.search(rf"\b{re.escape(w)}", low)] if m), (0, 0))
    return window(sentence, 0, len(sentence), i, n)


# Standard Medication Guide and Patient Information headings (21 CFR 208.20). A quoted heading is a cross-reference
# ('See “ What are the possible side effects of ...? ”'), not the start of a part (see CROSS_REFERENCE).
LEAFLET_HEADING = re.compile(
    r"(?:what (?:is|are) [^?]{1,150}\?|who should not (?:take|use)[^?]{0,100}\?|"
    r"do not (?:take|use) [^.:?]{1,100} if you[^.:?]{0,40}:|what should i tell [^?]{1,150}\?|"
    r"before (?:you )?(?:take|taking|use|using|start|starting|receiving)[^.:?]{0,120}"
    r"(?:tell|talk to) your (?:healthcare provider|doctor)[^.:?]{0,100}[.:?]|"
    r"how should i (?:take|use|store) [^?]{1,120}\?|what should i avoid [^?]{1,120}\?|general information about [^.]{1,150}\.)",
    re.I)
EFFECT_HEADING = re.compile(r"what is the most important information|what are the (?:possible )?side effects", re.I)
# Text just before a heading that makes it a cross-reference, such as an opening quote (with or without a space)
# or "See".
CROSS_REFERENCE = re.compile(r"(?:[\"“‘']|\bsee)\s*$", re.I)
LIMITATION = re.compile(r"limitations? of use", re.I)
# A numbered subsection heading ("1.2 Glycemic Control"), not a number in the text ("approximately 12.5 L").
SUBSECTION = re.compile(r"\b1\.\d+\s+[A-Z][a-z]")
# The next indication after a Limitation of Use ("WEGOVY is ... indicated in combination ..."); "not indicated" is
# part of the limitation.
INDICATED = re.compile(r"(?<!not )\bindicated\b", re.I)
PHARMACOLOGY_HEADING = re.compile(r"\b12\.\d+\s+(Mechanism of Action|Pharmacodynamics|Pharmacokinetics)\b", re.I)
PHARMACOLOGY_PARTS = {"mechanism of action": "mechanism_of_action", "pharmacodynamics": "pharmacodynamics",
                      "pharmacokinetics": "pharmacokinetics"}
WINDOW = 6  # words between a direction word and each of the term's other words


def leaflet_parts(text: str) -> tuple[str, str]:
    """(side-effect parts, other parts) of a Medication Guide or patient leaflet. Only "What is the most important
    information" and "What are the possible side effects" describe effects. The rest says what the drug treats, who
    should not take it and what to tell the doctor first, which reads like a contraindication (metformin's leaflet
    says "Do not take ... if you have kidney problems"). A leaflet without these headings counts as other parts.
    The side-effect parts can still list risk factors, which is why the rules don't settle coverage from them."""
    effect, other = [], []
    current, start = other, 0  # text before the first heading is an introduction
    for m in LEAFLET_HEADING.finditer(text):
        if CROSS_REFERENCE.search(text[max(0, m.start() - 8):m.start()]):
            continue
        current.append(text[start:m.start()])
        current, start = (effect if EFFECT_HEADING.match(m.group(0)) else other), m.start()
    current.append(text[start:])
    return " ".join(effect).strip(), " ".join(other).strip()


def indication_parts(text: str) -> tuple[str, str]:
    """(indications, Limitation of Use passages). A Limitation of Use names a condition the drug is not for (Invokana's
    diabetic ketoacidosis before its 2015 warning), so it is neither the treated condition nor coverage. A passage
    runs to the next numbered subsection, or to the sentence naming the next indication, or the end of the section.
    Text in doubt stays with the indications, where it counts as before."""
    ind, lim, pos = [], [], 0
    for m in LIMITATION.finditer(text):
        if m.start() < pos:
            continue
        nxt, again = SUBSECTION.search(text, m.end()), INDICATED.search(text, m.end())
        stop = nxt.start() if nxt else len(text)
        if again and again.start() < stop:
            # Cut where the sentence naming the next indication starts; with no sentence before it, there's no passage.
            cut = text.rfind(". ", m.end(), again.start())
            stop = cut + 2 if cut >= 0 else m.end()
        ind.append(text[pos:m.start()])
        lim.append(text[m.start():stop])
        pos = stop
    ind.append(text[pos:])
    return " ".join(ind).strip(), " ".join(lim).strip()


def clinical_pharmacology_parts(text: str) -> dict:
    """mechanism_of_action, pharmacodynamics and pharmacokinetics cut from a clinical pharmacology section by its
    numbered headings, for labels where openFDA did not split them (atorvastatin's and metformin's chosen labels on
    25 Oct). A part is named by its heading's title, not its number. Cross-references such as "(12.3)" and numbers
    such as "12.5 L" are not headings."""
    heads = list(PHARMACOLOGY_HEADING.finditer(text))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        nxt = re.search(r"\b12\.\d+\s+[A-Z][a-z]", text[m.end():end])
        out.setdefault(PHARMACOLOGY_PARTS[m.group(1).lower()],
                       text[m.start():m.end() + nxt.start() if nxt else end].strip())
    return out


def parts(label: dict) -> list[tuple[str, str, str, str]]:
    """(section, part, kind, text) for each section of the label, indications first, then effect, pharmacology and
    other sections. kind is "indication", "effect", "expected_effect" or "not_coverage". The indications give their
    Limitation of Use passages, and the leaflets everything but their side-effect parts, to "not_coverage" parts."""
    secs = sections(label)
    out = []
    for sec in sorted(secs, key=lambda s: ORDER.index(s) if s in ORDER else len(ORDER)):
        text = secs[sec]
        if sec == INDICATION:
            ind, lim = indication_parts(text)
            out += [(sec, "", "indication", ind), (sec, "Limitation of Use", "not_coverage", lim)]
        elif sec in LEAFLETS:
            eff, other = leaflet_parts(text)
            out += [(sec, "side effects", "effect", eff), (sec, "not a side-effect part", "not_coverage", other)]
        else:
            out.append((sec, "", KIND.get(sec, "not_coverage"), text))
    return [p for p in out if p[3]]


def effect_text(label: dict, section: str | None = None) -> str:
    """The text that can support coverage, from one effect section or from all of them."""
    return " ".join(t for s, _, k, t in parts(label) if k == "effect" and (section is None or s == section))


def name_in(reaction: str, text: str) -> str | None:
    """The words text uses to name the reaction, by its MedDRA name (singular or plural) or a NAMED_AS phrase."""
    term, t = us(norm(reaction)), us(norm(text))
    for phrase in dict.fromkeys([term] + [p for pattern, extra in NAMED_AS if re.search(pattern, term) for p in extra]):
        m = re.search(rf"\b{re.escape(phrase)}(s|es)?\b", t)
        if m:
            return m.group(0)
    return None


def change_in(reaction: str, text: str) -> str | None:
    """For a term with a direction (WEIGHT DECREASED), the first sentence of text with a word for that change and,
    within WINDOW words of it, every other word of the term, as in "reduces body weight". None for other terms."""
    words = us(norm(reaction)).split()
    ways = next((DIRECTIONS[w] for w in words if w in DIRECTIONS), None)
    rest = word_stems(reaction, GRAMMAR | set(DIRECTIONS))
    if not ways or not rest:
        return None
    for s in re.split(r"(?<=[.;])\s+", text):
        tokens = re.findall(r"[a-z]+", us(norm(s)))
        for i, w in enumerate(tokens):
            near = tokens[max(0, i - WINDOW):i + WINDOW + 1]
            if w.startswith(ways) and all(any(t.startswith(r) for t in near) for r in rest):
                return around(s.strip(), list(ways))
    return None


def find_term(reaction: str, label: dict, kinds: tuple[str, ...] = ("indication", "effect"),
              only: tuple[str, ...] | None = None) -> tuple[str, str] | None:
    """(section, matched text) where a part of the given kinds names the reaction (name_in), in parts() order. Rules
    ask for the indications and the effect sections separately, so a treated disease is not mistaken for a warning.
    only: these sections alone."""
    for sec, _, kind, text in parts(label):
        hit = name_in(reaction, text) if kind in kinds and (only is None or sec in only) else None
        if hit:
            return sec, hit
    return None


def search(reaction: str, label: dict) -> dict:
    """Where the label names the reaction, part by part, done in code before any model call. "named_in" lists the
    parts that make "not found" wrong, which are a name in the indications or an effect part, a change or a related
    term (a curated synonym) in an effect part, or a change in the pharmacology (an expected effect of the drug).
    The rest is shown, never counted."""
    found, searched = [], []
    for sec, part, kind, text in parts(label):
        searched.append(sec)
        name = name_in(reaction, text)
        change = None if name else change_in(reaction, text)
        related = related_in(reaction, text) if kind == "effect" and not (name or change) else None
        if name or change or related:
            word = name or related
            quote = (label_sentence(text, word) or word) if word else change
            found.append({"section": sec, "part": part, "kind": kind,
                          "how": "name" if name else "change" if change else "related", "match": word,
                          "quote": quote})
    named = [h for h in found if (h["kind"] == "indication" and h["how"] == "name") or h["kind"] == "effect"
             or (h["kind"] == "expected_effect" and h["how"] == "change")]
    out = {"searched": list(dict.fromkeys(searched)), "found": found,
           "named_in": [where(h) for h in named]}
    out["summary"] = explain(out)
    return out


def where(hit: dict) -> str:
    return f"{hit['section']} ({hit['part']})" if hit["part"] else hit["section"]


def explain(s: dict, searched: bool = True) -> str:
    """Plain sentences for the prompts and the dossier, saying where the label names the reaction, what does not
    count and what was searched. An expected effect is quoted."""
    by = lambda kind, how=None: [h for h in s["found"] if h["kind"] == kind and how in (None, h["how"])]  # noqa: E731
    out = []
    if by("indication"):
        out.append(f"Named in the indications ({', '.join(where(h) for h in by('indication'))}), the treated "
                   f"condition.")
    if by("effect", "name"):
        out.append(f"Named in sections that can support coverage: {', '.join(where(h) for h in by('effect', 'name'))}.")
    if by("effect", "change"):
        out.append(f"Described in other words in sections that can support coverage: "
                   f"{', '.join(where(h) for h in by('effect', 'change'))}.")
    if by("effect", "related"):
        terms = list(dict.fromkeys(f'"{h["match"]}"' for h in by("effect", "related")))
        out.append(f"Named by a related term ({', '.join(terms)}) in sections that can support coverage: "
                   f"{', '.join(where(h) for h in by('effect', 'related'))}.")
    also = "Also an expected" if by("effect") else "Expected"
    out += [f"{also} effect of the drug ({h['section']}, not an adverse effect, never coverage): \"{h['quote']}\""
            for h in by("expected_effect", "change")]
    if by("expected_effect", "name"):
        out.append(f"Mentioned in the pharmacology ({', '.join(where(h) for h in by('expected_effect', 'name'))}), "
                   f"which describes how the drug works; check whether it says the drug causes it.")
    if by("not_coverage"):
        out.append(f"{'Also named' if len(by('not_coverage')) < len(s['found']) else 'Named only'} where it never counts "
                   f"as coverage: {', '.join(where(h) for h in by('not_coverage'))}.")
    if not s["found"]:
        # Said plainly because on 25 Oct the Analyst read "not named" as a reason to call montelukast CHEST DISCOMFORT
        # a clinical event, skipping the treated-condition question it should decide first.
        out.append("Not named in any section searched. That is about the label only, not whether it is the treated "
                   "condition.")
    if searched:
        out.append(f"Searched {len(s['searched'])} sections: {', '.join(s['searched'])}.")
    return " ".join(out)


def retrieve(reaction: str, label: dict, k: int = EXCERPTS_PER_REACTION) -> list[tuple[str, str]]:
    """Top k (section, sentence) pairs mentioning words from the reaction. Rarer words count for more,
    so 'SUICIDAL IDEATION' ranks sentences about suicidality above ones that only share a common word."""
    sents = sentences(label)
    words = [set(re.findall(r"[a-z]+", us(norm(s)))) for _, s in sents]
    scored = []
    # A synonym names the clinical concept itself, so it counts double: on metformin's label "blood" and
    # "hypoglyc" each hit 5 sentences, and the tie went to the lactate sentences, which come first.
    synonyms, weights = set(synonym_stems(reaction)), {}
    for st in stems(reaction):
        hits = [i for i, ws in enumerate(words) if any(w.startswith(st) for w in ws)]
        weights[st] = (SYNONYM_WEIGHT if st in synonyms else 1) / math.log(2 + len(hits))
        scored += [(i, weights[st]) for i in hits]
    score: dict[int, float] = {}
    for i, w in scored:
        score[i] = score.get(i, 0) + w
    out, seen = [], set()
    for i in sorted(score, key=lambda i: -score[i]):
        key = norm(sents[i][1])
        if key not in seen:  # labels repeat sentences across sections
            seen.add(key)
            out.append(i)
        if len(out) == k:
            break
    strongest = sorted(weights, key=lambda st: -weights[st])  # each excerpt centres on its strongest word
    return [(sents[i][0], around(sents[i][1], strongest)) for i in sorted(out)]


def excerpt_block(reactions: list[str], label: dict, label_qid: str | None) -> str:
    """Prompt text with the indication, what code searched, then for each reaction where the search named it and the
    retrieved sentences. Retrieval reads the sections it always has (the newer ones are long and mostly not
    coverage); what the search finds elsewhere is quoted, at most two parts per reaction."""
    if not sections(label):
        return "Current label: (no current label found)"
    lines = []
    ind = sections(label).get(INDICATION)
    if ind:
        lines.append(f"Indication (label section {INDICATION}, query {label_qid}): {ind[:INDICATION_CHARS]}")
    # Word matching misses synonyms (MedDRA 'NIGHTMARE' vs the label's 'dream abnormalities'), so the
    # boxed warning, the label's main safety statement, always goes in.
    boxed = sections(label).get("boxed_warning")
    if boxed:
        lines.append(f"\nBoxed warning (label section boxed_warning): {boxed[:BOXED_CHARS]}")
    searched = list(dict.fromkeys(sec for sec, *_ in parts(label)))
    lines.append(f"\nCode searched {len(searched)} label sections for each reaction's name: {', '.join(searched)}. "
                 f"Only warning, adverse-reaction and patient sections can support coverage (of a Medication Guide or "
                 f"leaflet, only its side-effect parts); pharmacology describes expected effects.")
    lines.append(f"\nLabel sentences that share words with each reaction (query {label_qid}, effective "
                 f"{label.get('effective_time', 'unknown')}). The label may also describe a reaction in other "
                 f"words that are not shown here.")
    core = {k: v for k, v in label.items() if k in (INDICATION,) + SECTIONS}
    for r in reactions:
        hits, found = retrieve(r, core), search(r, label)
        lines.append(f"- {r}:" + ("" if hits else " (no label sentence shares its words)"))
        lines.append(f"  Code search: {explain(found, searched=False)}")
        lines += [f"  [{sec}] {s}" for sec, s in hits]
        # explain() already quotes an expected effect. Also quoted here are effect parts the retrieved sentences miss,
        # and a pharmacology sentence that names the reaction, so the model can see what it says.
        quoted = [h for h in found["found"] if (h["kind"] == "effect" or h["kind"] == "expected_effect"
                                                 and h["how"] == "name")
                  and not any(sec == h["section"] and h["match"] and h["match"] in us(norm(s)) for sec, s in hits)][:2]
        note = lambda h: h["part"] or ("pharmacology, not coverage" if h["kind"] == "expected_effect" else "")  # noqa: E731
        lines += [f"  [{h['section']}] " + (f"({note(h)}) " if note(h) else "") + h["quote"] for h in quoted]
    return "\n".join(lines)
