# StudyForge AI: An NLP-Based Personalized Learning and Examination Preparation Platform

**Project report — NLP Laboratory**
Author: Nimit Sharma · Version 1.0.0 · October 2026

---

## Abstract

Students preparing for semester examinations must turn large volumes of lecture notes into revision material and practice questions. General-purpose chatbots can help, but they answer from general knowledge rather than the course as taught, and may produce confident but incorrect statements. This project presents **StudyForge AI**, a web platform that processes a student's own PDF, DOCX and PPTX files with a deterministic, CPU-only NLP pipeline. The system extracts text with page and slide metadata, segments it into topics using document structure (with a TextTiling-style fallback), ranks keyphrases with TF-IDF, extracts definitions with lexical patterns, builds extractive learning guides using TF-IDF centrality and maximal marginal relevance, answers questions by TF-IDF retrieval with an explicit evidence verdict, and generates multiple-choice, short-answer and long-answer questions that pass automatic validation rules. A quiz engine with server-side scoring supports mid- and end-semester practice tests, and progress analytics identify weak topics only when enough answers exist. On a synthetic nine-section set of lecture notes the pipeline produced 9 topics and 106 validated questions in about 0.2 s per document, with identical results from the PDF, DOCX and PPTX versions. The application is implemented with FastAPI and React, covered by 80 backend and 16 frontend automated tests plus a browser end-to-end test, and deployed on Render.

## 1. Introduction

Natural language processing offers well-understood tools for organising text: segmentation, keyword extraction, extractive summarisation and information retrieval. Combined carefully, these can transform lecture notes into study aids without relying on generative models. The guiding principle of StudyForge AI is **source grounding**: every guide sentence, question and answer is derived from the uploaded material and cites its location, and the system says so when it cannot support an answer.

## 2. Problem statement

Given a student's course material in common office formats, automatically produce (a) a topic-wise organisation of the content, (b) concise and detailed revision guides, (c) a bank of exam-style questions with correct answers and explanations, and (d) practice tests whose results reveal which topics need revision — while running on modest CPU-only hosting, avoiding paid APIs and large model downloads, protecting each user's data, and never presenting fabricated content as fact.

## 3. Objectives

1. Extract text from PDF, DOCX and PPTX while preserving headings and page/section/slide numbers, and handle invalid, empty and scanned files.
2. Segment documents into topics and source-aware passages.
3. Generate structured, extractive learning guides with citations.
4. Provide retrieval-based question answering that distinguishes supported, partial and insufficient evidence.
5. Generate MCQ, short-answer and long-answer questions and reject low-quality or ambiguous candidates.
6. Provide mid-semester, end-semester, topic and custom practice tests with secure server-side scoring.
7. Track performance by topic and recommend revision based on real results.
8. Deliver a tested, documented, deployable web application.

## 4. Proposed system

The system is a three-tier web application:

- **Frontend** (React, TypeScript, Tailwind CSS): landing page, dashboard, materials management, upload, learning view, question bank, practice tests, results, progress and about pages.
- **Backend** (FastAPI, SQLAlchemy): REST API, NLP pipeline, quiz engine, analytics and exports.
- **Database** (SQLite locally, PostgreSQL in production): documents, topics, passages, questions, quiz attempts and responses.

Users are isolated by anonymous workspaces: the server issues a random 256-bit token per browser and stores only its hash; all data access is filtered by the owning workspace.

## 5. Architecture


Component, data-model and sequence diagrams are in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). In summary, an upload request validates the file, checks for duplicates and quotas, runs the NLP pipeline synchronously with a 120-second deadline, and stores all results in one transaction; the original file is discarded. Quiz creation selects stored questions; submission is claimed atomically and scored from stored answer keys.

## 6. NLP algorithms

A complete description with formulas and parameters is given in [NLP_METHODOLOGY.md](NLP_METHODOLOGY.md). The main algorithms are:

