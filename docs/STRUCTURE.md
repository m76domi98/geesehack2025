# Project structure

Layout after the revamp. The backend is done; the frontend files listed are the target.

```
geesehack2025/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md      # study loop, data model, Gemini calls
│   ├── API.md               # endpoint reference
│   ├── STRUCTURE.md         # this file
│   ├── TESTING.md           # running and writing tests
│   └── DEVELOPMENT.md       # conventions, secrets, workflow
│
├── adea-backend/            # Flask API
│   ├── app.py               # routes and input validation only
│   ├── gemini.py            # every Gemini call: write_lesson, write_review, synthesize, answer
│   ├── db.py                # SQLite schema, queries, next_review() spaced-repetition rule
│   ├── test_app.py          # API route tests (Gemini mocked)
│   ├── test_db.py           # queries and spaced-repetition rule
│   ├── test_gemini.py       # offline checks: WAV joining, schema validation
│   ├── test.pdf             # sample PDF for manual end-to-end runs
│   ├── requirements.txt
│   ├── .env.example         # copy to .env and add GEMINI_API_KEY
│   └── data/                # gitignored: podcastify.db, uploaded PDFs, rendered audio
│
└── adea-frontend/           # Vue 3 + Vite SPA
    ├── index.html
    ├── vite.config.js       # /api proxy to localhost:5000
    └── src/
        ├── main.js
        ├── App.vue          # shell and nav
        ├── api.js           # fetch wrappers for every endpoint
        ├── styles.css       # design tokens (from Figma) and base styles
        ├── router/index.js
        ├── views/
        │   ├── TodayView.vue    # /: review-due card and course library
        │   ├── NewCourseView.vue# /new: upload PDFs and options
        │   ├── CourseView.vue   # /courses/:id: episodes, mastery, chat
        │   └── EpisodeView.vue  # /episodes/:id: player, transcript, quiz
        └── components/
            ├── UploadForm.vue
            ├── CourseList.vue
            ├── ConceptMastery.vue
            ├── PodcastPlayer.vue
            ├── Transcript.vue
            ├── Quiz.vue
            └── CourseChat.vue
```

## Where does X go?
| Change | File |
|---|---|
| New or changed prompt, model or voice | `adea-backend/gemini.py` |
| New table, column or query | `adea-backend/db.py` |
| New endpoint or validation rule | `adea-backend/app.py` (and document it in `docs/API.md`) |
| New screen | `adea-frontend/src/views/` plus a route in `router/index.js` |
| Color, spacing or font | the CSS custom properties at the top of `src/styles.css` |
