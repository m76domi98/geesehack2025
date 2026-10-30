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


def document_path(conn: sqlite3.Connection, document_id: int) -> str:
    return conn.execute("SELECT path FROM documents WHERE id = ?", (document_id,)).fetchone()["path"]


def document_paths(conn: sqlite3.Connection, course_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT path FROM documents WHERE course_id = ? ORDER BY position", (course_id,)
    ).fetchall()
    return [r["path"] for r in rows]


# --- episodes ----------------------------------------------------------------

def get_episode(conn: sqlite3.Connection, episode_id: int) -> dict | None:
    """Full episode, including quiz answers. Callers decide what to expose."""
    row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    if row is None:
        return None
    questions = conn.execute(
        "SELECT q.id, k.name AS concept, q.question, q.choices_json, q.answer_index, q.explanation"
        " FROM questions q JOIN concepts k ON k.id = q.concept_id WHERE q.episode_id = ? ORDER BY q.id",
        (episode_id,),
    ).fetchall()
    episode = dict(row)
    episode["script"] = json.loads(episode.pop("script_json")) if row["script_json"] else None
    episode["questions"] = [_question(q) for q in questions]
    return episode


def _question(row: sqlite3.Row) -> dict:
    question = {k: row[k] for k in row.keys() if k != "choices_json"}
    question["choices"] = json.loads(row["choices_json"])
    return question


def prior_concepts(conn: sqlite3.Connection, course_id: int, position: int) -> list[dict]:
    """Concepts taught in episodes before `position`, so later lessons can build on them."""
    rows = conn.execute(
        "SELECT k.name, k.summary FROM concepts k JOIN episodes e ON e.id = k.episode_id"
        " WHERE k.course_id = ? AND e.position < ? ORDER BY k.id",
        (course_id, position),
    ).fetchall()
    return [dict(r) for r in rows]


def _concept_id(conn: sqlite3.Connection, course_id: int, episode_id: int, name: str, summary: str) -> int:
    # ponytail: concept identity is its exact name; fuzzy matching if Gemini drifts on wording
    conn.execute(
        "INSERT INTO concepts (course_id, name, summary, episode_id) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (course_id, name) DO NOTHING",
        (course_id, name, summary, episode_id),
    )
    return conn.execute(
        "SELECT id FROM concepts WHERE course_id = ? AND name = ?", (course_id, name)
    ).fetchone()["id"]


def save_lesson(conn: sqlite3.Connection, episode_id: int, lesson: dict) -> None:
    """Store a generated script plus its concepts and concept-tagged quiz."""
    course_id = conn.execute(
        "SELECT course_id FROM episodes WHERE id = ?", (episode_id,)
    ).fetchone()["course_id"]
    script = {"title": lesson["title"], "chapters": lesson["chapters"]}
    summaries = {c["name"]: c["summary"] for c in lesson["concepts"]}
    with conn:
        conn.execute(
            "UPDATE episodes SET title = ?, script_json = ? WHERE id = ?",
            (lesson["title"], json.dumps(script), episode_id),
        )
        for name, summary in summaries.items():
            _concept_id(conn, course_id, episode_id, name, summary)
        for q in lesson["quiz"]:
            concept_id = _concept_id(conn, course_id, episode_id, q["concept"], summaries.get(q["concept"], ""))
            conn.execute(
                "INSERT INTO questions (episode_id, concept_id, question, choices_json, answer_index, explanation)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (episode_id, concept_id, q["question"], json.dumps(q["choices"]), q["answer_index"], q["explanation"]),
            )


def set_audio(conn: sqlite3.Connection, episode_id: int, path: str) -> None:
    with conn:
        conn.execute("UPDATE episodes SET audio_path = ? WHERE id = ?", (path, episode_id))


def create_review_episode(conn: sqlite3.Connection, course_id: int) -> int:
    with conn:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM episodes WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        return conn.execute(
            "INSERT INTO episodes (course_id, kind, position, title, created_at) VALUES (?, 'review', ?, ?, ?)",
            (course_id, position, "Review", stamp(now_utc())),
        ).lastrowid


# --- quiz + spaced repetition -------------------------------------------------

def get_question(conn: sqlite3.Connection, question_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    return _question(row) if row else None


def record_attempt(conn: sqlite3.Connection, question_id: int, correct: bool, now: datetime) -> None:
    question = conn.execute("SELECT concept_id FROM questions WHERE id = ?", (question_id,)).fetchone()
    schedule = conn.execute(
        "SELECT box FROM concept_schedule WHERE concept_id = ?", (question["concept_id"],)
    ).fetchone()
    box, due_at = next_review(schedule["box"] if schedule else 0, correct, now)
    with conn:
        conn.execute(
            "INSERT INTO attempts (question_id, correct, answered_at) VALUES (?, ?, ?)",
            (question_id, int(correct), stamp(now)),
        )
        conn.execute(
            "INSERT INTO concept_schedule (concept_id, box, due_at) VALUES (?, ?, ?)"
            " ON CONFLICT (concept_id) DO UPDATE SET box = excluded.box, due_at = excluded.due_at",
            (question["concept_id"], box, stamp(due_at)),
        )


def review_concepts(
    conn: sqlite3.Connection, course_id: int, now: datetime, limit: int = REVIEW_CONCEPT_LIMIT
) -> list[dict]:
    """Concepts missed on their latest attempt, or due. Missed first, then oldest due date."""
    rows = conn.execute(
        """
        SELECT k.id, k.name, k.summary, s.due_at,
               (SELECT a.correct FROM attempts a JOIN questions q ON q.id = a.question_id
                 WHERE q.concept_id = k.id ORDER BY a.answered_at DESC, a.id DESC LIMIT 1) AS last_correct
        FROM concepts k JOIN concept_schedule s ON s.concept_id = k.id
        WHERE k.course_id = ?
        """,
        (course_id,),
    ).fetchall()
    due = stamp(now)
    picked = [r for r in rows if r["due_at"] <= due or r["last_correct"] == 0]
    picked.sort(key=lambda r: (r["last_correct"] != 0, r["due_at"]))
    return [{"id": r["id"], "name": r["name"], "summary": r["summary"]} for r in picked[:limit]]
