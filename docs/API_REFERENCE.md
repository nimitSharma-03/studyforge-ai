# API Reference

Base path: `/api`. Interactive documentation: `/docs` (Swagger UI), `/redoc`, schema at `/openapi.json`.

## Conventions

- **Authentication:** send `X-Workspace-Token: <token>` on every request except `GET /health` and `POST /workspaces`.
- **Errors:** `{"detail": "Human readable message", "code": "machine_code"}`. Validation errors (422) add `errors: [{field, message}]`. Unexpected errors (500) add `ref`.
- **Ownership:** resources belonging to another workspace return `404`.

| Status | Typical codes |
| --- | --- |
| 400 | `empty_file` |
| 401 | `workspace_required`, `workspace_invalid` |
| 404 | `document_not_found`, `topic_not_found`, `quiz_not_found`, `not_found` |
| 409 | `document_not_ready`, `already_submitted`, `quiz_not_submitted`, `quota_exceeded` |
| 413 | `file_too_large` |
| 415 | `unsupported_type` |
| 422 | `validation_error`, `corrupted`, `no_questions`, `topics_required`, `nothing_to_retry`, `unknown_question` |
| 429 | `rate_limited` |
| 503 | `database_unavailable`, `llm_unavailable` |

---

## System

### `GET /health`
`200 {"status":"ok","version":"1.0.0","environment":"production","database":"ok","database_backend":"postgresql","llm_enabled":false,"max_upload_mb":25}` — returns `503` with `"database":"error"` when the database is unreachable.

### `POST /workspaces`
Creates an anonymous workspace. `201 {"token":"sfw_…","workspace_id":"…","created_at":"…"}`. The token is shown only once. Rate-limited per client IP.

### `GET /workspaces/me` · `DELETE /workspaces/me`
Workspace info and limits · permanently deletes the workspace and all its data (`204`).

## Documents

### `POST /documents`
`multipart/form-data` with field `file` (`.pdf`, `.docx`, `.pptx`, ≤ `MAX_UPLOAD_MB`). Processes synchronously and returns `201` with a **DocumentDetail**:

```json
{
  "id": "4f0c…", "name": "Lecture 3", "original_filename": "Lecture 3.pdf", "file_type": "pdf",
  "size_bytes": 182311, "status": "ready", "error_code": null, "error_message": null, "is_sample": false,
  "unit_label": "page", "unit_count": 12, "word_count": 4210, "chunk_count": 31, "topic_count": 9,
  "question_count": 84, "warnings": [], "segmentation_method": "headings", "heading_count": 14,
  "rejected_question_count": 6, "processing_ms": 640,
  "stats": {"definitions": 18, "sentences": 240, "keyphrases": 160,
            "questions_by_type": {"mcq": 41, "short_answer": 28, "long_answer": 15},
            "rejected_total": 6, "rejected_reasons": {"insufficient_distractors": 4, "near_duplicate": 2}},
  "topics": [{"id": 1, "position": 0, "title": "Introduction", "keywords": ["…"], "location_type": "page",
              "location_start": 1, "location_end": 2, "word_count": 410, "question_count": 9, "title_source": "heading"}],
  "preview": [{"id": 1, "text": "…", "location_type": "page", "location_start": 1, "location_end": 1, "heading": "Introduction"}],
  "duplicate": false
}
```

If extraction fails (scanned PDF, damaged file, too little text, timeout) the response is still `201` with `"status":"failed"`, an `error_code` and a readable `error_message`; the record appears in the materials list. Uploading identical bytes again returns the existing document with `"duplicate": true`.

### `POST /documents/sample`
Adds the bundled synthetic demo notes (same response as upload).

### `GET /documents`
List of **DocumentSummary** (newest first).

### `GET /documents/{id}` · `PATCH /documents/{id}` · `DELETE /documents/{id}`
Details · rename with `{"name": "New name"}` · delete the document, its topics, chunks, questions and the quiz attempts that used it (`204`).

### `GET /documents/{id}/delete-impact`
`{"document_id":"…","topics":9,"questions":84,"quiz_attempts":2}`

### `GET /documents/{id}/content?offset=0&limit=20&topic_id=`
Paginated extracted passages: `{"items":[Chunk], "total": 31, "offset": 0, "limit": 20}`.

### `GET /documents/{id}/topics`
Topics with question counts (`409` if the document is not ready).

### `GET /topics/{id}`
Topic with `guide`, `chunks`, `document_name`, `unit_label`, `prev_topic_id`, `next_topic_id`. Guide fields: `overview`, `definitions[{term, definition, text, location}]`, `key_points[{text, location, rank}]`, `concepts[{term, sentence}]`, `relationships[{text, location, cue}]`, `examples`, `revision[str]`, `method: "extractive-rule-based"`.

### `POST /documents/{id}/ask`
Body `{"question": "Why can accuracy be misleading?", "topic_id": null}` (3–500 characters).

