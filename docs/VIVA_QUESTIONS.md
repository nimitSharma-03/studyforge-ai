# Viva Questions and Answers

Prepared answers for project evaluation. Answers describe what the code actually does.

## Project and motivation

**1. What problem does StudyForge AI solve?**
It turns a student's own unstructured lecture material into organised topics, revision guides and practice questions that are traceable to the source page or slide, so exam preparation is grounded in the syllabus actually taught rather than in a chatbot's general knowledge.

**2. Why rule-based NLP instead of a large language model?**
The requirements were CPU-only deployment, no mandatory model download, no paid API and no fabricated content. Rule-based extraction and classical statistics run in under a second per document on a free cloud instance, are deterministic (the same notes always give the same output) and every output sentence can be traced to the input. The trade-off is less fluent, less flexible output. An optional local LLM adapter (Ollama) is provided but never required.

**3. What does "document-grounded" mean here?**
Guides are extractive (verbatim sentences), questions are built from source sentences and answers are retrieved passages. Every item carries a page/section/slide reference, and the QA feature explicitly reports when the notes do not contain enough evidence.

## Extraction and preprocessing

**4. How are headings detected in a PDF that has no structure tags?**
From typography. PyMuPDF returns spans with font size and flags. The most common size (by character count) is the body size; short lines at ≥ 1.15 × body size are headings, with distinct larger sizes mapped to levels 1–3. Short, fully bold blocks without terminal punctuation are level-3 headings.

**5. How do you handle running headers, page numbers and hyphenation?**
Short blocks whose digit-normalised text repeats on at least half the pages are removed, as are bare page numbers. Words split as `Tokeniza-` / `tion` are re-joined, while a hyphen earlier in the token (`state-of-` / `the-art`) marks a compound and is kept.

**6. What happens with scanned PDFs?**
If almost no text is found and pages contain images, extraction fails with a `scanned_pdf` code and a message recommending OCR. The project does not bundle OCR, and the UI says so.

**7. How is sentence segmentation done without spaCy or NLTK?**
A regex splits after `.`, `!` or `?` followed by whitespace and an upper-case letter or digit; splits that follow known abbreviations (`e.g.`, `Dr.`, `Fig.`) or single-letter initials are merged back.

## Segmentation and representation

**8. How are topics identified?**
Primarily from the author's structure: the deepest heading level that yields at most 40 sections. Tiny sections are merged forward and "(cont.)" slides are joined. Without headings, a TextTiling-style method compares TF-IDF vectors of adjacent paragraph windows and cuts at the deepest valleys of cosine similarity.

**9. Explain TF-IDF.**
`tf-idf(t, d) = tf(t, d) × idf(t)`, with `idf(t) = ln((1 + N) / (1 + df(t))) + 1` in scikit-learn's smoothed form. A term scores highly when it is frequent in one document but rare across the collection. We use sublinear tf (`1 + ln tf`) and L2-normalised vectors.

**10. Explain cosine similarity and why it is used.**
`cos(a, b) = (a · b) / (‖a‖ ‖b‖)`, the cosine of the angle between two vectors. With L2-normalised TF-IDF vectors it is a dot product, it ignores document length and it is cheap on sparse vectors, which suits retrieval over hundreds of passages on a CPU.

**11. Why do you chunk by paragraph rather than fixed token windows?**
Fixed windows cut sentences and mix topics, which weakens both retrieval and citations. Paragraph-aware chunks of about 160 words never cross a topic boundary and keep their page range, so every retrieved passage has a correct citation.

**12. How are keyphrases extracted?**
Candidate phrases are runs of content words between stopwords, punctuation and common verbs (similar to RAKE). They are scored with TF-IDF using topics as documents, boosted when they appear in headings or are defined terms, and de-duplicated when one phrase contains another. We also corrected scikit-learn's stopword list, which wrongly contains content words such as *system* and *computer*.

## Learning guides and QA

