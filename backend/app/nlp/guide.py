"""Rule-based, extractive learning-guide construction.

Guides are assembled from sentences that appear verbatim in the uploaded material:
definitions found by lexical patterns, central sentences ranked by TF-IDF similarity
(a TextRank-style degree centrality), and cue-phrase matches for relationships and
examples. Nothing is paraphrased or invented, and every item keeps its source location.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.nlp.segment import Section
from app.nlp.text import (
    PRONOUN_START_RE,
    STOPWORDS,
    contains_phrase,
    normalize_key,
    split_sentences,
    truncate_words,
    word_count,
)

GUIDE_METHOD = "extractive-rule-based"


@dataclass
class Sentence:
    text: str
    location: int
    order: int
    section_index: int


@dataclass
class Definition:
    term: str
    definition: str
    sentence: str
    location: int
    section_index: int
    strength: str  # strong | medium


# --------------------------------------------------------------------------- sentences


def section_sentences(section: Section, section_index: int, start_order: int = 0) -> list[Sentence]:
    out: list[Sentence] = []
    order = start_order
    for para in section.paragraphs:
        if para.subheading and para.text == para.subheading:
            continue
        for sent in split_sentences(para.text):
            sent = sent.strip()
            n = word_count(sent)
            if n < 4 or n > 70:
                continue
            out.append(Sentence(sent, para.location, order, section_index))
            order += 1
    return out


# --------------------------------------------------------------------------- definitions

_TERM = r"(?P<term>[A-Za-z][A-Za-z0-9\-' ]{1,60}?(?:\s*\([A-Za-z0-9\-]{2,12}\))?)"
_STRONG_PATTERNS = [
    re.compile(rf"^{_TERM}\s*,?\s+(?:is|are)\s+(?:formally\s+)?(?:defined|described)\s+as\s+(?P<def>.+)$", re.I),
    re.compile(rf"^{_TERM}\s+(?:refers?|relates?)\s+to\s+(?P<def>.+)$", re.I),
    re.compile(rf"^{_TERM}\s+(?:means|denotes|stands for)\s+(?P<def>.+)$", re.I),
    re.compile(
        rf"^{_TERM}\s+(?:is|are)\s+(?P<def>(?:the|a|an)\s+(?:process|technique|method|task|measure|model|algorithm|approach|way|procedure|representation|branch|field|study|set|collection|statistic|metric|step|form|type|kind|family|class)\b.+)$",
        re.I,
    ),
]
_MEDIUM_PATTERN = re.compile(rf"^{_TERM}\s+(?:is|are)\s+(?P<def>(?:the|a|an)\s+.+)$", re.I)
_GLOSSARY_PATTERN = re.compile(
    r"^(?P<term>[A-Za-z][A-Za-z0-9\-' ()]{1,50}?)\s*(?::|\s[-–—]\s)\s*(?P<def>[A-Za-z(].{12,})$"
)

_BAD_TERM_START = re.compile(
    r"^(this|these|those|that|it|its|they|there|here|which|what|who|one|each|every|some|any|all|most|such|"
    r"our|we|you|he|she|his|her|their|example|result|output|input|goal|aim|idea|main|problem|reason|answer|"
    r"advantage|disadvantage|benefit|drawback|purpose|key|first|second|third|next|last|following|above|below|"
    r"other|another|same|only|important|note)\b",
    re.I,
)
_LEADING_DET = re.compile(r"^(the|a|an)\s+", re.I)


def _clean_term(term: str) -> str | None:
    term = _LEADING_DET.sub("", term.strip(" ,:;-–—\"'"))
    if not term or _BAD_TERM_START.match(term):
        return None
    n = word_count(term)
    if n == 0 or n > 6:
        return None
    content = [w for w in re.findall(r"[A-Za-z0-9\-]+", term.lower()) if w not in STOPWORDS]
    if not content:
        return None
    return term


def extract_definitions(sentences: list[Sentence], keyphrase_keys: set[str]) -> list[Definition]:
    """Find term-definition pairs using lexical patterns; weak patterns require a known keyphrase."""
    found: list[Definition] = []
    seen: set[str] = set()
    for sent in sentences:
        text = sent.text.rstrip()
        match = None
        strength = "strong"
        for pattern in _STRONG_PATTERNS:
            match = pattern.match(text)
            if match:
                break
        if not match:
            m = _MEDIUM_PATTERN.match(text)
            if m:
                term_key = normalize_key(_LEADING_DET.sub("", m.group("term")))
                acronym = bool(re.search(r"\b[A-Z]{2,}\b", m.group("term")))
                if term_key in keyphrase_keys or acronym or m.group("term")[:1].isupper() and term_key.count(" ") >= 1:
                    match, strength = m, "medium"
        if not match:
            m = _GLOSSARY_PATTERN.match(text)
            if m and word_count(m.group("def")) >= 4:
                match, strength = m, "strong"
        if not match:
            continue
        term = _clean_term(match.group("term"))
        if not term:
            continue
        definition = match.group("def").strip().rstrip(".")
        if word_count(definition) < 4 or word_count(definition) > 45:
            continue
        key = normalize_key(term)
        if key in seen:
            continue
        seen.add(key)
        found.append(Definition(term, definition, text, sent.location, sent.section_index, strength))
    return found


# --------------------------------------------------------------------------- ranking


def rank_sentences(sentences: list[Sentence], keyphrases: list[str]) -> list[tuple[Sentence, float]]:
    """Score sentences by TF-IDF degree centrality, keyphrase coverage and early position."""
    if not sentences:
        return []
    texts = [s.text for s in sentences]
    try:
        matrix = TfidfVectorizer(stop_words=list(STOPWORDS), sublinear_tf=True).fit_transform(texts)
        sim = cosine_similarity(matrix)
        np.fill_diagonal(sim, 0.0)
        centrality = sim.sum(axis=1)
        if centrality.max() > 0:
            centrality = centrality / centrality.max()
    except ValueError:
        centrality = np.zeros(len(sentences))
    scored: list[tuple[Sentence, float]] = []
    total = len(sentences)
    for i, sent in enumerate(sentences):
        kp_hits = sum(1 for kp in keyphrases[:10] if contains_phrase(sent.text, kp))
        position = 1.0 - (i / total) if total > 1 else 1.0
        n = word_count(sent.text)
        length_penalty = 0.0 if 8 <= n <= 40 else 0.15
        pronoun_penalty = 0.2 if PRONOUN_START_RE.match(sent.text) else 0.0
        question_penalty = 0.5 if sent.text.endswith("?") else 0.0
        score = (
            0.55 * float(centrality[i])
            + 0.25 * min(kp_hits, 3) / 3
            + 0.2 * position
            - length_penalty
            - pronoun_penalty
            - question_penalty
        )
        scored.append((sent, score))
    return scored


def mmr_select(
    scored: list[tuple[Sentence, float]], k: int, exclude: set[int] | None = None, lambda_: float = 0.7
) -> list[Sentence]:
    """Maximal marginal relevance selection to avoid near-duplicate key points."""
    exclude = exclude or set()
    pool = [(s, sc) for s, sc in scored if s.order not in exclude]
    if not pool:
        return []
    try:
        matrix = TfidfVectorizer(stop_words=list(STOPWORDS)).fit_transform([s.text for s, _ in pool])
        sim = cosine_similarity(matrix)
    except ValueError:
        sim = np.zeros((len(pool), len(pool)))
    chosen: list[int] = []
    candidates = list(range(len(pool)))
    while candidates and len(chosen) < k:
        best, best_val = None, -1e9
        for c in candidates:
            redundancy = max((sim[c][j] for j in chosen), default=0.0)
            if redundancy > 0.75:
                continue
            val = lambda_ * pool[c][1] - (1 - lambda_) * redundancy
            if val > best_val:
                best, best_val = c, val
        if best is None:
            break
        chosen.append(best)
        candidates.remove(best)
    return [pool[i][0] for i in chosen]


# --------------------------------------------------------------------------- cues

RELATION_RE = re.compile(
    r"\b(is a (?:type|kind|form|subset|part|variant) of|are (?:types|kinds|forms) of|consists? of|is composed of|"
    r"depends? on|is based on|are based on|builds? on|extends?|unlike|whereas|in contrast|compared (?:to|with)|"
    r"differs? from|difference between|is part of|leads? to|results? in|causes?|because|therefore|as a result|"
    r"is related to|corresponds? to|is equivalent to|replaces?|improves? (?:on|upon))\b",
    re.I,
)
EXAMPLE_RE = re.compile(
    r"\b(for example|for instance|e\.g\.|such as|applications? (?:include|of)|is used in|are used in|"
    r"is used for|are used for|is applied to|in practice|real-world|commonly used)\b",
    re.I,
)


def _item(sent: Sentence) -> dict:
    return {"text": sent.text, "location": sent.location}


def build_guide(
    section: Section,
    sentences: list[Sentence],
    keyphrases: list[str],
    keyphrase_forms: dict[str, str],
    definitions: list[Definition],
) -> dict:
    """Assemble a structured, source-referenced learning guide for one topic."""
    scored = rank_sentences(sentences, keyphrases)
    by_score = sorted(scored, key=lambda x: -x[1])
    overview_pick = sorted(by_score[:2], key=lambda x: x[0].order)
    overview = [s for s, _ in overview_pick if not PRONOUN_START_RE.match(s.text)] or [s for s, _ in overview_pick[:1]]
    used = {s.order for s in overview}
    def_sentences = {normalize_key(d.sentence) for d in definitions}

    key_points = mmr_select([(s, sc) for s, sc in scored if normalize_key(s.text) not in def_sentences], 10, used)
    used |= {s.order for s in key_points}

    concepts: list[dict] = []
    for kp in keyphrases[:8]:
        support = next((s for s, _ in by_score if contains_phrase(s.text, kp)), None)
        if support is None:
            continue
        concepts.append({"term": keyphrase_forms.get(kp, kp), "sentence": _item(support)})

    relationships: list[dict] = []
    for sent in sentences:
        m = RELATION_RE.search(sent.text)
        if not m:
            continue
        hits = sum(1 for kp in keyphrases[:12] if contains_phrase(sent.text, kp))
        if hits >= 1:
            relationships.append({**_item(sent), "cue": m.group(1).lower()})
        if len(relationships) >= 6:
            break

    examples: list[dict] = []
    for sent in sentences:
        if EXAMPLE_RE.search(sent.text):
            examples.append(_item(sent))
        if len(examples) >= 6:
            break

    revision: list[str] = []
    for d in definitions[:6]:
        revision.append(f"{d.term}: {truncate_words(d.definition, 22)}")
    for s in sorted(key_points[:6], key=lambda s: word_count(s.text))[:3]:
        revision.append(truncate_words(s.text, 30))
    if not revision and overview:
        revision.append(truncate_words(overview[0].text, 30))

    locations = sorted({p.location for p in section.paragraphs})
    return {
        "method": GUIDE_METHOD,
        "overview": [_item(s) for s in overview],
        "definitions": [
            {"term": d.term, "definition": d.definition, "text": d.sentence, "location": d.location}
            for d in definitions
        ],
        # Items stay in reading order; "rank" lets concise mode show only the most central points.
        "key_points": [{**_item(s), "rank": key_points.index(s)} for s in sorted(key_points, key=lambda s: s.order)],
        "concepts": concepts,
        "relationships": relationships,
        "examples": examples,
        "revision": revision,
        "locations": locations,
        "sentence_count": len(sentences),
    }
