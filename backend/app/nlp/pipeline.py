"""End-to-end NLP pipeline: extraction result -> topics, chunks, guides and questions.

This module is pure (no database access) so it can be unit-tested directly.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from app.nlp.extract import ExtractionError, ExtractionResult
from app.nlp.guide import (
    Definition,
    Sentence,
    build_guide,
    extract_definitions,
    mmr_select,
    rank_sentences,
    section_sentences,
)
from app.nlp.keywords import surface_forms, title_from_keyphrases, topic_keyphrases
from app.nlp.questions import QuestionCandidate, QuestionGenerator, SectionInput
from app.nlp.segment import ChunkData, Section, chunk_sections, segment
from app.nlp.text import contains_phrase, normalize_key, word_count


@dataclass
class ProcessedTopic:
    section_index: int
    title: str
    title_source: str
    keywords: list[str]
    location_start: int
    location_end: int
    word_count: int
    guide: dict


@dataclass
class ProcessedDocument:
    unit_label: str
    unit_count: int
    word_count: int
    heading_count: int
    segmentation_method: str
    topics: list[ProcessedTopic]
    chunks: list[ChunkData]
    questions: list[QuestionCandidate]
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class _Deadline:
    def __init__(self, seconds: float):
        self.end = time.monotonic() + seconds

    def check(self, stage: str) -> None:
        if time.monotonic() > self.end:
            raise ExtractionError(
                "timeout", f"Processing took too long (stopped during {stage}). Try a smaller document."
            )


_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def concept_key(term: str) -> str:
    """Lowercase phrase used for matching, without a trailing acronym: "TF-IDF (term weighting)" -> "tf-idf"."""
    return _PAREN_RE.sub(" ", term).strip().lower()


def _rerank_concepts(
    sections: list[Section],
    kp_scored: list[list[tuple[str, float]]],
    definitions: list[Definition],
    forms: dict[str, str],
) -> tuple[list[list[tuple[str, float]]], set[str]]:
    """Boost phrases that the author marked as important (headings, defined terms) and pick strong concepts.

    Strong concepts are the only phrases used as quiz answers: defined terms, phrases that occur in a
    heading, recurring multi-word phrases, and acronyms / distinctively cased terms.
    """
    def_keys: dict[str, str] = {}
    for d in definitions:
        key = concept_key(d.term)
        def_keys[key] = d.term
        forms.setdefault(key, _PAREN_RE.sub(" ", d.term).strip())
    headings = " \n ".join(s.title for s in sections)
    strong: set[str] = set(def_keys)
    reranked: list[list[tuple[str, float]]] = []
    for i, (section, row) in enumerate(zip(sections, kp_scored, strict=False)):
        boosted: dict[str, float] = {}
        top = row[0][1] if row else 1.0
        for phrase, score in row:
            in_heading = contains_phrase(section.title, phrase)
            is_def = phrase in def_keys
            single = " " not in phrase
            if single and phrase.endswith(("ing", "ed")) and not (in_heading or is_def):
                continue
            boosted[phrase] = score * (2.0 if in_heading else 1.0) * (2.5 if is_def else 1.0)
            form = forms.get(phrase, phrase)
            distinctive = any(c.isupper() for c in form[1:]) or any(c.isdigit() for c in form)
            if is_def or contains_phrase(headings, phrase) or not single or distinctive:
                strong.add(phrase)
        for d in definitions:
            key = concept_key(d.term)
            if d.section_index == i and key not in boosted and word_count(key) <= 5:
                boosted[key] = top * 2.5
        reranked.append(sorted(boosted.items(), key=lambda x: -x[1]))
    return reranked, strong


def process(extraction: ExtractionResult, timeout_seconds: float = 120) -> ProcessedDocument:
    deadline = _Deadline(timeout_seconds)
    sections, method = segment(extraction.blocks, extraction.file_type)
    if not sections:
        raise ExtractionError("no_topics", "No topics could be identified in this document.")
    deadline.check("segmentation")

    kp_scored = topic_keyphrases([s.text for s in sections])
    all_phrases = {p for row in kp_scored for p, _ in row}
    full_text = "\n\n".join(s.text for s in sections)
    forms = surface_forms(full_text, all_phrases)
    for section, row in zip(sections, kp_scored, strict=False):
        if not section.title:
            section.title = title_from_keyphrases([p for p, _ in row], forms)
            section.title_source = "keywords"
    deadline.check("keyphrase extraction")

    sentences_by_section: list[list[Sentence]] = []
    order = 0
    for i, section in enumerate(sections):
        sents = section_sentences(section, i, order)
        order += len(sents)
        sentences_by_section.append(sents)
    all_sentences = [s for group in sentences_by_section for s in group]
    kp_keys = {normalize_key(p) for p in all_phrases}
    definitions = extract_definitions(all_sentences, kp_keys)
    deadline.check("definition extraction")
    kp_scored, strong = _rerank_concepts(sections, kp_scored, definitions, forms)

    topics: list[ProcessedTopic] = []
    section_inputs: list[SectionInput] = []
    for i, section in enumerate(sections):
        keyphrases = [p for p, _ in kp_scored[i]]
        sec_defs = [d for d in definitions if d.section_index == i]
        guide = build_guide(section, sentences_by_section[i], keyphrases, forms, sec_defs)
        topics.append(
            ProcessedTopic(
                section_index=i,
                title=section.title,
                title_source=section.title_source,
                keywords=[forms.get(p, p) for p in keyphrases[:10]],
                location_start=section.location_start,
                location_end=section.location_end,
                word_count=section.words,
                guide=guide,
            )
        )
        scored = rank_sentences(sentences_by_section[i], keyphrases)
        ranked = [s for s, _ in sorted(scored, key=lambda x: -x[1])]
        section_inputs.append(
            SectionInput(i, section.title, sentences_by_section[i], ranked, keyphrases, mmr_select(scored, 6))
        )
        deadline.check("learning guide generation")

    chunks = chunk_sections(sections)
    deadline.check("chunking")

    generator = QuestionGenerator(section_inputs, definitions, forms, full_text, extraction.unit_label, strong)
    generated = generator.generate()
    deadline.check("question generation")

    by_type: dict[str, int] = {}
    for q in generated.questions:
        by_type[q.question_type] = by_type.get(q.question_type, 0) + 1
    rejected_total = sum(v for k, v in generated.rejected.items() if not k.endswith("_skipped"))
    stats = {
        "definitions": len(definitions),
        "sentences": len(all_sentences),
        "keyphrases": len(all_phrases),
        "questions_by_type": by_type,
        "rejected_total": rejected_total,
        "rejected_reasons": dict(generated.rejected.most_common()),
    }
    warnings = list(extraction.warnings)
    if not by_type.get("mcq"):
        warnings.append(
            "No multiple-choice questions passed validation. This usually means the material is short or has "
            "few distinct key terms to use as answer options."
        )
    return ProcessedDocument(
        unit_label=extraction.unit_label,
        unit_count=extraction.unit_count,
        word_count=extraction.word_count,
        heading_count=sum(1 for b in extraction.blocks if b.kind == "heading"),
        segmentation_method=method,
        topics=topics,
        chunks=chunks,
        questions=generated.questions,
        warnings=warnings,
        stats=stats,
    )
