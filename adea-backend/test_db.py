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
