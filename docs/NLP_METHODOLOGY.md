# NLP Methodology

StudyForge AI uses deterministic, CPU-only NLP. Every component is rule-based or classical-statistical (TF-IDF, cosine similarity), so results are reproducible, explainable and require no model download. Source: [`backend/app/nlp/`](../backend/app/nlp/).

| Stage | Module |
| --- | --- |
| Extraction | `extract.py` |
| Normalisation, sentences, tokens | `text.py` |
| Topic segmentation and chunking | `segment.py` |
| Keyphrases | `keywords.py` |
| Definitions, ranking, learning guides | `guide.py` |
| Question generation and validation | `questions.py` |
| Retrieval and question answering | `retrieval.py` |
| Orchestration | `pipeline.py` |
| Optional local LLM | `llm.py` |

---

## 1. Document extraction

The output of every extractor is an ordered list of **blocks** — `(text, kind ∈ {heading, paragraph}, level, location)` — where `location` is a 1-based page (PDF), section (DOCX) or slide (PPTX) number.

**File validation.** The extension must be `.pdf`, `.docx` or `.pptx` *and* the bytes must match: PDFs must start with `%PDF`; Office files must be ZIP archives containing `word/document.xml` or `ppt/presentation.xml`. A PPTX renamed to `.docx` is therefore rejected.

**PDF (PyMuPDF).** `page.get_text("dict")` gives text spans with font size and flags.
- *Body size* = the font size covering the most characters.
- A block is a **heading** if its size is ≥ 1.15 × body size (distinct larger sizes become levels 1–3) or if it is entirely bold, at most two lines and heading-like (≤ 12 words, no terminal punctuation).
- Blocks with ≥ 2 bullet-prefixed lines are split into one paragraph per bullet.
- **Running headers/footers**: short blocks (≤ 15 words) whose digit-normalised text appears on ≥ 50 % of pages (≥ 3 pages) are dropped, as are bare page numbers.
- A paragraph broken across a page boundary is re-joined when the first part lacks terminal punctuation and the continuation starts in lower case.
- **Scanned PDFs**: if the document has < 200 characters of text and at least one page with images but no text, extraction fails with a clear message (no OCR is bundled). Partially scanned documents produce a warning.
- Encrypted PDFs and PDFs over the page limit are rejected.

**DOCX (python-docx).** Body elements are walked in order so tables stay in place. `Title` and `Heading N` styles define headings; fully bold short paragraphs are treated as level-3 headings. Each heading starts a new *section* number. Table rows become `cell — cell` or `cell; cell; …` paragraphs.

**PPTX (python-pptx).** Each slide's title placeholder is a level-1 heading. Other shapes are read top-to-bottom, left-to-right; group shapes are recursed; tables are flattened; speaker notes with ≥ 4 words are included. Every block carries its slide number.

Documents with fewer than 40 words of text are rejected.

## 2. Normalisation and sentence segmentation

- Unicode **NFKC** (expands ligatures such as `ﬁ`), straight quotes, removal of soft hyphens and control characters, leading bullet/numbering removal, whitespace collapsing.
- **De-hyphenation**: `Tokeniza-` + `tion` → `Tokenization`, but `state-of-` + `the-art` → `state-of-the-art` (a hyphen earlier in the token marks a compound).
- **Sentence splitting**: split after `. ! ?` when followed by an upper-case letter or digit, then re-merge splits that followed an abbreviation (`e.g`, `i.e`, `Dr`, `Fig`, `et al`, …) or a single-letter initial.
- **Phrase matching** treats hyphens as word characters, so the phrase *written* does not match inside *hand-written*.
- A **light stemmer** (suffix stripping: `-ization`, `-ies`, `-ing`, `-ed`, `-s`, …) is used for retrieval and term coverage. It is deliberately simple; it is not the Porter algorithm.

## 3. Topic segmentation

**Structure first.** Let the heading levels present be L₁ < L₂ < …. The split level is the deepest level such that the number of headings at or above it is ≤ 40. Deeper headings are kept as sub-headings inside the topic. Then:
- consecutive sections with the same title after removing `(cont.)`, `(2)`, `– part 2` are merged (common in slide decks);
- sections with < 30 words (e.g. a chapter title followed directly by its first sub-section, or a cover slide) are merged forward into the next section;
- if more than 40 topics remain, the smallest adjacent pair is merged repeatedly.

**TextTiling-style fallback.** Used for heading-less documents over 300 words (≥ 4 paragraphs; segments of ≥ 100 words, about one per 200 words), and for any single headed section over 1 200 words (segments of ≥ 150 words, about one per 450 words).
1. Paragraphs longer than six sentences are split into three-sentence units.
2. Each unit is a TF-IDF vector. For every gap *i*, the cohesion score is the cosine similarity between the mean vectors of the `w = 2` units before and after the gap.
3. The **depth** of gap *i* is `(max score to the left − sᵢ) + (max score to the right − sᵢ)`.
4. Candidate boundaries are gaps with depth > mean − σ/2, taken deepest first, accepted only if every resulting segment keeps the minimum length, up to the target number of segments.
5. Segments without a heading are titled from their top two keyphrases (`"Gradient Descent and Learning Rate"`) and flagged in the UI as *title from keyphrases*.

