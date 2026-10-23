"""Label text helpers: sentence lookup and per-reaction retrieval. Pure functions, no I/O.

Agents get the few label sentences that mention words from each reaction, instead of a truncated
copy of the whole label: shorter prompts (fewer Nightshift timeouts) and nothing cut off at the end."""
import math
import re

META = ("effective_time", "set_id")
INDICATION = "indications_and_usage"
# Sections searched for a literal reaction name, after the indications section.
SECTIONS = ("boxed_warning", "warnings_and_cautions", "warnings", "precautions", "adverse_reactions",
            "contraindications")

# MedDRA uses British spelling; US labels do not.
UK_US = [("oesophag", "esophag"), ("oedem", "edem"), ("haemorrh", "hemorrh"), ("haem", "hem"),
         ("anaem", "anem"), ("diarrhoea", "diarrhea"), ("dyspnoea", "dyspnea"), ("paed", "ped"),
         ("tumour", "tumor"), ("leukaem", "leukem"), ("ischaem", "ischem"), ("oestr", "estr"),
         ("faec", "fec"), ("glycaem", "glycem"), ("colour", "color"), ("behaviour", "behavior")]
STOP = {"a", "an", "and", "of", "the", "to", "due", "in", "on", "with", "without", "general", "medical",
        "condition", "disorder", "abnormal", "increased", "decreased", "nos", "syndrome", "type", "other",
        "site", "full", "count", "test", "level"}
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
    out = []
    for w in re.findall(r"[a-z]+", us(norm(reaction))):
        if len(w) < 3 or w in STOP:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w[:6] if len(w) > 6 else w)
    return list(dict.fromkeys(out))


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
    lo = max(start, min(i - (limit - n) // 2, stop - limit))
    hi = min(stop, lo + limit)
    return ("..." if lo > start else "") + t[lo:hi] + ("..." if hi < stop else "")


def label_sentence(text: str, term: str) -> str | None:
    """The sentence in text that contains term (case-insensitive), or None. A long sentence is cut around the term."""
    t = norm(text)
    i = t.find(norm(term)) if term else -1
    if i < 0:
        return None
    dot = t.rfind(". ", 0, i)
    start = dot + 2 if dot >= 0 else 0
    end = t.find(". ", i)
    return window(t, start, end + 1 if end >= 0 else len(t), i, len(norm(term)))


def around(sentence: str, words: list[str]) -> str:
    """At most SENTENCE_CHARS of a sentence, around the first of the given word stems it contains."""
    low = sentence.lower()
    hits = sorted((m.start(), len(w)) for w in words for m in [re.search(rf"\b{re.escape(w)}", low)] if m)
    i, n = hits[0] if hits else (0, 0)
    return window(sentence, 0, len(sentence), i, n)


def find_term(reaction: str, label: dict) -> tuple[str, str] | None:
    """(section, matched text) where the label names the reaction itself, singular or plural.
    The indications section is checked first, so a treated disease is not mistaken for a warning."""
    pattern = re.compile(rf"\b{re.escape(us(norm(reaction)))}(s|es)?\b")
    secs = sections(label)
    for sec in (INDICATION,) + SECTIONS + tuple(k for k in secs if k not in SECTIONS and k != INDICATION):
        m = pattern.search(us(norm(secs.get(sec, ""))))
        if m:
            return sec, m.group(0)
    return None


def named_in_label(reaction: str, label: dict) -> bool:
    return find_term(reaction, label) is not None


def retrieve(reaction: str, label: dict, k: int = EXCERPTS_PER_REACTION) -> list[tuple[str, str]]:
    """Top k (section, sentence) pairs mentioning words from the reaction. Rarer words count for more,
    so 'SUICIDAL IDEATION' ranks sentences about suicidality above ones that only share a common word."""
    sents = sentences(label)
    words = [set(re.findall(r"[a-z]+", us(norm(s)))) for _, s in sents]
    scored = []
    for st in stems(reaction):
        hits = [i for i, ws in enumerate(words) if any(w.startswith(st) for w in ws)]
        weight = 1 / math.log(2 + len(hits))
        scored += [(i, weight) for i in hits]
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
    sts = stems(reaction)
    return [(sents[i][0], around(sents[i][1], sts)) for i in sorted(out)]


def excerpt_block(reactions: list[str], label: dict, label_qid: str | None) -> str:
    """Prompt text: the indication, then the retrieved sentences for each reaction."""
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
    lines.append(f"\nLabel sentences that share words with each reaction (query {label_qid}, effective "
                 f"{label.get('effective_time', 'unknown')}). The label may also describe a reaction in other "
                 f"words that are not shown here.")
    for r in reactions:
        hits = retrieve(r, label)
        lines.append(f"- {r}:" + ("" if hits else " (no label sentence shares its words)"))
        lines += [f"  [{sec}] {s}" for sec, s in hits]
    return "\n".join(lines)
