# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-24

### Added
- PDF, DOCX and PPTX ingestion with page/section/slide metadata, heading detection, table and speaker-notes extraction, header/footer removal, scanned-PDF detection and duplicate-upload recognition.
- Topic segmentation from headings and slide titles with a TextTiling-style fallback; source-aware chunking.
- Keyphrase and definition extraction; extractive learning guides with concise and detailed modes.
- TF-IDF retrieval and evidence-graded question answering (supported / partial / insufficient).
- Rule-based question generation (MCQ, short and long answer across five categories) with validation and rejection statistics.
- Question bank with filters, search, random question sets and downloads.
- Practice tests: mid-semester, end-semester, topic and custom modes; timer with auto-submit; autosave; review marks; atomic server-side scoring; retry of missed questions.
- Progress analytics: history, score trend, topic accuracy with minimum-evidence thresholds, weak topics, incorrect-question review and recommendations.
- Markdown, TXT and PDF exports for revision notes, question banks and quiz results.
- Anonymous workspace isolation, rate limiting, upload quotas, "delete all my data".
- Optional Ollama adapter (disabled by default).
- React frontend with landing page, dashboard, materials, upload, learn, question bank, practice, results, progress and about pages.
- Synthetic demo notes in three formats; pytest, Vitest and Playwright tests; GitHub Actions CI; Render Blueprint; project documentation.
