from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.models import Question, Topic


def _answer_key(question_ids: list[str]) -> dict[str, int]:
    with SessionLocal() as db:
        return {q.id: q.correct_index for q in db.query(Question).filter(Question.id.in_(question_ids))}


def _create(client, headers, **body) -> dict:
    r = client.post("/api/quizzes", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_exam_view_hides_answers(client, headers, ready_doc):
    quiz = _create(client, headers, mode="end_sem", document_ids=[ready_doc["id"]])
    assert quiz["status"] == "in_progress"
    assert quiz["time_limit_minutes"] == 60
    raw = json.dumps(quiz)
    for leaked in ("correct_index", "explanation", "answer_text", "evidence", "option_notes"):
        assert leaked not in raw
    again = client.get(f"/api/quizzes/{quiz['id']}", headers=headers).text
    assert "correct_index" not in again
    assert client.get(f"/api/quizzes/{quiz['id']}/result", headers=headers).status_code == 409


def test_scoring_uses_stored_answer_key(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=8)
    ids = [q["question_id"] for q in quiz["questions"]]
    key = _answer_key(ids)
    responses = []
    for n, qid in enumerate(ids):
        if n < 3:
            responses.append({"question_id": qid, "selected_index": key[qid]})  # correct
        elif n < 6:
            responses.append({"question_id": qid, "selected_index": (key[qid] + 1) % 4})  # wrong
        # last two unanswered
    r = client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": responses})
    assert r.status_code == 200
    result = r.json()
    assert (result["correct_count"], result["incorrect_count"], result["unanswered_count"]) == (3, 3, 2)
    assert result["answered_count"] == 6
    assert result["score_percent"] == 37.5
    statuses = [i["status"] for i in sorted(result["items"], key=lambda i: i["position"])]
    assert statuses == ["correct"] * 3 + ["incorrect"] * 3 + ["unanswered"] * 2
    for item in result["items"]:
        assert item["correct_index"] == key[item["question_id"]]
        assert item["explanation"] and item["evidence"]
    assert sum(t["total"] for t in result["topic_breakdown"]) == 8


def test_client_cannot_inject_score(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=3)
    payload = {
        "responses": [
            {"question_id": q["question_id"], "selected_index": None, "is_correct": True} for q in quiz["questions"]
        ],
        "score": 100,
        "correct_count": 3,
    }
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json=payload).json()
    assert result["correct_count"] == 0
    assert result["unanswered_count"] == 3


def test_duplicate_submission_is_rejected(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=4)
    first = client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": []})
    second = client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": []})
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "already_submitted"
    assert (
        client.put(f"/api/quizzes/{quiz['id']}/responses", headers=headers, json={"responses": []}).status_code == 409
    )


def test_concurrent_submissions_score_once(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=4)

    def submit(_):
        return client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": []}).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = sorted(pool.map(submit, range(4)))
    assert codes.count(200) == 1
    assert codes.count(409) == 3


def test_autosave_responses(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=3)
    qid = quiz["questions"][0]["question_id"]
    r = client.put(
        f"/api/quizzes/{quiz['id']}/responses",
        headers=headers,
        json={"responses": [{"question_id": qid, "selected_index": 2, "marked_for_review": True}]},
    )
    saved = next(q for q in r.json()["questions"] if q["question_id"] == qid)
    assert saved["selected_index"] == 2 and saved["marked_for_review"] is True
    bad = client.put(
        f"/api/quizzes/{quiz['id']}/responses",
        headers=headers,
        json={"responses": [{"question_id": "not-in-quiz", "selected_index": 1}]},
    )
    assert bad.status_code == 422
    out_of_range = client.put(
        f"/api/quizzes/{quiz['id']}/responses",
        headers=headers,
        json={"responses": [{"question_id": qid, "selected_index": 4}]},
    )
    assert out_of_range.status_code == 422


def test_mid_sem_covers_first_half_of_topics(client, headers, ready_doc):
    quiz = _create(client, headers, mode="mid_sem", document_ids=[ready_doc["id"]])
    first_half = {t["id"] for t in ready_doc["topics"][:5]}  # ceil(9 / 2) = 5
    assert {q["topic_id"] for q in quiz["questions"]} <= first_half
    assert quiz["time_limit_minutes"] == 30
    assert quiz["total"] == 15


def test_topic_mode(client, headers, ready_doc):
    assert (
        client.post(
            "/api/quizzes", headers=headers, json={"mode": "topic", "document_ids": [ready_doc["id"]]}
        ).status_code
        == 422
    )
    topic = ready_doc["topics"][5]
    quiz = _create(client, headers, mode="topic", document_ids=[ready_doc["id"]], topic_ids=[topic["id"]])
    assert quiz["title"] == f"Topic practice: {topic['title']}"
    assert {q["topic_id"] for q in quiz["questions"]} == {topic["id"]}


def test_explicit_difficulty_is_a_hard_filter(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], difficulties=["hard"], count=50)
    assert quiz["total"] > 0
    assert {q["difficulty"] for q in quiz["questions"]} == {"hard"}