```json
{
  "question": "Why can accuracy be misleading?",
  "verdict": "supported",
  "message": "These sentences from your material closely match the question.",
  "answer": [{"text": "Accuracy can be misleading on imbalanced datasets because …", "location_type": "page", "location": 3, "topic_id": 9, "score": 0.63}],
  "passages": [{"chunk_id": 9, "text": "…", "heading": "Evaluation of NLP Systems", "topic_id": 9, "location_type": "page", "location_start": 3, "location_end": 3, "score": 0.41}],
  "coverage": 1.0, "top_score": 0.63, "method": "tfidf-extractive"
}
```

`verdict` ∈ `supported | partial | insufficient`; for `insufficient`, `answer` is empty.

### `POST /topics/{id}/llm-explanation`
Optional. `200 {"topic_id", "model", "text", "passages_used"}` when `OLLAMA_URL` is configured; otherwise `503 llm_unavailable`.

## Questions

### `GET /questions`
Query: `document_id` (required), repeatable `topic_id`, `difficulty`, `question_type`, `category`, plus `search`, `offset`, `limit` (≤ 200). Returns `{"items":[Question], "total", "offset", "limit", "counts": {"question_type": {...}, "difficulty": {...}, "category": {...}}}`. Study mode: items include answers.

**Question:** `id, document_id, topic_id, topic_title, question_type (mcq|short_answer|long_answer), category (definition|factual|conceptual|application|revision), difficulty (easy|medium|hard), stem, options[4]|null, correct_index|null, option_notes, answer_text, explanation, evidence, location_type, location_start, location_end`.

### `POST /questions/generate`
Body `{"document_id", "topic_ids":[], "difficulties":[], "question_types":[], "categories":[], "count":10, "seed":null}`. Returns a random selection of validated questions: `{"questions", "requested", "available", "message"}`. Never pads with unvalidated questions.

## Quizzes

### `POST /quizzes`
```json
{"mode": "mid_sem", "document_ids": ["…"], "topic_ids": [], "difficulties": [], "count": 15, "time_limit_minutes": 30}
```
| Mode | Topics | Default count / timer | Difficulty |
| --- | --- | --- | --- |
| `mid_sem` | first ⌈n/2⌉ topics of each document | 15 / 30 min | prefers easy + medium, tops up if short |
| `end_sem` | all | 30 / 60 min | all |
| `topic` | `topic_ids` required | 10 / none | all |
| `custom` | optional `topic_ids` | 10 / none | optional hard filter |
| `retry` | `source_attempt_id` required | incorrect + unanswered | — |

Returns `201` **Quiz** (exam view): `id, title, mode, status, time_limit_minutes, created_at, total, document_ids, questions[{question_id, position, stem, options, topic_id, topic_title, difficulty, category, selected_index, marked_for_review}]` — no answer keys.

### `GET /quizzes`
History (newest first), including `score_percent` for submitted attempts.

### `GET /quizzes/{id}`
Exam view of a quiz with saved selections.

### `PUT /quizzes/{id}/responses`
Body `{"responses":[{"question_id","selected_index":0..3|null,"marked_for_review":false}]}`. Autosave; `409` once submitted.

### `POST /quizzes/{id}/submit`
Body `{"responses":[…], "duration_seconds": 512}`. Returns **QuizResult**: `total, correct_count, incorrect_count, unanswered_count, answered_count, score_percent, duration_seconds, items[{question_id, stem, options, selected_index, correct_index, status (correct|incorrect|unanswered), explanation, option_notes, evidence, location…, topic_title, marked_for_review}], topic_breakdown[{topic_id, topic_title, correct, total}]`. A second submission returns `409 already_submitted`.

### `GET /quizzes/{id}/result` · `POST /quizzes/{id}/retry` · `DELETE /quizzes/{id}`
Result of a submitted quiz (`409` before submission) · new quiz from incorrect/unanswered questions · delete an attempt.

## Progress

### `GET /progress/summary`
`documents_ready, documents_total, attempts_submitted, attempts_in_progress, questions_answered, questions_correct, average_accuracy|null, min_answers_for_accuracy (5), min_answers_per_topic (5), topics[TopicProgress], weak_topics, insufficient_topics, recommendations[{kind, title, detail, topic_id, document_id, attempt_id}], recent_activity, accuracy_trend`.

TopicProgress `status` ∈ `not_started | insufficient | weak | developing | strong`.

### `GET /progress/incorrect?limit=50`
Questions whose latest answer was wrong or blank, with the selected and correct options, explanation, source and `times_missed`.

## Exports

| Endpoint | Query | Content |
| --- | --- | --- |
| `GET /exports/documents/{id}/notes` | `format=md\|txt\|pdf`, `mode=concise\|detailed`, `topic_id` | Revision notes with source references |
| `GET /exports/documents/{id}/questions` | `format`, `answers=true\|false`, filters as `/questions` | Question bank with optional answer key |
| `GET /exports/quizzes/{id}` | `format` | Quiz result report |

Responses use `Content-Disposition: attachment; filename="…"` and `Cache-Control: no-store`.
