"""Rule-based question generation with validation.

Generators produce candidates from source sentences (definitions, cloze deletions,
example lists, cue-phrase patterns and topic outlines). Every candidate then passes
through ``validate`` which rejects ambiguous or low-quality items instead of keeping
plausible-looking but indefensible questions. Rejection reasons are counted so the
pipeline can report them honestly.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter
from dataclasses import dataclass, field

from app.nlp.guide import Definition, Sentence
from app.nlp.text import (
    PRONOUN_START_RE,
    contains_phrase,
    content_words,
    count_phrase,
    light_stem,
    normalize_key,
    phrase_pattern,
    truncate_words,
    word_count,
)

BLANK = "_____"


@dataclass
class QuestionCandidate:
    question_type: str  # mcq | short_answer | long_answer
    category: str  # definition | factual | conceptual | application | revision
    difficulty: str  # easy | medium | hard
    stem: str
    answer_text: str
    explanation: str
    evidence: str
    location: int
    location_end: int
    section_index: int
    options: list[str] | None = None
    correct_index: int | None = None
    option_notes: list[str | None] | None = None
    quality: float = 0.5
    answer_key: str = ""  # used for duplicate detection

    @property
    def stem_hash(self) -> str:
        return hashlib.sha256(normalize_key(self.stem).encode()).hexdigest()


@dataclass
class SectionInput:
    index: int
    title: str
    sentences: list[Sentence]
    ranked: list[Sentence]  # sentences ordered by importance
    keyphrases: list[str]  # lowercase, ordered by score
    key_points: list[Sentence] = field(default_factory=list)


@dataclass
class GenerationResult:
    questions: list[QuestionCandidate]
    rejected: Counter


def _loc_label(location_label: str, n: int) -> str:
    return f"{location_label} {n}"


def _stems(text: str) -> set[str]:
    return {light_stem(w) for w in content_words(text)}


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


class QuestionGenerator:
    def __init__(
        self,
        sections: list[SectionInput],
        definitions: list[Definition],
        forms: dict[str, str],
        full_text: str,
        unit_label: str,
        strong: set[str] | None = None,
    ):
        self.sections = sections
        self.strong = strong if strong is not None else {kp for sec in sections for kp in sec.keyphrases}
        self.definitions = definitions
        self.forms = forms
        self.full_text_key = normalize_key(full_text)
        self.unit_label = unit_label.capitalize()
        self.rejected: Counter = Counter()
        self.all_sentences = [s for sec in sections for s in sec.sentences]
        self.phrase_pool: list[tuple[str, int, int]] = []  # (phrase, section index, rank)
        for sec in sections:
            for rank, kp in enumerate(sec.keyphrases):
                self.phrase_pool.append((kp, sec.index, rank))
        self.titles = {sec.index: sec.title for sec in sections}
        self.def_text = {normalize_key(re.sub(r"\([^)]*\)", " ", d.term)): d.definition for d in definitions}

    # ------------------------------------------------------------------ helpers

    def form(self, phrase: str) -> str:
        return self.forms.get(phrase, phrase)

    def loc(self, n: int) -> str:
        return _loc_label(self.unit_label, n)

    def _compatible(self, answer: str, cand: str, context: str, chosen: list[str]) -> bool:
        ak, ck = normalize_key(answer), normalize_key(cand)
        if not ck or ak == ck or ak in ck or ck in ak:
            return False
        if contains_phrase(context, cand):
            return False
        if _stems(answer) & _stems(cand):
            return False
        if abs(word_count(answer) - word_count(cand)) > 2:
            return False
        if self.related(answer, cand):
            return False
        for c in chosen:
            if normalize_key(c) == ck or _stems(c) & _stems(cand):
                return False
        return True

    def related(self, a: str, b: str) -> bool:
        """True when two concepts are too close to serve as each other's distractor.

        Covers shared word roots (tokenizer / tokenization) and concepts defined in terms of each
        other ("Porter stemmer: a ... stemming algorithm").
        """
        if _shares_prefix(a, b):
            return True
        for x, y in ((a, b), (b, a)):
            definition = self.def_text.get(normalize_key(re.sub(r"\([^)]*\)", " ", x)))
            if definition and (_stems(y) <= _stems(definition) or _shares_prefix(definition, y)):
                return True
        return False

    def pick_phrase_distractors(
        self, answer: str, context: str, section_index: int, n: int = 3, blank_prefix: str | None = None
    ) -> tuple[list[str], int] | None:
        """Pick keyphrase distractors; returns (distractors, number taken from the same topic)."""
        plural = _is_plural(answer)
        ranked = sorted(
            self.phrase_pool,
            key=lambda p: (
                p[0] not in self.strong,
                _is_plural(p[0]) != plural,
                p[1] != section_index,
                abs(p[0].count(" ") - answer.count(" ")),
                _jitter(answer, p[0]),
            ),
        )
        chosen: list[str] = []
        same = 0
        for phrase, sec_idx, _rank in ranked:
            cand = self.form(phrase)
            if not self._compatible(answer, cand, context, chosen):
                continue
            if blank_prefix is not None:
                # Ambiguity check: would the distractor also complete a sentence that exists in the notes?
                probe = normalize_key(f"{blank_prefix} {cand}")
                if len(probe.split()) >= 3 and probe in self.full_text_key:
                    self.rejected["ambiguous_distractor_skipped"] += 1
                    continue
            chosen.append(cand)
            same += sec_idx == section_index
            if len(chosen) == n:
                return chosen, same
        return None

    def _shuffle(
        self, correct: str, distractors: list[str], notes: list[str | None], seed: str
    ) -> tuple[list[str], int, list[str | None]]:
        rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))
        items = [(correct, None, True)] + [(d, n, False) for d, n in zip(distractors, notes, strict=False)]
        rng.shuffle(items)
        options = [i[0] for i in items]
        correct_index = next(k for k, i in enumerate(items) if i[2])
        option_notes = [i[1] for i in items]
        return options, correct_index, option_notes

    def _phrase_note(self, phrase: str) -> str | None:
        key = normalize_key(phrase)
        d = next((d for d in self.definitions if normalize_key(d.term) == key), None)
        if d:
            return f'{d.term} is a different concept: "{truncate_words(d.definition, 20)}" ({self.loc(d.location)}).'
        sec = next((p[1] for p in self.phrase_pool if normalize_key(self.form(p[0])) == key), None)
        if sec is not None:
            return f'"{phrase}" is discussed under "{self.titles[sec]}" but does not fit this statement.'
        return None

    # ------------------------------------------------------------------ generators

    def definition_questions(self) -> list[QuestionCandidate]:
        out: list[QuestionCandidate] = []
        for d in self.definitions:
            masked = phrase_pattern(d.term).sub(BLANK, d.definition)
            # (1) Which term matches this description?
            term_pool = [
                x.term
                for x in sorted(
                    (x for x in self.definitions if x is not d),
                    key=lambda x: (x.section_index != d.section_index, _jitter(d.term, x.term)),
                )
            ]
            chosen: list[str] = []
            for t in term_pool:
                if self._compatible(d.term, t, masked, chosen):
                    chosen.append(t)
                if len(chosen) == 3:
                    break
            if len(chosen) < 3:
                extra = self.pick_phrase_distractors(d.term, masked, d.section_index, 3 - len(chosen))
                if extra:
                    chosen += [e for e in extra[0] if self._compatible(d.term, e, masked, chosen)]
            if len(chosen) >= 3:
                chosen = chosen[:3]
                notes = [self._phrase_note(c) for c in chosen]
                stem = f'Which term matches this description from your notes: "{_cap(masked)}"?'
                options, ci, onotes = self._shuffle(d.term, chosen, notes, stem)
                out.append(
                    QuestionCandidate(
                        "mcq",
                        "definition",
                        "easy",
                        stem,
                        d.term,
                        f'Your notes define {d.term} as "{d.definition}" ({self.loc(d.location)}).',
                        d.sentence,
                        d.location,
                        d.location,
                        d.section_index,
                        options,
                        ci,
                        onotes,
                        quality=0.75 if d.strength == "strong" else 0.6,
                        answer_key=f"term:{normalize_key(d.term)}",
                    )
                )
            else:
                self.rejected["insufficient_distractors"] += 1

            # (2) Which statement best describes the term?
            correct_def = _cap(d.definition)
            if word_count(correct_def) <= 32:
                others = [x for x in self.definitions if x is not d and not self.related(d.term, x.term)]
                others.sort(
                    key=lambda x: (
                        x.section_index != d.section_index,
                        abs(word_count(x.definition) - word_count(d.definition)),
                    )
                )
                distractors: list[str] = []
                notes2: list[str | None] = []
                for x in others:
                    text = _cap(x.definition)
                    if word_count(text) > 32 or normalize_key(text) == normalize_key(correct_def):
                        continue
                    distractors.append(text)
                    notes2.append(f"This describes {x.term} ({self.loc(x.location)}), not {d.term}.")
                    if len(distractors) == 3:
                        break
                if len(distractors) == 3:
                    stem = f"Which of the following best describes {d.term}?"
                    options, ci, onotes = self._shuffle(correct_def, distractors, notes2, stem)
                    out.append(
                        QuestionCandidate(
                            "mcq",
                            "definition",
                            "medium",
                            stem,
                            correct_def,
                            f'Your notes define {d.term} as "{d.definition}" ({self.loc(d.location)}).',
                            d.sentence,
                            d.location,
                            d.location,
                            d.section_index,
                            options,
                            ci,
                            onotes,
                            quality=0.7,
                            answer_key=f"def:{normalize_key(d.term)}",
                        )
                    )
                elif len(self.definitions) >= 4:
                    self.rejected["insufficient_distractors"] += 1

            # (3) Short answer: Define the term.
            out.append(
                QuestionCandidate(
                    "short_answer",
                    "definition",
                    "easy",
                    f"Define {d.term}.",
                    _cap(d.definition) + ".",
                    f"Model answer taken from your notes ({self.loc(d.location)}).",
                    d.sentence,
                    d.location,
                    d.location,
                    d.section_index,
                    quality=0.65,
                    answer_key=f"define:{normalize_key(d.term)}",
                )
            )
        return out

    def cloze_questions(self, per_section: int = 6) -> list[QuestionCandidate]:
        out: list[QuestionCandidate] = []
        def_sentences = {normalize_key(d.sentence) for d in self.definitions}
        def_terms = {
            normalize_key(d.sentence): normalize_key(re.sub(r"\([^)]*\)", " ", d.term)) for d in self.definitions
        }
        for sec in self.sections:
            made = 0
            used_answers: set[str] = set()
            for sent in sec.ranked[:24]:
                if made >= per_section:
                    break
                text = sent.text
                n = word_count(text)
                if n < 8 or n > 45:
                    self.rejected["sentence_length"] += 1
                    continue
                if PRONOUN_START_RE.match(text):
                    self.rejected["pronoun_reference"] += 1
                    continue
                if text.endswith("?"):
                    continue
                candidates = [kp for kp in sec.keyphrases if kp in self.strong and count_phrase(text, kp) == 1]
                candidates += [
                    p
                    for p, s, _ in self.phrase_pool
                    if s != sec.index and p in self.strong and count_phrase(text, p) == 1 and p not in candidates
                ]
                candidates = [c for c in candidates if normalize_key(c) not in used_answers]
                if not candidates:
                    continue
                candidates.sort(key=lambda c: -c.count(" "))  # prefer specific multi-word phrases
                answer_phrase = candidates[0]
                match = phrase_pattern(answer_phrase).search(text)
                if not match:
                    continue
                answer = match.group(0)
                if def_terms.get(normalize_key(text)) == normalize_key(answer):
                    continue  # already covered by the "which term matches this description" question
                end = match.end()
                acronym = re.match(r"\s*\([A-Z][A-Za-z0-9\-]{1,10}\)", text[end:])
                if acronym:
                    end += acronym.end()  # hide "(NLP)" too, it would give the answer away
                blanked = text[: match.start()] + BLANK + text[end:]
                remaining = [w for w in content_words(blanked)]
                if len(remaining) < 4:
                    self.rejected["low_context"] += 1
                    continue
                prefix = " ".join(text[: match.start()].split()[-3:])
                picked = self.pick_phrase_distractors(answer, text, sec.index, 3, blank_prefix=prefix or None)
                if not picked:
                    self.rejected["insufficient_distractors"] += 1
                    continue
                distractors, same = picked
                if answer[:1].islower():
                    distractors = [
                        d if any(ch.isupper() or ch.isdigit() for ch in d[1:]) else d.lower() for d in distractors
                    ]
                notes = [self._phrase_note(d) for d in distractors]
                stem = f"Fill in the blank: {blanked}"
                options, ci, onotes = self._shuffle(answer, distractors, notes, stem)
                hard = same >= 2 or n > 28
                is_def = normalize_key(text) in def_sentences
                out.append(
                    QuestionCandidate(
                        "mcq",
                        "factual",
                        "hard" if hard and not is_def else ("easy" if is_def else "medium"),
                        stem,
                        answer,
                        f'The original statement in your notes reads: "{text}" ({self.loc(sent.location)}).',
                        text,
                        sent.location,
                        sent.location,
                        sec.index,
                        options,
                        ci,
                        onotes,
                        quality=0.55 + 0.1 * same + (0.1 if answer.count(" ") else 0.0),
                        answer_key=f"cloze:{normalize_key(text)}",
                    )
                )
                used_answers.add(normalize_key(answer))
                made += 1
        return out

    _SUCH_AS = re.compile(
        r"(?P<head>[A-Za-z][A-Za-z0-9\- ]{2,80}?)\s*,?\s+(?:such as|including|e\.g\.,?)\s+(?P<items>[^.;:()]+)", re.I
    )

    def example_questions(self) -> list[QuestionCandidate]:
        out: list[QuestionCandidate] = []
        known = {kp for sec in self.sections for kp in sec.keyphrases}
        for sent in self.all_sentences:
            m = self._SUCH_AS.search(sent.text)
            if not m:
                continue
            head_words = m.group("head").split()[-4:]
            head = None
            for k in range(len(head_words)):
                cand = " ".join(head_words[k:]).lower()
                if cand in known and cand in self.strong:
                    head = " ".join(head_words[k:])
                    break
            if not head:
                continue
            items = [i.strip(" ,") for i in re.split(r",|\band\b|\bor\b", m.group("items")) if i.strip(" ,")]
            items = [i for i in items if 1 <= word_count(i) <= 4]
            if len(items) < 2:
                continue
            correct = items[0]
            co_occurring = [s.text for s in self.all_sentences if contains_phrase(s.text, head)]
            chosen: list[str] = []
            for phrase, _sec, _rank in sorted(self.phrase_pool, key=lambda p: p[2]):
                cand = self.form(phrase)
                if any(contains_phrase(t, cand) for t in co_occurring):
                    continue
                if any(normalize_key(cand) == normalize_key(i) for i in items):
                    continue
                if self._compatible(correct, cand, sent.text, chosen):
                    chosen.append(cand)
                if len(chosen) == 3:
                    break
            if len(chosen) < 3:
                self.rejected["insufficient_distractors"] += 1
                continue
            stem = f"According to your notes, which of the following is given as an example of {head}?"
            notes = [f'"{c}" is not mentioned alongside {head} in your notes.' for c in chosen]
            options, ci, onotes = self._shuffle(correct, chosen, notes, stem + correct)
            out.append(
                QuestionCandidate(
                    "mcq",
                    "application",
                    "medium",
                    stem,
                    correct,
                    f'Your notes list examples of {head}: "{sent.text}" ({self.loc(sent.location)}).',
                    sent.text,
                    sent.location,
                    sent.location,
                    sent.section_index,
                    options,
                    ci,
                    onotes,
                    quality=0.6,
                    answer_key=f"example:{normalize_key(head)}:{normalize_key(correct)}",
                )
            )
        return out

    _USED_FOR = re.compile(
        r"^(?P<x>[A-Z][A-Za-z0-9\-' ]{2,60}?)\s+(?:is|are)\s+(?:mainly\s+|commonly\s+|often\s+|widely\s+)?"
        r"used\s+(?:to|for)\s+(?P<y>.{8,})$"
    )
    _CONSISTS = re.compile(
        r"^(?P<x>[A-Z][A-Za-z0-9\-' ]{2,60}?)\s+(?:consists?|is composed|are composed)\s+of\s+(?P<y>.{8,})$"
    )
    _BECAUSE = re.compile(r"^(?P<a>.{15,}?),?\s+because\s+(?P<b>.{8,})$", re.I)
    _ADVANTAGE = re.compile(
        r"^(?:the\s+|one\s+)?(?:main\s+|key\s+|major\s+)?(?P<kind>advantages?|benefits?|disadvantages?|limitations?|drawbacks?|weakness(?:es)?|strengths?)\s+of\s+(?P<x>.{3,60}?)\s+(?:is|are|include|includes)\s+(?P<y>.{8,})$",
        re.I,
    )
    _CONTRAST = re.compile(r"\b(whereas|unlike|in contrast|differs? from|compared (?:to|with)|while)\b", re.I)

    def pattern_questions(self) -> list[QuestionCandidate]:
        out: list[QuestionCandidate] = []
        for sent in self.all_sentences:
            text = sent.text.rstrip(".")
            loc = self.loc(sent.location)
            for pattern, template, category in (
                (self._USED_FOR, "What is {x} used for, according to your notes?", "application"),
                (self._CONSISTS, "What does {x} consist of?", "conceptual"),
            ):
                m = pattern.match(text)
                if m and not PRONOUN_START_RE.match(m.group("x")) and word_count(m.group("x")) <= 6:
                    x = m.group("x").strip()
                    out.append(
                        QuestionCandidate(
                            "short_answer",
                            category,
                            "medium",
                            template.format(x=x),
                            _cap(m.group("y")) + ".",
                            f"Answer taken from your notes ({loc}).",
                            sent.text,
                            sent.location,
                            sent.location,
                            sent.section_index,
                            quality=0.6,
                            answer_key=f"pattern:{normalize_key(sent.text)}",
                        )
                    )
            m = self._ADVANTAGE.match(text)
            if m:
                kind = m.group("kind").lower()
                kind = kind if kind.endswith("s") else kind + "s"
                out.append(
                    QuestionCandidate(
                        "short_answer",
                        "conceptual",
                        "medium",
                        f"What are the {kind} of {m.group('x').strip()}?",
                        _cap(m.group("y")) + ".",
                        f"Answer taken from your notes ({loc}).",
                        sent.text,
                        sent.location,
                        sent.location,
                        sent.section_index,
                        quality=0.65,
                        answer_key=f"adv:{normalize_key(sent.text)}",
                    )
                )
            m = self._BECAUSE.match(text)
            if m and not PRONOUN_START_RE.match(m.group("a")):
                out.append(
                    QuestionCandidate(
                        "short_answer",
                        "conceptual",
                        "medium",
                        f'Explain why the following holds: "{_cap(m.group("a").strip())}."',
                        _cap(m.group("b")) + ".",
                        f"Reasoning stated in your notes ({loc}).",
                        sent.text,
                        sent.location,
                        sent.location,
                        sent.section_index,
                        quality=0.6,
                        answer_key=f"why:{normalize_key(sent.text)}",
                    )
                )
        # Compare-and-contrast long answers from contrast sentences that mention two concepts.
        seen_pairs: set[tuple[str, str]] = set()
        for sec in self.sections:
            for sent in sec.sentences:
                if not self._CONTRAST.search(sent.text):
                    continue
                present = [
                    kp for kp, _s, _r in self.phrase_pool if kp in self.strong and contains_phrase(sent.text, kp)
                ]
                present = [p for i, p in enumerate(present) if not any(p in q and p != q for q in present)]
                uniq: list[str] = []
                for p in present:
                    if not any(_stems(p) & _stems(q) for q in uniq):
                        uniq.append(p)
                if len(uniq) < 2:
                    continue
                a, b = self.form(uniq[0]), self.form(uniq[1])
                pair = tuple(sorted((normalize_key(a), normalize_key(b))))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                answer_lines = [f"- {sent.text} ({self.loc(sent.location)})"]
                for term in (a, b):
                    d = next((d for d in self.definitions if normalize_key(d.term) == normalize_key(term)), None)
                    if d:
                        answer_lines.append(f"- {d.term}: {d.definition} ({self.loc(d.location)})")
                out.append(
                    QuestionCandidate(
                        "long_answer",
                        "conceptual",
                        "hard",
                        f"Compare and contrast {a} and {b}.",
                        "\n".join(answer_lines),
                        "Outline built from the statements in your notes that relate the two concepts.",
                        sent.text,
                        sent.location,
                        sent.location,
                        sec.index,
                        quality=0.65,
                        answer_key=f"compare:{pair[0]}:{pair[1]}",
                    )
                )
        return out

    def topic_questions(self) -> list[QuestionCandidate]:
        out: list[QuestionCandidate] = []
        for sec in self.sections:
            points = sec.key_points[:6]
            if len(points) < 2:
                continue
            kps = [self.form(k) for k in sec.keyphrases if k in self.strong][:3]
            outline = "\n".join(f"- {p.text} ({self.loc(p.location)})" for p in points)
            evidence = " ".join(p.text for p in points[:3])
            start = min(p.location for p in points)
            end = max(p.location for p in points)
            if len(points) >= 4 and len(kps) >= 3:
                stem = f"Explain {sec.title} in detail. Your answer should cover {kps[0]}, {kps[1]} and {kps[2]}."
                out.append(
                    QuestionCandidate(
                        "long_answer",
                        "conceptual",
                        "hard",
                        stem,
                        outline,
                        "Model answer outline assembled from the key points of this topic in your notes.",
                        evidence,
                        start,
                        end,
                        sec.index,
                        quality=0.7,
                        answer_key=f"explain:{sec.index}",
                    )
                )
            out.append(
                QuestionCandidate(
                    "long_answer",
                    "revision",
                    "medium",
                    f"Write short notes on {sec.title}.",
                    outline,
                    "Model answer outline assembled from the key points of this topic in your notes.",
                    evidence,
                    start,
                    end,
                    sec.index,
                    quality=0.6,
                    answer_key=f"notes:{sec.index}",
                )
            )
            defined = {normalize_key(d.term) for d in self.definitions}
            for kp in [k for k in sec.keyphrases if k in self.strong][:4]:
                if normalize_key(kp) in defined:
                    continue
                support = next(
                    (s for s in sec.ranked if contains_phrase(s.text, kp) and not PRONOUN_START_RE.match(s.text)), None
                )
                if support is None:
                    continue
                out.append(
                    QuestionCandidate(
                        "short_answer",
                        "revision",
                        "easy",
                        f"Briefly explain {self.form(kp)} as described in your notes on {sec.title}.",
                        support.text,
                        f"Answer taken from your notes ({self.loc(support.location)}).",
                        support.text,
                        support.location,
                        support.location,
                        sec.index,
                        quality=0.5,
                        answer_key=f"brief:{normalize_key(kp)}",
                    )
                )
        return out

    # ------------------------------------------------------------------ pipeline

    def generate(self) -> GenerationResult:
        candidates = (
            self.definition_questions()
            + self.cloze_questions()
            + self.example_questions()
            + self.pattern_questions()
            + self.topic_questions()
        )
        accepted: list[QuestionCandidate] = []
        seen_hashes: set[str] = set()
        seen_keys: set[str] = set()
        stem_tokens: list[tuple[str, set[str]]] = []
        for q in sorted(candidates, key=lambda q: -q.quality):
            ok, reason = validate(q)
            if not ok:
                self.rejected[reason] += 1
                continue
            if q.stem_hash in seen_hashes or q.answer_key in seen_keys:
                self.rejected["duplicate"] += 1
                continue
            tokens = set(normalize_key(q.stem).split())
            if any(t == q.question_type and _jaccard(tokens, other) >= 0.85 for t, other in stem_tokens):
                self.rejected["near_duplicate"] += 1
                continue
            seen_hashes.add(q.stem_hash)
            seen_keys.add(q.answer_key)
            stem_tokens.append((q.question_type, tokens))
            accepted.append(q)
        accepted.sort(key=lambda q: (q.section_index, q.location, q.question_type))
        return GenerationResult(accepted, self.rejected)


def _jitter(a: str, b: str) -> int:
    """Deterministic pseudo-random tie-breaker so the same distractors are not reused everywhere."""
    return int(hashlib.md5(f"{a.lower()}|{b.lower()}".encode()).hexdigest()[:6], 16)


def _shares_prefix(a: str, b: str, n: int = 5) -> bool:
    wa = [w.lower() for w in content_words(a) if len(w) >= n]
    wb = [w.lower() for w in content_words(b) if len(w) >= n]
    return any(x[:n] == y[:n] for x in wa for y in wb)


def _is_plural(phrase: str) -> bool:
    last = phrase.split()[-1].lower() if phrase.split() else ""
    return len(last) > 3 and last.endswith("s") and not last.endswith(("ss", "us", "is", "ics"))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def validate(q: QuestionCandidate) -> tuple[bool, str]:
    """Structural and source checks applied to every generated question."""
    if not q.stem.strip() or not q.answer_text.strip() or not q.evidence.strip():
        return False, "missing_fields"
    if q.question_type == "mcq":
        opts = q.options or []
        if len(opts) != 4:
            return False, "option_count"
        if any(not o.strip() for o in opts):
            return False, "empty_option"
        if len({normalize_key(o) for o in opts}) != 4:
            return False, "duplicate_options"
        if q.correct_index is None or not 0 <= q.correct_index < 4:
            return False, "answer_mapping"
        if normalize_key(opts[q.correct_index]) != normalize_key(q.answer_text):
            return False, "answer_mapping"
        if word_count(q.stem) < 6:
            return False, "stem_too_short"
        if q.category in {"factual", "application"} or (q.category == "definition" and q.difficulty == "easy"):
            if normalize_key(q.answer_text) not in normalize_key(q.evidence):
                return False, "answer_not_in_source"
        for i, o in enumerate(opts):
            if i != q.correct_index and word_count(o) > 2 and contains_phrase(q.evidence, o):
                return False, "distractor_in_source_statement"
        lengths = [word_count(o) for o in opts]
        if max(lengths) > 2.5 * min(lengths) + 2:
            return False, "length_imbalance"
        stem_body = q.stem.split(":", 1)[-1]
        if any(contains_phrase(stem_body, o) for o in opts if word_count(o) <= 4):
            return False, "option_in_stem"
    else:
        if word_count(q.stem) < 2:
            return False, "stem_too_short"
        if word_count(q.answer_text) < 3:
            return False, "answer_too_short"
    return True, "ok"
