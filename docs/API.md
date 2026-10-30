# API

Base path: `/api`. Request and response bodies are JSON unless noted.

Errors look like `{"error": "human-readable message"}`, with these status codes:
| Status | Meaning |
|---|---|
| 400 | Invalid input (bad file, bad option, missing field) |
| 404 | Unknown ID |
| 409 | Nothing to do (for example, no concepts are due for review) |
| 413 | Upload too large |
| 502 | Gemini failed (details are logged on the server, not sent to the client) |

## Courses

### `POST /api/courses`
Multipart form:
| Field | Type | Rules |
|---|---|---|
| `files` | PDF, repeated | 1–10 files, each must start with `%PDF`; order sets episode order |
| `title` | string | optional; defaults to the first filename |
| `length` | `5` \| `10` \| `15` | minutes per lesson |
| `depth` | `intro` \| `exam` | |
| `voice_a`, `voice_b` | Gemini voice name | must be on the allowlist and different from each other |

→ `201 {"id": 1}`

### `GET /api/courses`
→ `[{"id", "title", "created_at", "episodes_total", "episodes_done", "due_count"}]`, newest first.

### `GET /api/courses/<id>`
→ `{"id", "title", "options", "documents": [...], "episodes": [{"id", "kind", "position", "title", "has_script", "has_audio"}], "concepts": [{"id", "name", "box", "due_at"}], "due_count"}`

### `POST /api/courses/<id>/reviews`
Makes a review episode from up to 5 concepts that are due or were recently missed.
→ `201 {"episode_id": 7}`, or `409` if nothing is due.

### `POST /api/courses/<id>/chat`
`{"history": [{"role": "user"|"model", "text": "..."}], "question": "..."}` → `{"answer": "..."}`

## Episodes

### `POST /api/episodes/<id>/script`
Generates the lesson script (with its concepts and quiz) if it doesn't exist yet. It's safe to call again.
→ the same body as `GET`.

### `GET /api/episodes/<id>`
→ `{"id", "course_id", "kind", "position", "title", "chapters": [...], "questions": [{"id", "concept", "question", "choices"}], "has_script", "has_audio"}`
Answers aren't included; they're only revealed by an attempt.

### `POST /api/episodes/<id>/audio`
Renders the audio if it's missing → `{"ok": true}`. The script must exist first, otherwise 409.

### `GET /api/episodes/<id>/audio`
→ `audio/wav` stream, which supports range requests so the player can seek.

## Questions

### `POST /api/questions/<id>/attempt`
`{"choice": 2}` → `{"correct": false, "answer_index": 1, "explanation": "..."}`
Records the attempt and updates the concept's spaced-repetition schedule.