def test_retry_incorrect(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=5)
    ids = [q["question_id"] for q in quiz["questions"]]
    key = _answer_key(ids)
    responses = [
        {"question_id": ids[0], "selected_index": key[ids[0]]},
        {"question_id": ids[1], "selected_index": (key[ids[1]] + 1) % 4},
    ]
    client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": responses})
    retry = client.post(f"/api/quizzes/{quiz['id']}/retry", headers=headers)
    assert retry.status_code == 201
    retry_ids = {q["question_id"] for q in retry.json()["questions"]}
    assert retry_ids == set(ids[1:])  # wrong + unanswered
    assert retry.json()["mode"] == "retry"


def test_retry_requires_submission_and_mistakes(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=2)
    assert client.post(f"/api/quizzes/{quiz['id']}/retry", headers=headers).status_code == 409
    key = _answer_key([q["question_id"] for q in quiz["questions"]])
    responses = [{"question_id": qid, "selected_index": idx} for qid, idx in key.items()]
    client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": responses})
    r = client.post(f"/api/quizzes/{quiz['id']}/retry", headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "nothing_to_retry"


def test_history_and_delete(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=2)
    history = client.get("/api/quizzes", headers=headers).json()
    assert history[0]["id"] == quiz["id"] and history[0]["score_percent"] is None
    assert client.delete(f"/api/quizzes/{quiz['id']}", headers=headers).status_code == 204
    assert client.get("/api/quizzes", headers=headers).json() == []


def test_quiz_export(client, headers, ready_doc):
    quiz = _create(client, headers, mode="custom", document_ids=[ready_doc["id"]], count=3)
    assert client.get(f"/api/exports/quizzes/{quiz['id']}", headers=headers).status_code == 409
    client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": []})
    r = client.get(f"/api/exports/quizzes/{quiz['id']}?format=txt", headers=headers)
    assert r.status_code == 200 and "Score 0/3" in r.text and "correct answer" in r.text


# ------------------------------------------------------------------ progress


def test_progress_requires_enough_data(client, headers, ready_doc):
    summary = client.get("/api/progress/summary", headers=headers).json()
    assert summary["average_accuracy"] is None
    assert summary["attempts_submitted"] == 0
    assert all(t["status"] == "not_started" for t in summary["topics"])
    assert summary["recommendations"][0]["kind"] == "start"


def test_progress_identifies_weak_topics_and_resolves_mistakes(client, headers, ready_doc):
    topic = ready_doc["topics"][5]
    quiz = _create(client, headers, mode="topic", document_ids=[ready_doc["id"]], topic_ids=[topic["id"]], count=6)
    ids = [q["question_id"] for q in quiz["questions"]]
    assert len(ids) >= 5
    key = _answer_key(ids)
    wrong = [{"question_id": qid, "selected_index": (key[qid] + 1) % 4} for qid in ids]
    client.post(f"/api/quizzes/{quiz['id']}/submit", headers=headers, json={"responses": wrong})

    summary = client.get("/api/progress/summary", headers=headers).json()
    assert summary["average_accuracy"] == 0.0
    tp = next(t for t in summary["topics"] if t["topic_id"] == topic["id"])
    assert tp["status"] == "weak" and tp["attempted"] == len(ids) and tp["correct"] == 0
    assert summary["weak_topics"][0]["topic_id"] == topic["id"]
    kinds = [r["kind"] for r in summary["recommendations"]]
    assert "revise" in kinds and "retry" in kinds

    incorrect = client.get("/api/progress/incorrect", headers=headers).json()
    assert {i["question_id"] for i in incorrect} == set(ids)

    # Answering one of them correctly later removes it from the review list.
    retry = client.post(f"/api/quizzes/{quiz['id']}/retry", headers=headers).json()
    first = retry["questions"][0]["question_id"]
    client.post(
        f"/api/quizzes/{retry['id']}/submit",
        headers=headers,
        json={"responses": [{"question_id": first, "selected_index": key[first]}]},
    )
    incorrect = client.get("/api/progress/incorrect", headers=headers).json()
    assert first not in {i["question_id"] for i in incorrect}
    assert len(incorrect) == len(ids) - 1


def test_topic_status_thresholds(client, headers, ready_doc):
    topic_id = ready_doc["topics"][8]["id"]
    with SessionLocal() as db:
        assert db.get(Topic, topic_id) is not None
    quiz = _create(client, headers, mode="topic", document_ids=[ready_doc["id"]], topic_ids=[topic_id], count=2)
    key = _answer_key([q["question_id"] for q in quiz["questions"]])
    client.post(
        f"/api/quizzes/{quiz['id']}/submit",
        headers=headers,
        json={"responses": [{"question_id": k, "selected_index": v} for k, v in key.items()]},
    )
    summary = client.get("/api/progress/summary", headers=headers).json()
    tp = next(t for t in summary["topics"] if t["topic_id"] == topic_id)
    assert tp["status"] == "insufficient"  # 2 correct answers are not enough evidence to call it strong
    assert summary["average_accuracy"] is None  # fewer than 5 questions answered overall
