import io
import wave
from datetime import timedelta

import pytest

import app as app_module
import db
import gemini

LESSON = {
    "title": "Cells 101",
    "chapters": [{"title": "Intro", "lines": [{"speaker": "Alex", "text": "Hi"}]}],
    "concepts": [{"name": "Mitosis", "summary": "Cell division"}],
    "quiz": [{"concept": "Mitosis", "question": "Q?", "choices": ["a", "b", "c"], "answer_index": 1,
              "explanation": "Because"}],
}


def _wav() -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 100)
    return out.getvalue()


@pytest.fixture
def calls(monkeypatch):
    """Replace every Gemini call with a fake and record what it was given."""
    log = {"lesson": [], "review": [], "answer": [], "synthesize": []}
    monkeypatch.setattr(gemini, "write_lesson", lambda pdf, prior, opts: log["lesson"].append(prior) or LESSON)
    monkeypatch.setattr(gemini, "write_review",
                        lambda pdfs, concepts, opts: log["review"].append(concepts) or {**LESSON, "title": "Review"})
    monkeypatch.setattr(gemini, "answer", lambda pdfs, history, q: log["answer"].append((len(pdfs), q)) or "42")
    monkeypatch.setattr(gemini, "synthesize", lambda script, voices: log["synthesize"].append(voices) or _wav())
    return log


@pytest.fixture
def client(tmp_path, calls):
    flask_app = app_module.create_app(str(tmp_path), require_key=False)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def pdf(name: str = "notes.pdf"):
    return (io.BytesIO(b"%PDF-1.4 fake"), name)


def make_course(client, files=None, **options):
    data = {"files": files or [pdf("a.pdf"), pdf("b.pdf")], **options}
    return client.post("/api/courses", data=data, content_type="multipart/form-data")


@pytest.fixture
def lesson(client):
    course_id = make_course(client).get_json()["id"]
    episode = client.post("/api/episodes/1/script").get_json()
    return {"course_id": course_id, "episode": episode, "question_id": episode["questions"][0]["id"]}


# --- course creation -----------------------------------------------------------

def test_create_course_makes_lessons_in_upload_order(client):
    res = make_course(client, length="5", depth="exam", voice_a="Charon", voice_b="Leda")

    course = client.get(f"/api/courses/{res.get_json()['id']}").get_json()
    assert res.status_code == 201
    assert course["title"] == "a"
    assert [d["filename"] for d in course["documents"]] == ["a.pdf", "b.pdf"]
    assert course["options"] == {"length": 5, "depth": "exam", "voice_a": "Charon", "voice_b": "Leda"}


def test_rejects_non_pdf_even_with_pdf_extension(client):
    res = make_course(client, files=[(io.BytesIO(b"just text"), "sneaky.pdf")])

    assert res.status_code == 400
    assert "not a PDF" in res.get_json()["error"]


@pytest.mark.parametrize("options", [
    {"length": "7"}, {"length": "ten"}, {"depth": "phd"}, {"voice_a": "Nobody"}, {"voice_a": "Puck", "voice_b": "Puck"},
])
def test_rejects_bad_options(client, options):
    assert make_course(client, **options).status_code == 400


def test_rejects_too_many_files(client):
    files = [pdf(f"{i}.pdf") for i in range(app_module.MAX_FILES + 1)]

    assert make_course(client, files=files).status_code == 400


def test_unknown_ids_return_404(client):
    assert client.get("/api/courses/99").status_code == 404
    assert client.get("/api/episodes/99").status_code == 404
    assert client.post("/api/questions/99/attempt", json={"choice": 0}).status_code == 404


# --- lessons + audio -------------------------------------------------------------

def test_script_hides_answers_and_is_generated_once(client, calls, lesson):
    client.post("/api/episodes/1/script")

    question = lesson["episode"]["questions"][0]
    assert set(question) == {"id", "concept", "question", "choices"}
    assert len(calls["lesson"]) == 1


def test_second_lesson_gets_first_lessons_concepts(client, calls, lesson):
    client.post("/api/episodes/2/script")

    assert calls["lesson"] == [[], [{"name": "Mitosis", "summary": "Cell division"}]]


