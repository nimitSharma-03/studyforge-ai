from __future__ import annotations

import pytest

from app.nlp.extract import Block, extract
from app.nlp.guide import Sentence, extract_definitions
from app.nlp.keywords import candidate_phrases, topic_keyphrases
from app.nlp.pipeline import process
from app.nlp.questions import QuestionCandidate, validate
from app.nlp.retrieval import Passage, PassageIndex, answer_question
from app.nlp.segment import chunk_sections, segment
from app.nlp.text import contains_phrase, join_lines, normalize_text, split_sentences


@pytest.fixture(scope="module")
def processed(demo_pdf):
    return process(extract("demo.pdf", demo_pdf))


# ------------------------------------------------------------------ text


def test_normalize_text_handles_bullets_quotes_and_ligatures():
    assert normalize_text("•  The “ﬁrst”   point") == 'The "first" point'
    assert normalize_text("1) Numbered item") == "Numbered item"


def test_join_lines_repairs_hyphenation():
    assert join_lines(["Tokeniza-", "tion splits text", "into tokens."]) == "Tokenization splits text into tokens."
    assert join_lines(["state-of-", "the-art"]) == "state-of-the-art"
    assert join_lines(["Natural", "Language"]) == "Natural Language"


def test_sentence_split_respects_abbreviations():
    text = "Dr. Smith uses tools, e.g. NLTK. Results improved. Fig. 2 shows this."
    assert split_sentences(text) == ["Dr. Smith uses tools, e.g. NLTK.", "Results improved.", "Fig. 2 shows this."]


def test_phrase_matching_ignores_hyphenated_parts():
    assert not contains_phrase("hand-written rules", "written")
    assert contains_phrase("rules are written by hand", "written")
    assert contains_phrase("We use TF-IDF here", "tf-idf")


# ------------------------------------------------------------------ segmentation and chunking


def test_heading_segmentation_and_metadata(processed):
    titles = [t.title for t in processed.topics]
    assert titles[0] == "Introduction to Natural Language Processing"
    assert "Word Embeddings" in titles
    assert processed.segmentation_method == "headings"
    for t in processed.topics:
        assert 1 <= t.location_start <= t.location_end <= processed.unit_count


def test_chunks_never_cross_topics(processed):
    assert processed.chunks
    for chunk in processed.chunks:
        assert 0 <= chunk.section_index < len(processed.topics)
        topic = processed.topics[chunk.section_index]
        assert topic.location_start <= chunk.location_start <= chunk.location_end <= topic.location_end


def test_texttiling_fallback_splits_unstructured_text():
    astronomy = (
        "Stars form inside clouds of gas and dust. Gravity pulls the gas together until nuclear fusion begins. "
        "A star spends most of its life fusing hydrogen into helium in its core. Massive stars burn faster. "
    )
    cooking = (
        "Bread dough needs flour, water, yeast and salt. Kneading develops gluten which traps gas from the yeast. "
        "The dough rises while proofing and is then baked in a hot oven until the crust browns. "
    )
    law = (
        "A contract requires an offer, acceptance and consideration. Courts examine whether both parties intended "
        "to create legal relations. Breach of contract can lead to damages or specific performance. "
    )
    blocks = [Block(astronomy * 2, "paragraph", 0, 1) for _ in range(4)]
    blocks += [Block(cooking * 2, "paragraph", 0, 2) for _ in range(4)]
    blocks += [Block(law * 2, "paragraph", 0, 3) for _ in range(4)]
    sections, method = segment(blocks, "pdf")
    assert "texttiling" in method
    assert len(sections) >= 2
    # No section should mix astronomy and law text.
    for s in sections:
        assert not ("nuclear fusion" in s.text and "contract" in s.text)
    chunks = chunk_sections(sections)
    assert all(c.text for c in chunks)


def test_tiny_heading_sections_are_merged():
    blocks = [
        Block("Unit 1", "heading", 1, 1),
        Block("Lexical analysis", "heading", 1, 1),
        Block("Lexical analysis converts a stream of characters into tokens for the parser. " * 5, "paragraph", 0, 1),
        Block("Parsing", "heading", 1, 2),
        Block(
            "Parsing builds a syntax tree from the token stream using a formal grammar of the language. " * 5,
            "paragraph",
            0,
            2,
        ),
    ]
    sections, _ = segment(blocks, "pdf")
    assert [s.title for s in sections] == ["Lexical analysis", "Parsing"]


# ------------------------------------------------------------------ keywords and definitions


def test_candidate_phrases_split_on_stopwords_and_verbs():
    phrases = candidate_phrases("Removing stop words reduces the vocabulary size.")
    assert "stop words" in phrases
    assert "removing" not in phrases
    assert all("the" not in p.split() for p in phrases)


def test_topic_keyphrases_are_topic_specific():
    texts = [
        "Tokenization splits text into tokens. Tokenization handles abbreviations. Tokens are words.",
        "Cosine similarity compares vectors. Cosine similarity ranks documents by angle between vectors.",
    ]
    rows = topic_keyphrases(texts)
    assert rows[0][0][0] in {"tokenization", "tokens"}
    assert "cosine similarity" in [p for p, _ in rows[1]]


def test_definition_patterns():
    sents = [
        Sentence(t, 1, i, 0)
        for i, t in enumerate(
            [
                "Tokenization is the process of splitting text into tokens.",
                "Perplexity refers to how well a model predicts a held-out sample.",
                "Stemming: removing suffixes to obtain a crude root form of a word.",
                "This is a very important idea that students should remember.",
                "The result is a list of numbers that nobody can interpret easily.",
            ]
        )
    ]
    defs = extract_definitions(sents, set())
    terms = [d.term for d in defs]
    assert terms == ["Tokenization", "Perplexity", "Stemming"]
    assert defs[0].definition.startswith("the process of splitting")