| Task | Method |
| --- | --- |
| Heading detection | Font-size ratio (≥ 1.15 × body size) and bold short lines (PDF); paragraph styles (DOCX); title placeholders (PPTX) |
| Text normalisation | NFKC, de-hyphenation with compound preservation, header/footer removal by cross-page repetition |
| Sentence segmentation | Regex boundaries with abbreviation and initial merging |
| Topic segmentation | Heading-level selection (≤ 40 topics) with merging rules; TextTiling-style depth scores over TF-IDF cosine similarity when headings are absent |
| Keyphrase extraction | Stopword/verb-delimited candidates (RAKE-like) scored by TF-IDF across topics, boosted for headings and defined terms |
| Definition extraction | Lexical patterns (`is defined as`, `refers to`, `is the process of`, glossary `X: Y`, constrained `X is a Y`) |
| Extractive guides | TF-IDF degree centrality + keyphrase coverage + position; maximal marginal relevance (λ = 0.7); cue-phrase detection for relationships and examples |
| Retrieval | TF-IDF with light stemming and bigrams; cosine similarity over paragraph-aware chunks |
| Answer grading | Best-sentence similarity and query-term coverage thresholds → supported / partial / insufficient |
| Question generation | Definition matching, cloze deletion, example lists, pattern transformation, contrast and outline templates |
| Distractor selection | Same-document strong concepts ranked by topic, plurality and length; rejection of overlapping, root-sharing, mutually defined or source-completing candidates |
| Validation | Structural (4 distinct options, index mapping), source (answer in evidence), leakage, length balance and duplicate checks |

## 7. Implementation

