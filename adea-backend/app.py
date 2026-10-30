"""HTTP routes and input validation. Persistence is in db.py, model calls in gemini.py."""
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, abort, current_app, g, jsonify, make_response, request
from werkzeug.exceptions import HTTPException

import db
import gemini

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_FILES = 10
MAX_TITLE_CHARS = 120
DEFAULT_OPTIONS = {"length": "10", "depth": "intro", "voice_a": "Puck", "voice_b": "Kore"}

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
    return {**raw, "length": int(raw["length"])}


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
    if error.response is not None:  # already a JSON response from fail()
        return error.response
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