def test_learning_guide_is_extractive_and_referenced(processed, demo_pdf):
    source_text = " ".join(b.text for b in extract("demo.pdf", demo_pdf).blocks)
    guide = processed.topics[5].guide  # TF-IDF topic
    assert guide["method"] == "extractive-rule-based"
    assert guide["overview"] and guide["key_points"] and guide["definitions"]
    for section in ("overview", "key_points", "examples", "relationships"):
        for item in guide[section]:
            assert item["text"] in source_text  # verbatim from the document
            assert isinstance(item["location"], int)
    terms = {d["term"] for d in guide["definitions"]}
    assert {"TF-IDF", "Cosine similarity"} <= terms


# ------------------------------------------------------------------ questions


def test_mcqs_have_four_options_and_one_valid_answer(processed):
    mcqs = [q for q in processed.questions if q.question_type == "mcq"]
    assert len(mcqs) >= 20
    for q in mcqs:
        assert len(q.options) == 4
        assert len({o.lower() for o in q.options}) == 4
        assert 0 <= q.correct_index < 4
        assert q.options[q.correct_index] == q.answer_text
        assert q.explanation and q.evidence
        assert q.difficulty in {"easy", "medium", "hard"}
        assert validate(q) == (True, "ok")


def test_cloze_answers_come_from_the_source_sentence(processed):
    cloze = [q for q in processed.questions if q.stem.startswith("Fill in the blank")]
    assert cloze
    for q in cloze:
        assert q.answer_text.lower() in q.evidence.lower()
        assert "_____" in q.stem
        assert q.answer_text.lower() not in q.stem.lower().replace("fill in the blank:", "")


def test_all_question_types_are_generated(processed):
    types = {q.question_type for q in processed.questions}
    categories = {q.category for q in processed.questions}
    assert types == {"mcq", "short_answer", "long_answer"}
    assert {"definition", "factual", "conceptual", "revision"} <= categories


def test_no_duplicate_questions(processed):
    stems = [q.stem.lower() for q in processed.questions]
    assert len(stems) == len(set(stems))


def test_answer_distribution_is_not_constant(processed):
    positions = {q.correct_index for q in processed.questions if q.question_type == "mcq"}
    assert len(positions) >= 3


def _mcq(**overrides) -> QuestionCandidate:
    base = dict(
        question_type="mcq",
        category="factual",
        difficulty="medium",
        stem="Fill in the blank: _____ splits text into smaller units called tokens.",
        answer_text="Tokenization",
        explanation="x",
        evidence="Tokenization splits text into smaller units called tokens.",
        location=1,
        location_end=1,
        section_index=0,
        options=["Tokenization", "Stemming", "Lemmatization", "Parsing"],
        correct_index=0,
    )
    base.update(overrides)
    return QuestionCandidate(**base)


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"options": ["Tokenization", "Stemming", "Parsing"]}, "option_count"),
        ({"options": ["Tokenization", "Stemming", "stemming", "Parsing"]}, "duplicate_options"),
        ({"correct_index": 1}, "answer_mapping"),
        ({"correct_index": 7}, "answer_mapping"),
        ({"evidence": "Something unrelated entirely about grammar rules."}, "answer_not_in_source"),
        (
            {
                "options": [
                    "Tokenization",
                    "Stemming",
                    "Lemmatization",
                    "a very long distractor option that is clearly much longer than all",
                ]
            },
            "length_imbalance",
        ),
        ({"options": ["Tokenization", "tokens", "Lemmatization", "Parsing"]}, "option_in_stem"),
    ],
)
def test_validator_rejects_bad_mcqs(overrides, reason):
    assert validate(_mcq(**overrides)) == (False, reason)


def test_validator_accepts_good_mcq():
    assert validate(_mcq()) == (True, "ok")


# ------------------------------------------------------------------ retrieval


def _index() -> PassageIndex:
    return PassageIndex(
        [
            Passage(
                1,
                "Tokenization splits text into tokens such as words and punctuation.",
                "Tokenization",
                10,
                "page",
                1,
                1,
            ),
            Passage(
                2,
                "Cosine similarity measures the angle between two vectors and ranks documents.",
                "Similarity",
                11,
                "page",
                2,
                2,
            ),
            Passage(
                3, "Precision is the fraction of predicted positives that are correct.", "Evaluation", 12, "page", 3, 3
            ),
        ]
    )


def test_tfidf_retrieval_ranks_relevant_passage_first():
    hits = _index().search("how are documents ranked using vectors?")
    assert hits[0][0].chunk_id == 2
    assert hits[0][1] > 0


def test_retrieval_respects_topic_filter():
    hits = _index().search("tokens and vectors", topic_id=12)
    assert all(p.topic_id == 12 for p, _ in hits)


def test_answer_verdicts():
    index = _index()
    supported = answer_question("What does cosine similarity measure between vectors?", index, [])
    assert supported["verdict"] == "supported"
    assert supported["answer"][0]["location"] == 2
    unrelated = answer_question("Who painted the Mona Lisa?", index, [])
    assert unrelated["verdict"] == "insufficient"
    assert unrelated["answer"] == []


def test_definition_lookup_in_qa():
    defs = [
        {
            "term": "Precision",
            "text": "Precision is the fraction of predicted positives that are correct.",
            "location": 3,
            "location_type": "page",
            "topic_id": 12,
        }
    ]
    result = answer_question("What is precision?", _index(), defs)
    assert result["verdict"] == "supported"
    assert result["answer"][0]["text"].startswith("Precision is")