**Backend.** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2. The NLP code (`backend/app/nlp`) is pure and independent of the database, which made it straightforward to unit-test. The services layer handles transactions; for example, document deletion removes quiz attempts that used the document so progress statistics never refer to missing questions. Submission uses a conditional update so concurrent requests cannot score a quiz twice. Exports (Markdown, plain text and PDF via PyMuPDF's HTML story renderer) are produced in memory.

**Frontend.** React 18 with TypeScript and Tailwind CSS using a small token-based design system (colour, radius and shadow tokens; reusable buttons, cards, badges, dialogs, tabs, alerts and empty states). Pages are lazy-loaded. Uploads use `XMLHttpRequest` to show real transfer progress, followed by an honest indeterminate "analysing on the server" state. The exam view supports one question at a time, a question navigator, review marks, autosave and an optional timer with automatic submission.

**Security and privacy.** File signature validation, size/page limits, processing deadline, rate limits, per-workspace quotas, CORS restrictions, uniform error responses without internal details, and logs without document content. No document is sent to an external service by default.

**Deployment.** A Render Blueprint defines a PostgreSQL database, the API web service with a health check, and the static site with an SPA rewrite. GitHub Actions runs lint, type checks, tests and the production build.

## 8. Testing

| Suite | Tool | Tests | Result |
| --- | --- | --- | --- |
| Backend unit and API tests | pytest | 80 | 80 passed |
| Backend lint/format | Ruff | — | clean |
| Frontend component/integration tests | Vitest + React Testing Library | 16 | 16 passed |
| Frontend lint and types | ESLint, `tsc --noEmit` | — | clean |
| Production build | Vite | — | succeeded |
| End-to-end workflow | Playwright (Chromium) | 9 steps | passed locally (production build) and against the live Render deployment |

Backend tests cover all three extractors, invalid and corrupted files, empty and scanned PDFs, header removal, normalisation, both segmentation strategies, chunk boundaries, keyphrases, definitions, guide citations, MCQ structure, every validator rule, retrieval ranking and QA verdicts, upload limits, quotas, rate limiting, duplicate detection, cross-workspace isolation, cascade deletion, question bank filters, exports, answer hiding in exam mode, scoring with correct/incorrect/unanswered items, ignored client score fields, duplicate and concurrent submissions, autosave, mode-specific question selection, retries, progress thresholds and resolution of corrected mistakes.

Frontend tests cover the landing page, navigation, dashboard empty and populated states, backend-unavailable handling, materials listing and deletion confirmation, client- and server-side upload errors, topic switching in the learning view, quiz interaction and the exact submission payload, absence of a late autosave after submission (a race first observed in the live end-to-end run), result display and the API client's token and error handling.

## 9. Results

Measured on the bundled synthetic notes (nine sections, 913 words), using a laptop CPU:

| Metric | PDF | DOCX | PPTX |
| --- | --- | --- | --- |
| Units | 3 pages | 10 sections | 10 slides |
| Topics | 9 | 9 | 9 |
| Definitions found | 21 | 21 | 21 |
| Validated questions (MCQ / short / long) | 106 (57 / 33 / 16) | 106 (57 / 33 / 16) | 106 (57 / 33 / 16) |
| Candidates rejected after generation | 3 | 3 | 3 |
| Pipeline time, laptop CPU (median of 3) | ≈ 175 ms | ≈ 200 ms | ≈ 183 ms |
| Full upload request on the free Render instance (single run) | — | 2.5 s | 2.1 s |

A heading-less operating-systems text (≈ 410 words over three pages) was split by the fallback segmenter into two topics and yielded 23 validated questions.

Qualitative observations from manual inspection of the demo output: definition questions and cloze questions on defined terms were consistently well-formed; distractor filtering removed several initially ambiguous items (for example, *Porter stemmer* offered as a wrong answer to a question about stemming); keyphrase quality depends on the absence of a part-of-speech tagger and occasionally includes generic words.

**No evaluation with human raters or student performance data has been carried out.** The figures above describe system behaviour, not question correctness rates or learning outcomes, and no accuracy or effectiveness claims are made.

## 10. Limitations

- Rule-based generation favours definitional and well-structured material; narrative, mathematical or diagram-heavy notes produce fewer questions.
- Without a POS tagger, keyphrases are approximate.
- Retrieval is lexical and misses paraphrases.
- No OCR; images and equations are ignored.
- Anonymous workspaces only; no cross-device access.
- In-memory rate limiting and caching assume a single instance.
- On the free hosting tier the API sleeps when idle, and the free database is time-limited.
- Difficulty labels are heuristic and unvalidated.

## 11. Future improvements

Semantic retrieval with sentence embeddings, OCR for scanned notes, spaced repetition scheduling, optional authenticated accounts, instructor review and rating of generated questions to measure quality, multilingual support and schema migrations.

## 12. Conclusion

StudyForge AI shows that a carefully engineered classical NLP pipeline can deliver a useful, transparent exam-preparation tool: it organises lecture notes into topics, produces cited revision guides, generates validated questions and runs secure practice tests, all on CPU-only infrastructure without generative models. Its explicit handling of uncertainty — evidence verdicts, rejection statistics and minimum-data thresholds for analytics — keeps the system honest about what it knows. The modular design leaves room for semantic models and human evaluation in future work.

## References

1. Salton, G., & Buckley, C. (1988). Term-weighting approaches in automatic text retrieval. *Information Processing & Management*, 24(5).
2. Hearst, M. A. (1997). TextTiling: Segmenting text into multi-paragraph subtopic passages. *Computational Linguistics*, 23(1).
3. Mihalcea, R., & Tarau, P. (2004). TextRank: Bringing order into texts. *EMNLP*.
4. Carbonell, J., & Goldstein, J. (1998). The use of MMR, diversity-based reranking for reordering documents and producing summaries. *SIGIR*.
5. Rose, S., Engel, D., Cramer, N., & Cowley, W. (2010). Automatic keyword extraction from individual documents (RAKE). In *Text Mining: Applications and Theory*.
6. Mitkov, R., & Ha, L. A. (2003). Computer-aided generation of multiple-choice tests. *HLT-NAACL Workshop on Building Educational Applications Using NLP*.
7. Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. *JMLR*, 12.
