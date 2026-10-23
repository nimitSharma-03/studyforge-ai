"""Text normalisation, sentence segmentation and tokenisation helpers.

Everything here is rule-based and deterministic so the pipeline runs offline on CPU
without downloading language models.
"""

from __future__ import annotations

import re
import unicodedata

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

EXTRA_STOPWORDS = {
    "also",
    "however",
    "thus",
    "hence",
    "may",
    "might",
    "must",
    "shall",
    "will",
    "would",
    "could",
    "can",
    "use",
    "used",
    "using",
    "uses",
    "example",
    "examples",
    "e.g",
    "i.e",
    "etc",
    "eg",
    "ie",
    "one",
    "two",
    "three",
    "first",
    "second",
    "third",
    "new",
    "different",
    "various",
    "many",
    "much",
    "several",
    "way",
    "ways",
    "like",
    "given",
    "make",
    "makes",
    "made",
    "called",
    "known",
    "based",
    "within",
    "without",
    "slide",
    "page",
    "figure",
    "fig",
    "table",
    "chapter",
    "section",
    "lecture",
    "unit",
    "module",
    "note",
    "notes",
    "important",
    "following",
    "include",
    "includes",
    "including",
    "refer",
    "refers",
    "means",
    "defined",
    "type",
    "types",
    "kind",
    "kinds",
    "set",
    "number",
    "lot",
    "often",
    "usually",
    "generally",
    "typically",
    "common",
    "commonly",
    "simple",
    "simply",
    "just",
    "us",
    "let",
    "get",
    "gets",
    "need",
    "needs",
    "say",
    "says",
    "see",
    "shown",
    "show",
    "shows",
    "able",
    "allow",
    "allows",
    "help",
    "helps",
    "good",
    "better",
    "best",
    "large",
    "small",
    "high",
    "low",
    "process",
    "processes",
    "task",
    "tasks",
    "method",
    "methods",
    "approach",
    "technique",
    "techniques",
}
# scikit-learn's list contains content words that matter in course notes ("operating system",
# "computer network", "interest rate"); they are put back.
_CONTENT_WORDS = {
    "system",
    "computer",
    "interest",
    "bill",
    "fire",
    "mill",
    "name",
    "side",
    "top",
    "bottom",
    "front",
    "back",
    "move",
    "detail",
    "empty",
    "fill",
    "thick",
    "thin",
    "serious",
    "amount",
    "call",
    "con",
    "de",
    "part",
}
STOPWORDS: frozenset[str] = frozenset((ENGLISH_STOP_WORDS - _CONTENT_WORDS) | EXTRA_STOPWORDS)

_BULLET_RE = re.compile(r"^\s*(?:[•‣▪▫●○◦⁃∙·■□➢➔➜✓✔*\-–—>]+|\(?\d{1,2}[.)]|\(?[a-zA-Z][.)])\s+")
_WS_RE = re.compile(r"[ \t  -​　]+")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "′": "'", "­": ""})

ABBREVIATIONS = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "dr",
    "mr",
    "mrs",
    "ms",
    "prof",
    "fig",
    "figs",
    "eq",
    "eqs",
    "no",
    "nos",
    "al",
    "approx",
    "dept",
    "inc",
    "ltd",
    "jr",
    "sr",
    "st",
    "vol",
    "pp",
    "ch",
    "sec",
    "cf",
    "resp",
    "min",
    "max",
}

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*")
PRONOUN_START_RE = re.compile(r"^(this|these|those|it|its|they|their|them|such|he|she|that|which|here|there)\b", re.I)


def normalize_text(text: str) -> str:
    """Normalise unicode, quotes, bullets and whitespace while keeping paragraph meaning."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTES)
    text = _CTRL_RE.sub(" ", text)
    text = _BULLET_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def strip_bullet(text: str) -> str:
    return _BULLET_RE.sub("", text).strip()


def join_lines(lines: list[str]) -> str:
    """Join visual lines of a paragraph, repairing words hyphenated across line breaks."""
    out = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and line[:1].islower() and len(out) > 1 and out[-2].isalpha():
            last_token = out.rsplit(" ", 1)[-1]
            # "state-of-" + "the-art" is a compound: keep its hyphen; "Tokeniza-" + "tion" is a broken word.
            out = out + line if "-" in last_token[:-1] else out[:-1] + line
        else:
            out = f"{out} {line}"
    return out


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with abbreviation and initial handling."""
    text = text.strip()
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    sentences: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if sentences:
            prev = sentences[-1]
            last_token = prev.rstrip(".").rsplit(" ", 1)[-1].lower().rstrip(".")
            if last_token in ABBREVIATIONS or (len(last_token) == 1 and last_token.isalpha()):
                sentences[-1] = f"{prev} {part}"
                continue
        sentences.append(part)
    return sentences


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def content_words(text: str) -> list[str]:
    return [w.lower() for w in words(text) if w.lower() not in STOPWORDS and len(w) > 1]


def light_stem(token: str) -> str:
    """A tiny suffix stripper used to make lexical matching less brittle (not a full stemmer)."""
    t = token.lower()
    if len(t) <= 4:
        return t
    for suffix, repl in (
        ("ization", "ize"),
        ("isation", "ize"),
        ("ational", "ate"),
        ("ies", "y"),
        ("sses", "ss"),
        ("ing", ""),
        ("edly", ""),
        ("ed", ""),
        ("ly", ""),
        ("es", ""),
        ("s", ""),
    ):
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            if suffix == "s" and t.endswith("ss"):
                return t
            return t[: len(t) - len(suffix)] + repl
    return t


def stem_tokens(text: str) -> list[str]:
    return [light_stem(w) for w in content_words(text)]


def normalize_key(text: str) -> str:
    """Canonical comparison key: lowercase alphanumerics separated by single spaces."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def truncate_words(text: str, limit: int) -> str:
    tokens = text.split()
    if len(tokens) <= limit:
        return text
    return " ".join(tokens[:limit]).rstrip(",;:") + "…"


def is_heading_like(text: str) -> bool:
    t = text.strip()
    return 0 < len(t) <= 90 and word_count(t) <= 12 and not t.endswith((".", "?", "!", ";", ","))


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Whole-phrase matcher; hyphens count as word characters so "written" never matches "hand-written"."""
    return re.compile(rf"(?<![A-Za-z0-9\-]){re.escape(phrase)}(?![A-Za-z0-9]|-[A-Za-z0-9])", re.I)


def contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return phrase_pattern(phrase).search(text) is not None


def count_phrase(text: str, phrase: str) -> int:
    return len(phrase_pattern(phrase).findall(text)) if phrase else 0