**13. How does the guide choose "key points"?**
Each sentence gets a score combining TF-IDF degree centrality (the sum of its similarities to other sentences in the topic, as in one iteration of TextRank), keyphrase coverage and position, with penalties for pronoun-initial sentences and questions. Maximal marginal relevance then picks diverse sentences.

**14. What is Maximal Marginal Relevance?**
A greedy selection maximising `λ · relevance(s) − (1 − λ) · max similarity(s, already selected)`, with λ = 0.7. It prevents near-duplicate key points.

**15. How does question answering work, and what are its limits?**
The question is vectorised with the document's TF-IDF model; the top five chunks are retrieved; their sentences are re-scored against the question. The verdict depends on the best sentence similarity and on how many of the question's content words the answer covers. Its limit is that it is lexical: it cannot recognise paraphrases and similarity does not prove the sentence logically answers the question, which the interface states.

## Question generation

**16. Which question types are generated and how?**
Definition MCQs in both directions, cloze (fill-in-the-blank) MCQs on key concepts in central sentences, example MCQs from "such as" lists, pattern-based short answers ("used for", "consists of", "because"), compare-and-contrast long answers from contrast sentences, and outline-based long answers per topic.

**17. How are distractors chosen?**
From other defined terms and strong keyphrases of the same document, preferring the same topic, the same grammatical number and similar length. Candidates are rejected if they overlap the answer, share a word root with it, are defined in terms of it, appear in the source statement, or would also complete a real sentence in the notes.

**18. How do you ensure exactly one defensible answer?**
The correct answer comes from the source sentence itself, and the validator checks four distinct options, correct index mapping, answer presence in the evidence, no option leaked in the stem and balanced option lengths. Distractor filters remove closely related concepts (e.g. *Porter stemmer* is never a distractor for *Stemming*). Candidates that cannot satisfy these rules are discarded and counted, not kept.

**19. How is difficulty assigned?**
Heuristically: definition-recognition questions are easy; description-matching and most cloze items are medium; cloze items with mostly same-topic distractors or long sentences, compare-and-contrast and "explain in detail" questions are hard. These labels have not been validated against student performance.

## Quiz engine and progress

**20. How do you prevent cheating through the API?**
The exam view never includes answer keys or explanations. Scoring is done on the server from stored `correct_index` values; extra fields sent by the client are ignored. Submission flips the status with a conditional `UPDATE … WHERE status='in_progress'`, so only one submission can be scored even under concurrent requests.

**21. How are weak topics determined?**
From submitted answers only. A topic needs at least five attempted questions before it is labelled weak (< 60 %), developing (< 80 %) or strong; below that it is "needs more practice". Overall accuracy is hidden until five questions have been attempted.

**22. What does "mid-semester mode" do?**
It draws questions from the first half of each selected document's topics, prefers easy and medium questions (topping up with hard ones if necessary), and defaults to 15 questions in 30 minutes.

## Engineering

**23. How is user data isolated without accounts?**
Each browser receives a random 256-bit workspace token; only its SHA-256 hash is stored. All queries filter by the workspace resolved from the token, and other workspaces' records return 404. This is anonymous isolation, not full authentication: losing the token means losing access.

**24. Why is processing synchronous?**
For lecture-sized documents the pipeline takes well under a second. A job queue would need an extra worker and broker that the free hosting tier does not provide. A 120-second deadline protects the server.

**25. How is the system tested?**
pytest covers extraction, NLP components, validation rules, API behaviour, access control, scoring, concurrency and exports; Vitest with React Testing Library covers pages and interactions; a Playwright script runs the full workflow in Chromium. CI runs the unit suites on every push.

**26. What are the main limitations?**
Lexical rather than semantic matching, heuristic keyphrases, no OCR, fewer questions from narrative or mathematical material, anonymous workspaces only, in-memory rate limiting, and no human evaluation of question quality yet.

**27. How would you improve it?**
Add sentence-embedding retrieval when resources allow, OCR, spaced repetition from per-question history, optional accounts, teacher review and rating of questions to measure quality, and database migrations.