## 4. Source-aware chunking

Paragraphs within one topic are accumulated into chunks of about 160 words (maximum 230). A chunk never crosses a topic boundary; very long paragraphs are split at sentence boundaries. Each chunk stores its heading and its first and last page/slide. Chunks are the retrieval units.

## 5. Keyphrase extraction

**Candidates** are produced RAKE-style: the token stream is split at stopwords (scikit-learn's English list minus content words it wrongly contains, such as *system* and *computer*, plus ~120 academic filler words), punctuation, digits and ~200 common verbs/adjectives (`removing`, `assigns`, `smaller`, …) that a POS tagger would otherwise exclude. Every 1–3-gram inside a run is a candidate; generic single nouns (`data`, `system`, `result`) are excluded.

**Scoring.** A `TfidfVectorizer` with the candidate extractor as analyzer is fitted with **topics as documents**, so phrases frequent in one topic but rare in others score highly. Multi-word phrases get a ×(1 + 0.35·(n − 1)) bonus but must occur at least twice. Phrases contained in a higher-ranked phrase are removed.

**Re-ranking.** After definitions are found, phrases appearing in the topic heading are boosted ×2, defined terms ×2.5, and defined terms are inserted if missing. Single words ending in *-ing* / *-ed* are dropped unless they appear in a heading or are defined (keeps *stemming*, drops *removing*).

**Strong concepts** — the only phrases used as quiz answers — are: defined terms, phrases appearing in any heading, recurring multi-word phrases and distinctively cased terms (acronyms such as `TF-IDF`, `BLEU`, `Word2Vec`). Original casing is restored from the most frequent surface form.

## 6. Definition extraction

Applied to every sentence (and bullet) in order:

| Strength | Pattern (simplified) | Example |
| --- | --- | --- |
| strong | `X is/are defined as Y` | *Lemmatization is defined as …* |
| strong | `X refers to Y` · `X means Y` · `X denotes Y` | *Noise removal refers to deleting …* |
| strong | `X is a/an/the {process, technique, method, measure, model, metric, task, …} Y` | *Tokenization is the process of splitting …* |
| strong | glossary line `X: Y` or `X – Y` | *Stemming: removing suffixes …* |
| medium | `X is a/an/the Y` — only if X is a known keyphrase, contains an acronym, or is a capitalised multi-word term | *A language model is a model that …* |

Terms must be 1–6 words, must not start with pronouns or generic heads (*this, it, the result, the advantage, one, …*), and definitions must be 4–45 words. Each term is kept once.

## 7. Learning guide construction (extractive)

For the sentences *S* of a topic:

1. **Centrality.** TF-IDF vectors → cosine similarity matrix with zero diagonal → degree centrality `cᵢ = Σⱼ sim(i, j)`, normalised to [0, 1] (a one-iteration TextRank).
2. **Score** `= 0.55·cᵢ + 0.25·min(keyphrase hits, 3)/3 + 0.2·(1 − i/|S|) − penalties`, with penalties for very short/long sentences (0.15), sentences starting with an unresolved pronoun such as *This/It/They* (0.2) and questions (0.5).
3. **Overview** = the two best sentences in reading order (pronoun-initial ones skipped).
4. **Key points** = up to 10 sentences chosen by **maximal marginal relevance** (`λ = 0.7`, candidates with similarity > 0.75 to an already chosen point are skipped), excluding definition sentences. The rank is stored so *concise mode* shows the top five.
5. **Main concepts** = top keyphrases, each with its best supporting sentence.
6. **Relationships** = sentences matching cue phrases (*is a type of, consists of, depends on, unlike, whereas, compared with, leads to, because, therefore, …*) that mention a topic keyphrase.
7. **Examples / applications** = sentences with *for example, for instance, e.g., such as, used in/for, applications include, …*.
8. **Quick revision** = defined terms with shortened definitions plus the three shortest key points.

Every item is a verbatim sentence with its page/slide number; nothing is paraphrased. The UI and exports say so.

## 8. Retrieval and question answering

- **Index.** One `TfidfVectorizer` per document over `heading + chunk text`, using light-stemmed content words plus bigrams and sublinear term frequency. Indexes are cached in an LRU cache (32 documents) keyed by document id and chunk count.
- **Search.** cosine(query, chunks) → top-5 chunks (optionally restricted to one topic).
- **Answer extraction.** The sentences of the retrieved chunks are scored against the query with the same vectoriser (pronoun-initial sentences × 0.85). Up to three sentences with similarity > 0.05 are returned with their locations.
- **Definition shortcut.** "What is X?", "Define X", "Meaning of X" questions return the stored definition of X when one exists.
- **Verdict.** Let *s* be the best sentence similarity and *c* the fraction of the question's content stems that appear in the top sentences:
  - **supported**: s ≥ 0.32 and c ≥ 0.75
  - **partial**: s ≥ 0.12 and c ≥ 0.40
  - **insufficient**: otherwise (no answer sentences are shown, only the closest passages).

These thresholds were chosen by inspecting the demo notes and are heuristics. Lexical overlap does not establish entailment, which the interface states next to every answer.

## 9. Question generation

All generators read sentences from the uploaded document. Options are shuffled with a seed derived from the question stem, so positions are stable but varied.

| Generator | Type / category | Difficulty | Construction |
| --- | --- | --- | --- |
| Term from description | MCQ / definition | easy | Stem quotes the definition (the term masked if it occurs). Options: the term + 3 other defined terms (same topic first) or strong keyphrases. |
| Description from term | MCQ / definition | medium | "Which of the following best describes X?" Options: X's definition + 3 definitions of *unrelated* terms (≤ 32 words each). |
| Define | Short / definition | easy | "Define X." Model answer = the definition. |
| Cloze | MCQ / factual | medium/hard | Among the 24 best-ranked sentences per topic (8–45 words, no unresolved pronoun), blank one strong concept occurring exactly once (an attached acronym such as "(NLP)" is blanked too). Hard if ≥ 2 distractors come from the same topic or the sentence is > 28 words. Up to 6 per topic; skipped if it would duplicate a definition question. |
| Example | MCQ / application | medium | From "*H* such as A, B and C" where *H* is a strong concept: correct = A; distractors = strong concepts never mentioned in any sentence with *H*. |
| Pattern short answers | Short / application, conceptual | medium | "X is used for Y" → *What is X used for?*; "X consists of Y"; "The advantages of X are Y"; "A because B" → *Explain why: A*. |
| Compare and contrast | Long / conceptual | hard | Sentences with *whereas / unlike / in contrast / differs from / compared with* that mention two distinct strong concepts. Model answer = the sentence plus both definitions if available. |
| Explain in detail | Long / conceptual | hard | Topics with ≥ 4 key points: "Explain T in detail. Your answer should cover A, B and C." Model answer = outline of key points with locations. |
| Short notes | Long / revision | medium | "Write short notes on T." |
| Brief explanation | Short / revision | easy | "Briefly explain K as described in your notes on T." for undefined strong concepts. |

**Distractor selection** ranks candidate phrases by: strong concept first → same plurality as the answer → same topic → similar length → deterministic pseudo-random tie-break (so the same few terms are not reused everywhere). A candidate is rejected if it equals, contains or is contained in the answer; appears in the stem or source sentence; shares a content-word stem or a 5-character prefix with the answer (*tokenizer/tokenization*); is defined in terms of the answer or vice versa (*Porter stemmer: a … stemming algorithm* vs *Stemming*); or — for cloze — the three words before the blank followed by the distractor occur in the document (the distractor would also complete a real statement).

## 10. Validation

Every candidate passes `validate()`:

- MCQ: exactly 4 options; none empty; 4 distinct normalised options; `correct_index ∈ [0, 3]` and `options[correct_index] == answer`; stem ≥ 6 words; for factual, application and easy definition questions the answer must occur in the evidence sentence; no wrong option of > 2 words may occur in the evidence; longest option ≤ 2.5 × shortest + 2 words; no short option may appear in the stem.
- Short/long: stem ≥ 2 words, model answer ≥ 3 words.
- Duplicates: identical normalised stems, identical *answer keys* (same generator, sentence and answer) and same-type stems with token Jaccard ≥ 0.85 are dropped (the higher-quality one is kept).

Rejected candidates are counted per reason and returned with the document (`stats.rejected_reasons`), displayed on the processing summary.

## 11. Measured behaviour on the demo notes

The synthetic notes in [`samples/`](../samples/) (9 sections, 913 words) produce identical results from the PDF, DOCX and PPTX versions:

| Metric | Value |
| --- | --- |
| Topics | 9 (headings / slide titles) |
| Chunks | 9 |
| Sentences used | 53 |
| Definitions found | 21 |
| Keyphrase candidates ranked | 107 |
| Validated questions | 106 — 57 MCQ, 33 short answer, 16 long answer |
| Rejected after generation | 3 (near-duplicates) |
| Processing time (pipeline only, laptop CPU, median of 3) | ≈ 175–200 ms per format |

A second, heading-less test document (≈ 410 words of operating-systems prose across three PDF pages) was segmented by the TextTiling fallback into 2 topics and produced 23 validated questions (11 MCQ); 4 candidates were rejected, 3 of them for lack of distinct distractors.

These figures describe pipeline output, not question quality. No human evaluation of question correctness or difficulty has been carried out, so no accuracy is claimed.

## 12. Optional LLM adapter

`llm.py` can call a local Ollama server (`OLLAMA_URL`) to write a free-form explanation from a topic's passages. It is off by default, needs no API key, uses a timeout, returns HTTP 503 with a reason when unavailable, and the UI labels its output as generated by the named model. The deterministic pipeline never depends on it.
