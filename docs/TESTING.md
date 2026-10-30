# Testing

## Backend
```bash
cd adea-backend
.venv/Scripts/python -m pytest          # macOS/Linux: .venv/bin/python -m pytest
```
**No API key is needed.** Every function in `gemini.py` is monkeypatched with a fake that returns fixed data, and each test gets a fresh SQLite database in a temporary directory.

### What's covered (`test_app.py`)
| Area | Cases |
|---|---|
| Spaced repetition | `next_review` steps up through the boxes, caps at box 5, and resets to box 1 on a wrong answer |
| Course creation | valid multi-PDF upload; a non-PDF is rejected (magic bytes, not the extension); bad length, depth or voice is rejected; too many files is rejected |
| Lesson generation | the script is stored; concepts and questions are linked; calling it twice doesn't call Gemini again |
| Quiz | answers are hidden in `GET`; an attempt returns the correct result and updates `concept_schedule` |
| Reviews | a wrong answer makes a review episode about that concept; nothing due returns 409 |
| Errors | unknown IDs return 404; a Gemini exception returns a JSON 502 |

### Writing a test
Use the `client` fixture and the fake Gemini fixtures, in Arrange, Act, Assert order:
```python
def test_wrong_answer_schedules_review(client, course_with_lesson):
    q = course_with_lesson["questions"][0]

    client.post(f"/api/questions/{q['id']}/attempt", json={"choice": q["wrong"]})
    res = client.post(f"/api/courses/{course_with_lesson['id']}/reviews")

    assert res.status_code == 201
```
Test through HTTP routes where you can; test pure functions like `next_review` directly.

## Frontend
```bash
cd adea-frontend
npm run build      # type and template errors fail the build
```
There are no frontend unit tests yet. The UI is checked manually with the end-to-end checklist below. Add Vitest component tests when a component gets real logic, for example the transcript timing.

## End-to-end checklist (real key)
Run both servers, then:
1. Create a course from 2 PDFs with non-default options.
2. Lesson 1 is a two-host dialogue (not the PDF read aloud) and matches the length and depth you chose.
3. The audio plays with both chosen voices. Chapters jump correctly and 1.5x speed works. The transcript highlight follows along.
4. Answer a quiz question wrongly. Set its `due_at` back in `data/podcastify.db`, and the Today page shows a review due.
5. Start review: a short episode about exactly that concept, with new questions.
6. Lesson 2 refers back to lesson 1's concepts.
7. Chat answers a question that needs both PDFs.
8. Uploading a `.txt` renamed to `.pdf` is rejected.
9. Refreshing any page reloads it correctly.
