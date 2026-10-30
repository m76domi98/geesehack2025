# Changelog

All notable changes to Podcastify. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Add an entry under **Unreleased** with every user-facing or API change.

## [Unreleased] (the revamp, on branch `revamp`)

### Added
- **Study loop backend:** courses made of 1–10 PDFs, one lesson episode per PDF, concept-tagged quizzes, and Leitner spaced repetition (boxes 1–5: 1/3/7/14/30 days) that creates short **review episodes** for missed or due concepts.
- **Two-host lessons written by Gemini** (`gemini-3.8-flash`), with chapters. Later lessons build on earlier lessons' concepts, and scripts stick to what the PDF actually covers.
- **Multi-speaker audio** with Gemini TTS (`gemini-3.8-flash-tts`), rendered per chapter and joined into one WAV that supports seeking.
- **Course chat** grounded in the course PDFs.
- **Podcast options:** length (5/10/15 min), depth (intro or exam), a voice for each host.
- **Rot factor (0–100):** slang tiers. At 75+, Tung Tung Tung Sahur replaces Sam as co-host. Facts and quiz wording stay plain at every level.
- **JSON API** (`/api/courses`, `/api/episodes`, `/api/questions`); see `docs/API.md`.
- **SQLite storage** (`adea-backend/data/`), with uploads stored under server-generated names.
- **Tests:** 67 pytest tests with Gemini mocked; coverage is 100% for `app.py`/`db.py` and 99% for `gemini.py`.
- **Docs:** `README`, `docs/` (architecture, API, structure, testing, development), a Figma design handoff, and a UI concept board.

### Changed
- **The script is actually rewritten.** The old pipeline pasted the raw PDF text between an intro and an outro.
- Speechify, pdfplumber and spaCy are replaced by Gemini, so the app needs one API key (`GEMINI_API_KEY`).
- Lower thinking level for script generation (`low`).

### Removed
- The Voiceflow chatbot, the fake Feedback page, unused Vuetify/Pinia code, the old `/upload` route and `podcastify.py`.
- Committed junk: `__pycache__`, `.DS_Store`, sample mp3 and txt output, a stray `.bash_profile`.

### Security
- Hardcoded and committed secrets removed: the Voiceflow key, the frontend `.env`, and a bearer token. **These must still be revoked, because they remain in git history.**
- Input validation added at the API boundary:
  - PDFs checked by their content (magic bytes), not just the file extension
  - size and file-count limits
  - option allowlists
  - integer IDs only, so user input never becomes a file path
- Gemini errors are logged on the server, and the client only gets a generic 502.

### Known issues
- **Slow generation:** Gemini is currently returning `503 Service Unavailable` under load, and the SDK retries silently, so one call can take 3–5 minutes. Planned fix: a request timeout plus a fallback to `gemini-3.5-flash-lite`.
- The frontend still has the old hackathon views and doesn't work with the new API yet. The rewrite will follow the Figma design.

## [0.1.0] (2025, GeeseHacks hackathon, `main`)
- First version: upload a PDF to get a single-voice Speechify reading of its text, plus a Voiceflow chatbot.
