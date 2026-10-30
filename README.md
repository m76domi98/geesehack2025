# Podcastify

**Turn your course PDFs into a podcast that actually checks you learned something.**

Upload your lecture notes or readings and Podcastify makes a series of two-host lesson episodes, each building on the last. Every episode ends with a short quiz. Podcastify tracks which concepts you miss and brings them back as short review episodes, scheduled with spaced repetition, until they stick.

> 🚧 A rewrite is in progress on the `revamp` branch. The original hackathon version (GeeseHacks 2025) is on `main`.

## Features
- **Course mode:** several PDFs make an ordered series of lessons, and later lessons refer back to earlier ones.
- **Two-host dialogue:** the material is explained in conversation, not read aloud.
- **Options:** length (5 / 10 / 15 min), depth (intro or exam review), and host voices.
- **Rot factor:** a 0–100 brainrot slider. At 75+, Tung Tung Tung Sahur becomes your co-host and gameplay footage plays in the background. The facts stay correct.
- **Player:** chapters, 1x to 2x speed, and a transcript that follows along.
- **Concept-tagged quizzes:** every question is linked to a concept from the episode.
- **Spaced repetition:** missed or due concepts come back as review episodes with fresh questions.
- **Chat with your course:** ask questions grounded in your PDFs.

## Tech
| Layer | Stack |
|---|---|
| Frontend | Vue 3, Vite, Vue Router, plain CSS |
| Backend | Python 3.12, Flask, SQLite |
| AI | Google Gemini: `gemini-3.8-flash` for scripts, quizzes and chat; `gemini-3.8-flash-tts` for multi-speaker audio |

## Getting started

### Prerequisites
- Python 3.12+
- Node 20+
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Backend
```bash
cd adea-backend
python -m venv .venv
.venv/Scripts/activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env          # then set GEMINI_API_KEY
flask --app app run --debug   # http://localhost:5000
```

### Frontend
```bash
cd adea-frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :5000)
```

## Docs
- [Architecture](docs/ARCHITECTURE.md): how the study loop, data model and Gemini calls fit together
- [API](docs/API.md): backend endpoints
- [Project structure](docs/STRUCTURE.md): where things live
- [Testing](docs/TESTING.md): how to run and write tests
- [Development](docs/DEVELOPMENT.md): conventions, secrets and workflow
- [Changelog](CHANGELOG.md): what changed
