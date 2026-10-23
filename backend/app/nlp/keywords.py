"""Keyphrase extraction: stopword-delimited candidate phrases ranked by TF-IDF across topics."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.nlp.text import STOPWORDS, normalize_key

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|\S")
_GENERIC = {
    "data",
    "text",
    "word",
    "words",
    "information",
    "system",
    "systems",
    "model",
    "models",
    "result",
    "results",
    "problem",
    "problems",
    "case",
    "cases",
    "thing",
    "things",
    "part",
    "parts",
    "form",
    "forms",
    "time",
    "level",
    "levels",
    "order",
    "value",
    "values",
    "term",
    "terms",
    "point",
    "points",
    "idea",
    "student",
    "students",
    "course",
    "class",
    "topic",
    "topics",
    "overview",
    "introduction",
    "summary",
    "conclusion",
    "definition",
    "definitions",
    "advantages",
    "disadvantages",
    "question",
    "questions",
    "answer",
    "answers",
    "people",
    "person",
    "user",
    "users",
    "work",
    "works",
    "field",
    "area",
    "areas",
}
# Frequent verbs, adjectives and adverbs in lecture prose. Without a POS tagger these act as phrase
# boundaries so candidates stay noun-phrase-like ("noise removal", not "removing").
_NON_NOUN = {
    "assign",
    "assigns",
    "assigned",
    "assigning",
    "divide",
    "divides",
    "divided",
    "measure",
    "measures",
    "measured",
    "remove",
    "removes",
    "removed",
    "removing",
    "reduce",
    "reduces",
    "reduced",
    "reducing",
    "require",
    "requires",
    "required",
    "produce",
    "produces",
    "produced",
    "producing",
    "predict",
    "predicts",
    "predicted",
    "predicting",
    "contain",
    "contains",
    "contained",
    "capture",
    "captures",
    "captured",
    "estimate",
    "estimates",
    "estimated",
    "learns",
    "learned",
    "learnt",
    "train",
    "trains",
    "trained",
    "combine",
    "combines",
    "combined",
    "enable",
    "enables",
    "enabled",
    "rely",
    "relies",
    "relied",
    "change",
    "changes",
    "changing",
    "changed",
    "choose",
    "chooses",
    "obtain",
    "obtains",
    "convert",
    "converts",
    "converted",
    "converting",
    "handle",
    "handles",
    "handling",
    "split",
    "splits",
    "splitting",
    "lets",
    "focus",
    "carry",
    "carries",
    "ignore",
    "ignores",
    "appear",
    "appears",
    "appearing",
    "tend",
    "tends",
    "state",
    "states",
    "relate",
    "relates",
    "related",
    "compare",
    "compares",
    "comparing",
    "summarise",
    "summarises",
    "summarize",
    "summarizes",
    "find",
    "finds",
    "found",
    "involve",
    "involves",
    "provide",
    "provides",
    "represent",
    "represents",
    "describe",
    "describes",
    "consider",
    "considered",
    "apply",
    "applies",
    "applied",
    "improve",
    "improves",
    "increase",
    "increases",
    "decrease",
    "decreases",
    "smaller",
    "larger",
    "higher",
    "lower",
    "faster",
    "slower",
    "fast",
    "slow",
    "valid",
    "actual",
    "actually",
    "typical",
    "early",
    "modern",
    "traditional",
    "single",
    "individual",
    "whole",
    "direct",
    "similar",
    "dense",
    "rare",
    "frequent",
    "idea",
    "ideas",
    "stage",
    "stages",
    "later",
    "little",
    "proportion",
    "correct",
    "incorrect",
    "successfully",
    "particular",
    "specific",
    "certain",
    "basic",
    "main",
    "key",
    "possible",
    "difficult",
    "easy",
    "hard",
    "useful",
    "relevant",
    "irrelevant",
    "available",
    "general",
    "specifically",
    "mainly",
    "widely",
    "always",
    "never",
    "sometimes",
    "constantly",
    "usually",
    "long",
    "short",
    "full",
    "extra",
    "true",
    "false",
    "known",
    "well-known",
    "consistent",
    "informative",
    "simple",
    "taken",
    "written",
    "seen",
    "given",
    "shown",
    "done",
    "makes",
    "making",
    "allows",
    "able",
}


def candidate_phrases(text: str, max_len: int = 3) -> list[str]:
    """Return lowercase candidate phrases: runs of content words split at stopwords and punctuation."""
    phrases: list[str] = []
    run: list[str] = []

    def flush() -> None:
        for n in range(1, max_len + 1):
            for i in range(len(run) - n + 1):
                gram = run[i : i + n]
                if n == 1 and (gram[0] in _GENERIC or len(gram[0]) < 3):
                    continue
                phrases.append(" ".join(gram))
        run.clear()

    for token in _TOKEN_RE.findall(text):
        low = token.lower()
        if not token[0].isalpha() or low in STOPWORDS or low in _NON_NOUN:
            flush()
            continue
        run.append(low)
        if len(run) > 6:  # very long runs are usually lists; cap to keep phrases meaningful
            flush()
    flush()
    return phrases


def surface_forms(text: str, phrases: set[str]) -> dict[str, str]:
    """Map lowercase phrases to their most common original casing (e.g. ``tf-idf`` -> ``TF-IDF``)."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    tokens = _TOKEN_RE.findall(text)
    max_n = 3
    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            gram_tokens = tokens[i : i + n]
            key = " ".join(t.lower() for t in gram_tokens)
            if key in phrases:
                counts[key][" ".join(gram_tokens)] += 1
    out: dict[str, str] = {}
    for key in phrases:
        if counts.get(key):
            forms = counts[key].most_common()
            # Prefer a non-sentence-initial capitalised form when lowercase also occurs.
            lower_form = next((f for f, _ in forms if f == key), None)
            out[key] = lower_form or forms[0][0]
        else:
            out[key] = key
    return out


