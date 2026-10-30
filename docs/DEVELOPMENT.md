# Development

## Secrets
- The only secret is `GEMINI_API_KEY`, stored in `adea-backend/.env` (gitignored). The template is in `.env.example`.
- **Never put API keys in frontend code.** Everything in the Vite bundle, including `VITE_*` variables, ships to the browser. All model calls go through the backend.
- The backend refuses to start if the key is missing.
- If a key is ever committed: revoke it right away. Deleting the file doesn't remove it from git history.

## Conventions

### Backend
- `app.py` has routes and validation; `gemini.py` has model calls; `db.py` has SQL. Don't mix them.
- SQL is parameterized only, never built with string formatting.
- Validate everything at the route: file type by magic bytes, options against allowlists, IDs as integers.
- Never swallow errors. Log the detail on the server and return a short JSON error.

### Frontend
- Vue 3 `<script setup>`.
- All HTTP calls go through `src/api.js`, using `fetch`.
- Styling is plain CSS using the custom properties in `styles.css`. No UI library.
- Accessibility basics: real `<button>` and `<label>` elements, visible focus, keyboard-usable dropzone and quiz.

### Both
Small focused files, descriptive names, and no dead code or commented-out blocks.

## Git workflow
- Branch from `main`. The current work is on `revamp`.
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Before opening a PR, `pytest` passes and `npm run build` succeeds.

## Design
The UI is designed in Figma first. Tokens (colors, type and spacing) are copied into `src/styles.css` as CSS custom properties. Change the design in Figma, then update the tokens; don't add one-off colors in components.

## Changing Gemini models
Model IDs are constants at the top of `gemini.py`. Check the [current model list](https://ai.google.dev/gemini-api/docs/models) before changing them. Run the end-to-end checklist in [TESTING.md](TESTING.md) afterwards, because prompt behavior differs between models.
