"""HTTP routes and input validation. Persistence is in db.py, model calls in gemini.py."""
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, abort, current_app, g, jsonify, make_response, request, send_file
from werkzeug.exceptions import HTTPException

import db
import gemini

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_FILES = 10
MAX_TITLE_CHARS = 120
DEFAULT_OPTIONS = {"length": "10", "depth": "intro", "voice_a": "Puck", "voice_b": "Kore", "rot": "0"}

# Routes live on a blueprint so tests can build a fresh app (and temp data dir) per test.
bp = Blueprint("api", __name__, url_prefix="/api")


def fail(status: int, message: str):
    abort(make_response(jsonify(error=message), status))


def get_db():
    if "db" not in g:
        g.db = db.connect(str(Path(current_app.config["DATA_DIR"]) / "podcastify.db"))
    return g.db


def call_gemini(fn, *args):
    """Run a Gemini call; log the real error, give the client a clean 502."""
    try:
        return fn(*args)
    except Exception:
        current_app.logger.exception("Gemini call %s failed", fn.__name__)
        fail(502, "The AI service failed. Please try again.")


def store_file(data: bytes, suffix: str) -> str:
    # Server-generated names only: user input never becomes part of a path.
    path = Path(current_app.config["DATA_DIR"]) / "files" / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return str(path)


def parse_options(form) -> dict:
    raw = {key: form.get(key, default) for key, default in DEFAULT_OPTIONS.items()}
    if not raw["length"].isdigit() or int(raw["length"]) not in gemini.LENGTHS:
        fail(400, f"length must be one of {list(gemini.LENGTHS)}")
    if raw["depth"] not in gemini.DEPTHS:
        fail(400, f"depth must be one of {list(gemini.DEPTHS)}")
    if raw["voice_a"] not in gemini.VOICES or raw["voice_b"] not in gemini.VOICES:
        fail(400, f"voices must be from {list(gemini.VOICES)}")
    if raw["voice_a"] == raw["voice_b"]:
        fail(400, "The two hosts need different voices")
    if not raw["rot"].isdigit() or int(raw["rot"]) > gemini.MAX_ROT:
        fail(400, f"rot must be a whole number from 0 to {gemini.MAX_ROT}")
    return {**raw, "length": int(raw["length"]), "rot": int(raw["rot"])}


def read_pdfs(files) -> list[tuple[str, bytes]]:
    if not 1 <= len(files) <= MAX_FILES:
        fail(400, f"Upload between 1 and {MAX_FILES} PDFs")
    pdfs = []
    for file in files:
        data = file.read()
        if not data.startswith(b"%PDF"):
            fail(400, f"{file.filename or 'A file'} is not a PDF")
        pdfs.append((file.filename or "document.pdf", data))
    return pdfs


def create_app(data_dir: str | None = None, require_key: bool = True) -> Flask:
    load_dotenv()
    if require_key and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
    flask_app = Flask(__name__)
    flask_app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    flask_app.config["DATA_DIR"] = data_dir or str(Path(__file__).parent / "data")
    (Path(flask_app.config["DATA_DIR"]) / "files").mkdir(parents=True, exist_ok=True)
    flask_app.register_blueprint(bp)
    flask_app.register_error_handler(HTTPException, json_error)
    flask_app.teardown_appcontext(close_db)
    logging.basicConfig(level=logging.INFO)
    return flask_app


def json_error(error: HTTPException):
    # Framework errors (unknown route, 413...). fail() responses are already JSON and skip this.
    return jsonify(error=error.description), error.code


def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@bp.post("/courses")
def create_course():
    options = parse_options(request.form)
    pdfs = read_pdfs(request.files.getlist("files"))
    title = (request.form.get("title") or "").strip() or Path(pdfs[0][0]).stem
    documents = [(name, store_file(data, ".pdf")) for name, data in pdfs]
    course_id = db.create_course(get_db(), title[:MAX_TITLE_CHARS], options, documents)
    return jsonify(id=course_id), 201


@bp.get("/courses")
def list_courses():
    return jsonify(db.list_courses(get_db(), db.now_utc()))


@bp.get("/courses/<int:course_id>")
def get_course(course_id: int):
    course = db.get_course(get_db(), course_id, db.now_utc())
    if course is None:
        fail(404, "Course not found")
    return jsonify(course)


# --- episodes ----------------------------------------------------------------

def load_episode(episode_id: int) -> dict:
    episode = db.get_episode(get_db(), episode_id)
    if episode is None:
        fail(404, "Episode not found")
    return episode


