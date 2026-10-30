"""SQLite persistence and the spaced-repetition rule. No Flask, no Gemini."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

# Leitner boxes: a correct answer moves a concept up one box, a wrong one resets it to box 1.
BOX_INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_BOX = 5
REVIEW_CONCEPT_LIMIT = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    options_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('lesson', 'review')),
    document_id INTEGER REFERENCES documents(id),
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    script_json TEXT,
    audio_path TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    summary TEXT NOT NULL,
    episode_id INTEGER NOT NULL REFERENCES episodes(id),
    UNIQUE (course_id, name)
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    question TEXT NOT NULL,
    choices_json TEXT NOT NULL,
    answer_index INTEGER NOT NULL,
    explanation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    correct INTEGER NOT NULL,
    answered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS concept_schedule (
    concept_id INTEGER PRIMARY KEY REFERENCES concepts(id) ON DELETE CASCADE,
    box INTEGER NOT NULL,
    due_at TEXT NOT NULL
);
"""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def stamp(dt: datetime) -> str:
    # Fixed-width UTC ISO strings compare correctly as text in SQL.
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_review(box: int, correct: bool, now: datetime) -> tuple[int, datetime]:
    """Return (new_box, due_at) after an answer. box=0 means never reviewed."""
    new_box = min(box + 1, MAX_BOX) if correct else 1
    return new_box, now + timedelta(days=BOX_INTERVAL_DAYS[new_box])


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --- courses -----------------------------------------------------------------

def create_course(
    conn: sqlite3.Connection, title: str, options: dict, documents: list[tuple[str, str]]
) -> int:
    """documents: [(filename, stored_path)] in lesson order. Returns the course id."""
    created = stamp(now_utc())
    with conn:
        course_id = conn.execute(
            "INSERT INTO courses (title, options_json, created_at) VALUES (?, ?, ?)",
            (title, json.dumps(options), created),
        ).lastrowid
        for position, (filename, path) in enumerate(documents, start=1):
            doc_id = conn.execute(
                "INSERT INTO documents (course_id, position, filename, path) VALUES (?, ?, ?, ?)",
                (course_id, position, filename, path),
            ).lastrowid
            conn.execute(
                "INSERT INTO episodes (course_id, kind, document_id, position, title, created_at)"
                " VALUES (?, 'lesson', ?, ?, ?, ?)",
                (course_id, doc_id, position, f"Lesson {position}", created),
            )
    return course_id


def list_courses(conn: sqlite3.Connection, now: datetime) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.id, c.title, c.created_at,
               (SELECT COUNT(*) FROM episodes e WHERE e.course_id = c.id) AS episodes_total,
               (SELECT COUNT(*) FROM episodes e WHERE e.course_id = c.id AND e.script_json IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.episode_id = e.id
                                  AND NOT EXISTS (SELECT 1 FROM attempts a WHERE a.question_id = q.id))
               ) AS episodes_done,
               (SELECT COUNT(*) FROM concepts k JOIN concept_schedule s ON s.concept_id = k.id
                 WHERE k.course_id = c.id AND s.due_at <= ?) AS due_count
        FROM courses c ORDER BY c.created_at DESC, c.id DESC
        """,
        (stamp(now),),
    ).fetchall()
    return [dict(r) for r in rows]


def get_course(conn: sqlite3.Connection, course_id: int, now: datetime) -> dict | None:
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    if course is None:
        return None
    documents = conn.execute(
        "SELECT id, position, filename FROM documents WHERE course_id = ? ORDER BY position",
        (course_id,),
    ).fetchall()
    episodes = conn.execute(
        "SELECT id, kind, position, title, script_json IS NOT NULL AS has_script,"
        " audio_path IS NOT NULL AS has_audio FROM episodes WHERE course_id = ? ORDER BY position",
        (course_id,),
    ).fetchall()
    concepts = conn.execute(
        "SELECT k.id, k.name, k.summary, s.box, s.due_at FROM concepts k"
        " LEFT JOIN concept_schedule s ON s.concept_id = k.id WHERE k.course_id = ? ORDER BY k.id",
        (course_id,),
    ).fetchall()
    due = stamp(now)
    return {
        "id": course["id"],
        "title": course["title"],
        "options": json.loads(course["options_json"]),
        "created_at": course["created_at"],
        "documents": [dict(r) for r in documents],
        "episodes": [{**dict(r), "has_script": bool(r["has_script"]), "has_audio": bool(r["has_audio"])}
                     for r in episodes],
        "concepts": [dict(r) for r in concepts],
        "due_count": sum(1 for r in concepts if r["due_at"] and r["due_at"] <= due),
    }


def course_options(conn: sqlite3.Connection, course_id: int) -> dict:
    row = conn.execute("SELECT options_json FROM courses WHERE id = ?", (course_id,)).fetchone()
    return json.loads(row["options_json"])


def document_paths(conn: sqlite3.Connection, course_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT path FROM documents WHERE course_id = ? ORDER BY position", (course_id,)
    ).fetchall()
    return [r["path"] for r in rows]
