from datetime import datetime, timedelta, timezone

import pytest

import db

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(str(tmp_path / "test.db"))
    yield connection
    connection.close()


def test_next_review_steps_up_on_correct():
    assert db.next_review(0, True, NOW) == (1, NOW + timedelta(days=1))
    assert db.next_review(2, True, NOW) == (3, NOW + timedelta(days=7))


def test_next_review_caps_at_max_box():
    assert db.next_review(db.MAX_BOX, True, NOW) == (db.MAX_BOX, NOW + timedelta(days=30))


def test_next_review_resets_on_wrong():
    assert db.next_review(4, False, NOW) == (1, NOW + timedelta(days=1))


def test_create_course_makes_one_lesson_per_document_in_order(conn):
    course_id = db.create_course(conn, "Bio", {"length": 5}, [("a.pdf", "/x/a"), ("b.pdf", "/x/b")])

    course = db.get_course(conn, course_id, NOW)

    assert [d["filename"] for d in course["documents"]] == ["a.pdf", "b.pdf"]
    assert [(e["kind"], e["position"]) for e in course["episodes"]] == [("lesson", 1), ("lesson", 2)]
    assert course["options"] == {"length": 5}
    assert db.document_paths(conn, course_id) == ["/x/a", "/x/b"]


def test_get_course_unknown_returns_none(conn):
    assert db.get_course(conn, 999, NOW) is None


def test_list_courses_newest_first(conn):
    first = db.create_course(conn, "First", {}, [("a.pdf", "/a")])
    second = db.create_course(conn, "Second", {}, [("b.pdf", "/b")])

    assert [c["id"] for c in db.list_courses(conn, NOW)] == [second, first]


LESSON = {
    "title": "Cells 101",
    "chapters": [{"title": "Intro", "lines": [{"speaker": "Host A", "text": "Hi"}]}],
    "concepts": [{"name": "Mitosis", "summary": "Cell division"}, {"name": "ATP", "summary": "Energy"}],
    "quiz": [
        {"concept": "Mitosis", "question": "Q1?", "choices": ["a", "b"], "answer_index": 0, "explanation": "e1"},
        {"concept": "ATP", "question": "Q2?", "choices": ["c", "d"], "answer_index": 1, "explanation": "e2"},
    ],
}


@pytest.fixture
def lesson(conn):
    course_id = db.create_course(conn, "Bio", {}, [("a.pdf", "/a"), ("b.pdf", "/b")])
    episode_id = db.get_course(conn, course_id, NOW)["episodes"][0]["id"]
    db.save_lesson(conn, episode_id, LESSON)
    return {"course_id": course_id, "episode": db.get_episode(conn, episode_id)}


def test_save_lesson_stores_script_and_tagged_questions(lesson):
    episode = lesson["episode"]

    assert episode["title"] == "Cells 101"
    assert episode["script"]["chapters"][0]["title"] == "Intro"
    assert [(q["concept"], q["choices"]) for q in episode["questions"]] == [
        ("Mitosis", ["a", "b"]), ("ATP", ["c", "d"])
    ]


def test_prior_concepts_only_from_earlier_episodes(conn, lesson):
    assert db.prior_concepts(conn, lesson["course_id"], 1) == []
    assert [c["name"] for c in db.prior_concepts(conn, lesson["course_id"], 2)] == ["Mitosis", "ATP"]


def test_wrong_answer_makes_concept_due_for_review(conn, lesson):
    mitosis, atp = lesson["episode"]["questions"]

    db.record_attempt(conn, mitosis["id"], False, NOW)
    db.record_attempt(conn, atp["id"], True, NOW)

    assert [c["name"] for c in db.review_concepts(conn, lesson["course_id"], NOW)] == ["Mitosis"]
    later = NOW + timedelta(days=2)
    assert [c["name"] for c in db.review_concepts(conn, lesson["course_id"], later)] == ["Mitosis", "ATP"]
    assert db.get_course(conn, lesson["course_id"], later)["due_count"] == 2


def test_nothing_to_review_before_any_attempt(conn, lesson):
    assert db.review_concepts(conn, lesson["course_id"], NOW) == []


def test_review_episode_goes_after_lessons(conn, lesson):
    episode_id = db.create_review_episode(conn, lesson["course_id"])

    episode = db.get_episode(conn, episode_id)

    assert (episode["kind"], episode["position"]) == ("review", 3)