def public_episode(episode: dict) -> dict:
    """Episode as the client sees it: quiz answers stay hidden until an attempt."""
    script = episode["script"] or {}
    return {
        "id": episode["id"],
        "course_id": episode["course_id"],
        "kind": episode["kind"],
        "position": episode["position"],
        "title": episode["title"],
        "chapters": script.get("chapters", []),
        "questions": [
            {key: q[key] for key in ("id", "concept", "question", "choices")} for q in episode["questions"]
        ],
        "has_script": episode["script"] is not None,
        "has_audio": episode["audio_path"] is not None,
    }


@bp.get("/episodes/<int:episode_id>")
def get_episode(episode_id: int):
    return jsonify(public_episode(load_episode(episode_id)))


@bp.post("/episodes/<int:episode_id>/script")
def write_script(episode_id: int):
    episode = load_episode(episode_id)
    if episode["script"] is None:
        # ponytail: two simultaneous requests could both generate; add a lock if that ever happens
        conn = get_db()
        lesson = call_gemini(
            gemini.write_lesson,
            Path(db.document_path(conn, episode["document_id"])).read_bytes(),
            db.prior_concepts(conn, episode["course_id"], episode["position"]),
            db.course_options(conn, episode["course_id"]),
        )
        db.save_lesson(conn, episode_id, lesson)
        episode = load_episode(episode_id)
    return jsonify(public_episode(episode))


@bp.post("/episodes/<int:episode_id>/audio")
def render_audio(episode_id: int):
    episode = load_episode(episode_id)
    if episode["script"] is None:
        fail(409, "Generate the script first")
    if episode["audio_path"] is None:
        options = db.course_options(get_db(), episode["course_id"])
        audio = call_gemini(gemini.synthesize, episode["script"], options)
        db.set_audio(get_db(), episode_id, store_file(audio, ".wav"))
    return jsonify(ok=True)


@bp.get("/episodes/<int:episode_id>/audio")
def stream_audio(episode_id: int):
    episode = load_episode(episode_id)
    if episode["audio_path"] is None:
        fail(404, "Audio not rendered yet")
    return send_file(episode["audio_path"], mimetype="audio/wav", conditional=True)


# --- quiz, reviews, chat -------------------------------------------------------

MAX_QUESTION_CHARS = 2000
MAX_HISTORY_TURNS = 20


def course_pdfs(course_id: int) -> list[bytes]:
    return [Path(path).read_bytes() for path in db.document_paths(get_db(), course_id)]


def require_course(course_id: int) -> None:
    if db.get_course(get_db(), course_id, db.now_utc()) is None:
        fail(404, "Course not found")


@bp.post("/questions/<int:question_id>/attempt")
def attempt(question_id: int):
    question = db.get_question(get_db(), question_id)
    if question is None:
        fail(404, "Question not found")
    choice = (request.get_json(silent=True) or {}).get("choice")
    if type(choice) is not int or not 0 <= choice < len(question["choices"]):
        fail(400, "choice must be the index of one of the options")
    correct = choice == question["answer_index"]
    db.record_attempt(get_db(), question_id, correct, db.now_utc())
    return jsonify(correct=correct, answer_index=question["answer_index"], explanation=question["explanation"])


@bp.post("/courses/<int:course_id>/reviews")
def create_review(course_id: int):
    require_course(course_id)
    concepts = db.review_concepts(get_db(), course_id, db.now_utc())
    if not concepts:
        fail(409, "Nothing to review right now")
    # Generate before creating the episode so a Gemini failure leaves no empty episode behind.
    lesson = call_gemini(
        gemini.write_review, course_pdfs(course_id), concepts, db.course_options(get_db(), course_id)
    )
    episode_id = db.create_review_episode(get_db(), course_id)
    db.save_lesson(get_db(), episode_id, lesson)
    return jsonify(episode_id=episode_id), 201


def parse_history(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > MAX_HISTORY_TURNS:
        fail(400, f"history must be a list of at most {MAX_HISTORY_TURNS} turns")
    for turn in raw:
        if not (isinstance(turn, dict) and turn.get("role") in ("user", "model")
                and isinstance(turn.get("text"), str) and len(turn["text"]) <= MAX_QUESTION_CHARS):
            fail(400, "each history turn needs role 'user' or 'model' and text")
    return [{"role": turn["role"], "text": turn["text"]} for turn in raw]


@bp.post("/courses/<int:course_id>/chat")
def chat(course_id: int):
    require_course(course_id)
    body = request.get_json(silent=True) or {}
    question = body.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
        fail(400, f"question must be 1-{MAX_QUESTION_CHARS} characters")
    history = parse_history(body.get("history", []))
    reply = call_gemini(gemini.answer, course_pdfs(course_id), history, question.strip())
    return jsonify(answer=reply)