def topic_keyphrases(topic_texts: list[str], top_n: int = 12) -> list[list[tuple[str, float]]]:
    """Rank candidate phrases for each topic by TF-IDF (topics act as the document collection)."""
    if not topic_texts:
        return []
    vectorizer = TfidfVectorizer(analyzer=candidate_phrases, sublinear_tf=True, norm="l2")
    try:
        matrix = vectorizer.fit_transform(topic_texts)
    except ValueError:
        return [[] for _ in topic_texts]
    vocab = np.array(vectorizer.get_feature_names_out())
    raw_counts = [Counter(candidate_phrases(t)) for t in topic_texts]
    results: list[list[tuple[str, float]]] = []
    for row_index in range(matrix.shape[0]):
        row = matrix.getrow(row_index).toarray().ravel()
        order = np.argsort(-row)
        scored: list[tuple[str, float]] = []
        counts = raw_counts[row_index]
        for idx in order[: top_n * 6]:
            score = float(row[idx])
            if score <= 0:
                break
            phrase = vocab[idx]
            n = phrase.count(" ") + 1
            freq = counts.get(phrase, 0)
            if n > 1 and freq < 2 and len(topic_texts) > 1:
                continue  # one-off multiword phrases are usually accidental collocations
            scored.append((phrase, score * (1 + 0.35 * (n - 1))))
        scored.sort(key=lambda x: -x[1])
        results.append(_dedupe_phrases(scored, top_n))
    return results


def _dedupe_phrases(scored: list[tuple[str, float]], top_n: int) -> list[tuple[str, float]]:
    selected: list[tuple[str, float]] = []
    for phrase, score in scored:
        words_ = set(phrase.split())
        redundant = False
        for other, _ in selected:
            other_words = set(other.split())
            if (
                phrase in other
                or other in phrase
                or len(words_ & other_words) >= max(1, min(len(words_), len(other_words)))
            ):
                # Keep the longer phrase when one contains the other.
                if len(phrase) > len(other) and other in phrase:
                    selected = [(p, s) for p, s in selected if p != other]
                    break
                redundant = True
                break
        if not redundant:
            selected.append((phrase, score))
        if len(selected) >= top_n:
            break
    return selected


def title_from_keyphrases(phrases: list[str], forms: dict[str, str]) -> str:
    picks = [forms.get(p, p) for p in phrases[:2]]
    if not picks:
        return "Untitled topic"
    titled = [p if any(c.isupper() for c in p) else p.title() for p in picks]
    return " and ".join(titled)


def key_of(phrase: str) -> str:
    return normalize_key(phrase)
