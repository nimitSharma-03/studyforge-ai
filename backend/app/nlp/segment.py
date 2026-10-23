"""Topic segmentation and source-aware chunking.

Primary strategy: use the document's own structure (headings, slide titles).
Fallback strategy: a TextTiling-style lexical cohesion segmenter over TF-IDF vectors,
used when a document has little or no heading structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.nlp.extract import Block
from app.nlp.text import STOPWORDS, normalize_key, split_sentences, word_count

MAX_TOPICS = 40
MIN_TOPIC_WORDS = 30
CHUNK_TARGET_WORDS = 160
CHUNK_MAX_WORDS = 230

_CONT_RE = re.compile(
    r"\s*[\(\[]?\b(cont(?:inued|d)?\.?|ctd\.?)[\)\]]?\s*$|\s*\(\d+\)\s*$|\s*[-–:]\s*part\s*\d+\s*$", re.I
)


@dataclass
class Paragraph:
    text: str
    location: int
    subheading: str | None = None


@dataclass
class Section:
    title: str
    title_source: str  # heading | keywords | default
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def words(self) -> int:
        return sum(word_count(p.text) for p in self.paragraphs)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs)

    @property
    def location_start(self) -> int:
        return self.paragraphs[0].location if self.paragraphs else 1

    @property
    def location_end(self) -> int:
        return max(p.location for p in self.paragraphs) if self.paragraphs else 1


@dataclass
class ChunkData:
    text: str
    heading: str
    location_start: int
    location_end: int
    section_index: int

    @property
    def words(self) -> int:
        return word_count(self.text)


def _clean_title(title: str) -> str:
    title = _CONT_RE.sub("", title).strip(" :-–—")
    return title[:200] or "Untitled section"


def segment(blocks: list[Block], file_type: str) -> tuple[list[Section], str]:
    """Group blocks into topic sections. Returns sections and the method used."""
    headings = [b for b in blocks if b.kind == "heading"]
    split_level = _choose_split_level(headings)
    sections: list[Section] = []
    if split_level:
        current: Section | None = None
        for block in blocks:
            if block.kind == "heading" and block.level <= split_level:
                current = Section(_clean_title(block.text), "heading")
                sections.append(current)
            elif block.kind == "heading":
                # Deeper heading: keep as context for the paragraphs that follow.
                if current is None:
                    current = Section(_clean_title(block.text), "heading")
                    sections.append(current)
                current.paragraphs.append(Paragraph(block.text, block.location, subheading=block.text))
            else:
                if current is None:
                    current = Section("Introduction", "default")
                    sections.append(current)
                current.paragraphs.append(Paragraph(block.text, block.location))
        sections = [s for s in sections if s.paragraphs or s.title_source == "heading"]
        sections = _merge_continuations(sections)
        sections = _merge_small(sections)
        method = "slides" if file_type == "pptx" else "headings"
    else:
        method = "single"
        sections = [Section("Main content", "default", [Paragraph(b.text, b.location) for b in blocks])]

    # Sections that are still very long and flat get split by lexical cohesion.
    refined: list[Section] = []
    for section in sections:
        # Flat documents (no headings) are split sooner and finer than sections the author delimited.
        flat = method == "single"
        if section.words > (300 if flat else 1200) and len(section.paragraphs) >= (4 if flat else 6):
            parts = texttile(section, min_words=100 if flat else 150, words_per_segment=200 if flat else 450)
            if len(parts) > 1:
                method = "texttiling" if method == "single" else f"{method}+texttiling"
            refined.extend(parts)
        else:
            refined.append(section)
    sections = [s for s in refined if s.paragraphs]
    sections = _cap_topics(sections)
    return sections, method


def _choose_split_level(headings: list[Block]) -> int:
    if len(headings) < 2:
        return 0
    levels = sorted({h.level for h in headings})
    chosen = 0
    for level in levels:
        count = sum(1 for h in headings if h.level <= level)
        if count <= MAX_TOPICS:
            chosen = level
        else:
            break
    if chosen == 0:
        chosen = levels[0]
    if sum(1 for h in headings if h.level <= chosen) < 2 and len(levels) > 1:
        chosen = levels[1]
    return chosen


def _merge_continuations(sections: list[Section]) -> list[Section]:
    out: list[Section] = []
    for section in sections:
        if out and normalize_key(out[-1].title) == normalize_key(section.title):
            out[-1].paragraphs.extend(section.paragraphs)
        else:
            out.append(section)
    return out


def _merge_small(sections: list[Section]) -> list[Section]:
    """Fold heading-only or tiny sections into a neighbour so every topic has real content."""
    if len(sections) <= 1:
        return sections
    out: list[Section] = []
    pending: Section | None = None
    for section in sections:
        if pending is not None:
            # A tiny section followed by another: keep the following section's title but its content first.
            if pending.paragraphs:
                section.paragraphs = [
                    Paragraph(p.text, p.location, p.subheading or pending.title) for p in pending.paragraphs
                ] + section.paragraphs
            pending = None
        if section.words < MIN_TOPIC_WORDS:
            pending = section
            continue
        out.append(section)
    if pending is not None:
        if out:
            out[-1].paragraphs.extend(
                Paragraph(p.text, p.location, p.subheading or pending.title) for p in pending.paragraphs
            )
        else:
            out.append(pending)
    return out


def _cap_topics(sections: list[Section]) -> list[Section]:
    while len(sections) > MAX_TOPICS:
        sizes = [sections[i].words + sections[i + 1].words for i in range(len(sections) - 1)]
        i = int(np.argmin(sizes))
        a, b = sections[i], sections[i + 1]
        b_paras = [Paragraph(p.text, p.location, p.subheading or b.title) for p in b.paragraphs]
        sections[i] = Section(a.title, a.title_source, a.paragraphs + b_paras)
        del sections[i + 1]
    return sections


# --------------------------------------------------------------------------- TextTiling fallback


def texttile(section: Section, window: int = 2, min_words: int = 150, words_per_segment: int = 450) -> list[Section]:
    """Split a long section at lexical-cohesion valleys between adjacent paragraph windows."""
    paras = section.paragraphs
    # Very long paragraphs are split into ~3-sentence pseudo paragraphs for better resolution.
    units: list[Paragraph] = []
    for p in paras:
        sents = split_sentences(p.text)
        if len(sents) > 6:
            for i in range(0, len(sents), 3):
                units.append(Paragraph(" ".join(sents[i : i + 3]), p.location, p.subheading))
        else:
            units.append(p)
    if len(units) < 2 * window:
        return [section]
    try:
        vectorizer = TfidfVectorizer(stop_words=list(STOPWORDS), sublinear_tf=True, min_df=1)
        matrix = vectorizer.fit_transform([u.text for u in units]).toarray()
    except ValueError:
        return [section]
    gaps: list[float] = []
    for i in range(1, len(units)):
        left = matrix[max(0, i - window) : i].mean(axis=0)
        right = matrix[i : i + window].mean(axis=0)
        denom = (np.linalg.norm(left) * np.linalg.norm(right)) or 1.0
        gaps.append(float(left @ right / denom))
    depths: list[float] = []
    for i, score in enumerate(gaps):
        left_peak = max(gaps[: i + 1])
        right_peak = max(gaps[i:])
        depths.append((left_peak - score) + (right_peak - score))
    total_words = sum(word_count(u.text) for u in units)
    target = int(min(25, max(1, round(total_words / words_per_segment))))
    threshold = float(np.mean(depths) - np.std(depths) / 2)
    candidates = sorted((i for i, d in enumerate(depths) if d > threshold), key=lambda i: depths[i], reverse=True)
    boundaries: list[int] = []
    for i in candidates:
        cut = i + 1
        trial = sorted(boundaries + [cut])
        edges = [0, *trial, len(units)]
        sizes = [sum(word_count(u.text) for u in units[a:b]) for a, b in zip(edges, edges[1:], strict=False)]
        if min(sizes) >= min_words:
            boundaries = trial
        if len(boundaries) >= target - 1:
            break
    if not boundaries:
        return [section]
    edges = [0, *sorted(boundaries), len(units)]
    parts: list[Section] = []
    for n, (a, b) in enumerate(zip(edges, edges[1:], strict=False)):
        title = section.title if n == 0 and section.title_source == "heading" else ""
        parts.append(Section(title, "heading" if title else "keywords", units[a:b]))
    return parts


# --------------------------------------------------------------------------- chunking


def chunk_sections(sections: list[Section]) -> list[ChunkData]:
    """Group paragraphs into retrieval chunks without crossing topic boundaries."""
    chunks: list[ChunkData] = []
    for index, section in enumerate(sections):
        buffer: list[Paragraph] = []
        buffer_words = 0

        def flush(section: Section = section, index: int = index) -> None:
            nonlocal buffer, buffer_words
            if buffer:
                heading = next((p.subheading for p in buffer if p.subheading), None) or section.title
                text = "\n\n".join(p.text for p in buffer if p.text != p.subheading or len(buffer) == 1)
                chunks.append(ChunkData(text, heading, buffer[0].location, max(p.location for p in buffer), index))
            buffer, buffer_words = [], 0

        for para in section.paragraphs:
            n = word_count(para.text)
            if n > CHUNK_MAX_WORDS:
                flush()
                piece: list[str] = []
                piece_words = 0
                for sent in split_sentences(para.text):
                    sw = word_count(sent)
                    if piece and piece_words + sw > CHUNK_TARGET_WORDS:
                        chunks.append(
                            ChunkData(
                                " ".join(piece), para.subheading or section.title, para.location, para.location, index
                            )
                        )
                        piece, piece_words = [], 0
                    piece.append(sent)
                    piece_words += sw
                if piece:
                    chunks.append(
                        ChunkData(
                            " ".join(piece), para.subheading or section.title, para.location, para.location, index
                        )
                    )
                continue
            if para.subheading and para.text == para.subheading and buffer_words >= 60:
                flush()
            if buffer and buffer_words + n > CHUNK_TARGET_WORDS:
                flush()
            buffer.append(para)
            buffer_words += n
        flush()
    return [c for c in chunks if c.text.strip()]
