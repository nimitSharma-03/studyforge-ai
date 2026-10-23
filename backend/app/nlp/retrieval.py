"""TF-IDF retrieval and extractive, evidence-graded question answering.

Similarity here is lexical (shared weighted terms). A high score means the passage uses
the same vocabulary as the question; it does not prove the passage entails an answer.
The verdict labels are therefore deliberately conservative.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.nlp.text import PRONOUN_START_RE, light_stem, normalize_key, split_sentences, stem_tokens, word_count


def _analyzer(text: str) -> list[str]:
    toks = stem_tokens(text)
    return toks + [f"{a} {b}" for a, b in zip(toks, toks[1:], strict=False)]


@dataclass
class Passage:
    chunk_id: int
    text: str
    heading: str | None
    topic_id: int | None
    location_type: str
    location_start: int
    location_end: int


class PassageIndex:
    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self.vectorizer = TfidfVectorizer(analyzer=_analyzer, sublinear_tf=True)
        texts = [f"{p.heading or ''}. {p.text}" for p in passages]
        try:
            self.matrix = self.vectorizer.fit_transform(texts) if passages else None
        except ValueError:
            self.matrix = None

    def search(self, query: str, k: int = 5, topic_id: int | None = None) -> list[tuple[Passage, float]]:
        if self.matrix is None or not query.strip():
            return []
        qv = self.vectorizer.transform([query])
        if qv.nnz == 0:
            return []
        scores = cosine_similarity(qv, self.matrix).ravel()
        order = np.argsort(-scores)
        results: list[tuple[Passage, float]] = []
        for idx in order:
            if scores[idx] <= 0:
                break
            p = self.passages[idx]
            if topic_id is not None and p.topic_id != topic_id:
                continue
            results.append((p, float(scores[idx])))
            if len(results) >= k:
                break
        return results


class IndexCache:
    """Small LRU cache so each document's TF-IDF index is built once per process."""

    def __init__(self, max_items: int = 32):
        self.max_items = max_items
        self._items: OrderedDict[str, PassageIndex] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str, builder) -> PassageIndex:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        index = builder()
        with self._lock:
            self._items[key] = index
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
        return index

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._items if k.startswith(prefix)]:
                del self._items[key]


index_cache = IndexCache()

_QUESTION_WORDS = {
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "when",
    "where",
    "why",
    "how",
    "is",
    "are",
    "does",
    "do",
    "did",
    "explain",
    "describe",
    "define",
    "definition",
    "meaning",
    "mean",
    "tell",
    "give",
    "list",
    "state",
    "discuss",
}
_DEFINE_RE = re.compile(
    r"^\s*(?:what\s+(?:is|are)\s+(?:meant\s+by\s+)?|define\s+|definition\s+of\s+|meaning\s+of\s+|explain\s+)(?:the\s+|a\s+|an\s+)?(?P<term>[^?]+?)\s*\??$",
    re.I,
)


def answer_question(question: str, index: PassageIndex, definitions: list[dict], topic_id: int | None = None) -> dict:
    """Return an extractive answer graded as supported, partial or insufficient evidence."""
    hits = index.search(question, k=5, topic_id=topic_id)
    q_terms = [t for t in stem_tokens(question) if t not in {light_stem(w) for w in _QUESTION_WORDS}]
    passages = [
        {
            "chunk_id": p.chunk_id,
            "text": p.text,
            "heading": p.heading,
            "topic_id": p.topic_id,
            "location_type": p.location_type,
            "location_start": p.location_start,
            "location_end": p.location_end,
            "score": round(score, 3),
        }
        for p, score in hits[:3]
    ]
    base = {"question": question, "passages": passages, "query_terms": q_terms}
    if not hits or not q_terms:
        return {
            **base,
            "verdict": "insufficient",
            "answer": [],
            "coverage": 0.0,
            "top_score": 0.0,
            "message": "Your uploaded material does not contain enough matching text to answer this question.",
        }

    # A direct definition lookup takes precedence when the question asks what a term means.
    m = _DEFINE_RE.match(question)
    if m:
        key = normalize_key(m.group("term"))
        for d in definitions:
            if normalize_key(d["term"]) == key:
                return {
                    **base,
                    "verdict": "supported",
                    "coverage": 1.0,
                    "top_score": 1.0,
                    "answer": [
                        {
                            "text": d["text"],
                            "location_type": d["location_type"],
                            "location": d["location"],
                            "topic_id": d.get("topic_id"),
                        }
                    ],
                    "message": "Definition found in your material.",
                }

    sentences: list[tuple[str, Passage, int]] = []
    for p, _score in hits:
        for order, sent in enumerate(split_sentences(p.text)):
            if word_count(sent) >= 4:
                sentences.append((sent, p, order))
    if not sentences:
        return {
            **base,
            "verdict": "insufficient",
            "answer": [],
            "coverage": 0.0,
            "top_score": 0.0,
            "message": "No usable sentences were found in the matching passages.",
        }
    sv = index.vectorizer.transform([s for s, _, _ in sentences])
    qv = index.vectorizer.transform([question])
    sims = cosine_similarity(qv, sv).ravel()
    for i, (sent, _p, _o) in enumerate(sentences):
        if PRONOUN_START_RE.match(sent):
            sims[i] *= 0.85
    order = np.argsort(-sims)
    top = [i for i in order[:3] if sims[i] > 0.05]
    top_score = float(sims[order[0]])
    covered_text = " ".join(sentences[i][0] for i in top)
    covered_stems = set(stem_tokens(covered_text))
    coverage = sum(1 for t in set(q_terms) if t in covered_stems) / max(1, len(set(q_terms)))

    if top_score >= 0.32 and coverage >= 0.75:
        verdict, message = "supported", "These sentences from your material closely match the question."
    elif top_score >= 0.12 and coverage >= 0.4:
        verdict, message = (
            "partial",
            (
                "Your material only partly matches this question. Read the cited passages "
                "to judge whether they answer it."
            ),
        )
    else:
        verdict, message = (
            "insufficient",
            (
                "Your material does not appear to address this question directly. "
                "The closest passages are shown for reference."
            ),
        )
    answer = []
    if verdict != "insufficient":
        for i in top[: (3 if verdict == "supported" else 2)]:
            sent, p, _o = sentences[i]
            answer.append(
                {
                    "text": sent,
                    "location_type": p.location_type,
                    "location": p.location_start,
                    "topic_id": p.topic_id,
                    "score": round(float(sims[i]), 3),
                }
            )
    return {
        **base,
        "verdict": verdict,
        "answer": answer,
        "coverage": round(coverage, 2),
        "top_score": round(top_score, 3),
        "message": message,
    }