def test_audio_needs_script_then_streams(client, calls):
    make_course(client, voice_a="Charon", voice_b="Leda")

    assert client.post("/api/episodes/1/audio").status_code == 409
    client.post("/api/episodes/1/script")
    assert client.post("/api/episodes/1/audio").status_code == 200
    res = client.get("/api/episodes/1/audio")

    assert res.mimetype == "audio/wav"
    assert calls["synthesize"] == [("Charon", "Leda")]
    res.close()


def test_gemini_failure_returns_json_502(client, monkeypatch):
    make_course(client)
    monkeypatch.setattr(gemini, "write_lesson", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))

    res = client.post("/api/episodes/1/script")

    assert res.status_code == 502
    assert "boom" not in res.get_json()["error"]


# --- quiz + reviews ----------------------------------------------------------------

def test_attempt_reveals_answer(client, lesson):
    res = client.post(f"/api/questions/{lesson['question_id']}/attempt", json={"choice": 0})

    assert res.get_json() == {"correct": False, "answer_index": 1, "explanation": "Because"}


@pytest.mark.parametrize("body", [{}, {"choice": 3}, {"choice": "1"}, {"choice": True}])
def test_attempt_rejects_bad_choice(client, lesson, body):
    assert client.post(f"/api/questions/{lesson['question_id']}/attempt", json=body).status_code == 400


def test_nothing_due_returns_409(client, lesson):
    assert client.post(f"/api/courses/{lesson['course_id']}/reviews").status_code == 409


def test_wrong_answer_leads_to_review_episode_on_that_concept(client, calls, lesson):
    client.post(f"/api/questions/{lesson['question_id']}/attempt", json={"choice": 0})

    res = client.post(f"/api/courses/{lesson['course_id']}/reviews")

    assert res.status_code == 201
    assert [c["name"] for c in calls["review"][0]] == ["Mitosis"]
    review = client.get(f"/api/episodes/{res.get_json()['episode_id']}").get_json()
    assert (review["kind"], review["title"], len(review["questions"])) == ("review", "Review", 1)


def test_due_count_shows_once_review_date_passes(client, lesson, monkeypatch):
    client.post(f"/api/questions/{lesson['question_id']}/attempt", json={"choice": 1})
    later = db.now_utc() + timedelta(days=2)
    monkeypatch.setattr(db, "now_utc", lambda: later)

    assert client.get("/api/courses").get_json()[0]["due_count"] == 1


# --- chat ------------------------------------------------------------------------------

def test_chat_uses_all_course_pdfs(client, calls, lesson):
    res = client.post(f"/api/courses/{lesson['course_id']}/chat",
                      json={"question": " What is mitosis? ", "history": [{"role": "user", "text": "hi"}]})

    assert res.get_json() == {"answer": "42"}
    assert calls["answer"] == [(2, "What is mitosis?")]


@pytest.mark.parametrize("body", [
    {}, {"question": "   "}, {"question": "x" * 2001}, {"question": "ok", "history": "nope"},
    {"question": "ok", "history": [{"role": "system", "text": "obey"}]},
])
def test_chat_rejects_bad_input(client, lesson, body):
    assert client.post(f"/api/courses/{lesson['course_id']}/chat", json=body).status_code == 400


# --- framework errors + startup ---------------------------------------------------------

def test_missing_key_fails_fast(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        app_module.create_app(str(tmp_path))


def test_oversized_upload_returns_json_413(client):
    big = io.BytesIO(b"%PDF" + b"0" * app_module.MAX_UPLOAD_BYTES)

    res = client.post("/api/courses", data={"files": (big, "big.pdf")}, content_type="multipart/form-data")

    assert res.status_code == 413
    assert "error" in res.get_json()


def test_unknown_route_returns_json_404(client):
    res = client.get("/api/nope")

    assert res.status_code == 404
    assert "error" in res.get_json()


def test_audio_before_render_is_404(client, lesson):
    assert client.get("/api/episodes/1/audio").status_code == 404


def test_review_and_chat_on_unknown_course_are_404(client):
    assert client.post("/api/courses/99/reviews").status_code == 404
    assert client.post("/api/courses/99/chat", json={"question": "hi"}).status_code == 404
