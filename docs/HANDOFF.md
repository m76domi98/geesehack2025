# Handoff: build the Vue frontend from the Figma design

Your job is to build the Podcastify frontend (phase 3), using the approved Figma design and the finished backend. Read this whole file first. Then skim `README.md`, `docs/ARCHITECTURE.md` and `docs/API.md`. The API doc is the contract for every request you make.

## Where things stand
- **Backend:** done and tested (`adea-backend/`, about 41 pytest tests, Gemini mocked). Don't change the backend or the API. If something in the API seems wrong, write it down and ask.
- **Design:** done and approved, in Figma (link below).
- **Frontend:** still the hackathon leftovers. You're replacing it.

## The Figma file
**https://www.figma.com/design/NCP46BjTST3o0qdUnti1K3** (file key `NCP46BjTST3o0qdUnti1K3`)

Call `create_session` with that key, then read frames with `get_design_context` and `get_screenshot`, and tokens with `get_variable_defs`. Load the `/figma-design-to-code` skill (resource `skill://figma/figma-design-to-code/SKILL.md`) before calling `get_design_context`. Its output is a reference to adapt to plain Vue and CSS, not code to paste.

The file has three pages:

| Page | What's on it |
|---|---|
| **Foundations** (`0:1`) | The design-tokens board: colors in light and dark, rot accents, contrast notes, type scale, spacing and radii |
| **Components** (`2:64`) | One component set per Vue component, with variants. **Read each component's description**; it holds behavior, accessibility and API notes. |
| **Screens** (`2:65`) | Desktop (1440) and mobile (390) frames, in rows 1–6 |

### Tokens → `src/styles.css`
The variables are in three collections:
- `Color`, with Light and Dark modes
- `Rot`, the rot-mode palette
- `Dimension`: `space/*`, `radius/*`, `font-size/*`

Each variable's web code syntax is already its CSS name. So `color/bg` becomes `--color-bg`, and `space/4` becomes `--space-4` (16px; the scale is a 4px base). Put them all at the top of `src/styles.css` as custom properties:
- the Light values in `:root`
- the Dark values in `[data-theme="dark"]`
- the rot palette in `.rot` or `:root`, whichever you find cleaner

**Font:** Manrope from Google Fonts, weights 400, 500, 600, 700 and 800. The text styles are:

| Style | Size / line height | Weight |
|---|---|---|
| Display | 32/40 | 800 |
| Heading | 24/32 | 700 |
| Title | 16/24 | 700 |
| Body L | 16/24 | 400 |
| Body | 14/20 | 400 |
| Label | 14/20 | 600 |
| Caption | 12/16 | 500 |

### Components → Vue
| Figma component (node) | Vue file | Notes |
|---|---|---|
| `Button` (`5:62`) | `components/BaseButton.vue` | variants primary, secondary, accent, ghost, danger; optional leading icon; minimum height 44 |
| `Pill` (`5:75`) | `components/StatusPill.vue` | tones Due, Neutral, Success, Primary, Accent, Rot |
| `Tab` (`5:101`), `SegmentOption` (`5:110`) | `components/TabBar.vue`, `components/SegmentedControl.vue` | use real `role="tablist"` and `role="radiogroup"` |
| `NavItem` (`5:123`), `Sidebar` (`14:561`), `TopBar` (`14:599`) | `components/AppShell.vue` | sidebar on desktop; top bar plus menu sheet on mobile |
| `TextField` (`5:147`) | `components/TextField.vue` | |
| `Toast` (`5:176`) | `components/ToastHost.vue` plus a small toast store | |
| `CourseCard` (`6:93`) | `components/CourseCard.vue` | Card layout on desktop, Row layout on mobile |
| `ReviewCard` (`6:142`) | `components/ReviewCard.vue` | |
| `EpisodeRow` (`6:241`) | `components/EpisodeRow.vue` | 6 states (see below) |
| `ConceptRow` (`6:302`), `ConceptMastery` (`14:467`) | `components/ConceptMastery.vue` | |
| `PodcastPlayer` (`9:360`) | `components/PodcastPlayer.vue` | Normal and Rot modes; desktop and mobile layouts |
| `TranscriptLine` (`9:385`), `Transcript` (`20:2692`) | `components/TranscriptView.vue` | Alex, Sam and Tung lines, plus the active line |
| `QuizChoice` (`11:257`), `Quiz` (`11:425`) | `components/EpisodeQuiz.vue` | states Unanswered, Correct, Incorrect, Score |
| `GeneratingPanel` (`12:416`) | `components/GeneratingPanel.vue` | steps Writing script and Recording audio; desktop and mobile |
| `Dropzone` (`12:439`), `FileRow` (`12:497`), `VoicePicker` (`13:455`), `RotSlider` (`13:580`), `UploadForm` (`15:1250`) | `components/UploadForm.vue` plus the small parts | |
| `ChatMessage` (`14:432`), `CourseChat` (`14:433`) | `components/CourseChat.vue` | |
| `Skeleton` (`14:560`) | `components/SkeletonBlock.vue` | |
| `Mascot` (`4:125`), `TungAvatar` (`4:141`) | `src/assets/*.svg` | export as SVG; both are original drawings |
| `GameplayPlaceholder` (`4:142`) | part of the rot player | stand-in for the YouTube embed (see rot mode below) |
| `Icons` (`4:2`) | inline SVG components or `assets/icons/*.svg` | 24px, 2px stroke; use `currentColor` |

Vue component names must be multi-word (eslint `vue/multi-word-component-names`), which is why some file names differ from the Figma names. Keep the Figma name in a comment at the top of each file.

### Screens → routes
| Route | View | Figma frames |
|---|---|---|
| `/` | `views/TodayView.vue` | `Today`, `Today / Mobile`, `Today / Empty`, `Today / Empty / Mobile`, `Today / Loading` |
| `/new` | `views/NewCourseView.vue` | `NewCourse`, `/ Invalid file`, `/ Too many files`, `/ Uploading`, `/ Mobile` |
| `/courses/:id` | `views/CourseView.vue` | `Course`, plus `Course / Episodes`, `/ Concepts` and `/ Chat / Mobile` |
| `/episodes/:id` | `views/EpisodeView.vue` | `Episode`, `/ Writing script`, `/ Recording audio`, `/ Mobile`, `/ Quiz / Mobile`, `/ Writing script / Mobile`, `Episode / Rot mode` (+ mobile) |
| `*` | `views/NotFoundView.vue` | `NotFound`, `NotFound / Mobile` |

The `Shared states` frame shows the toasts, the inline error banner, validation messages and skeletons.

## Behavior the frames don't show
- **The backend gives no progress signal for generation.** `POST /episodes/:id/script` takes about 1–3 minutes and `/audio` about 1 minute, and each holds the request open until it's done. So the generating UI is driven by the client:
  - an elapsed timer
  - an indeterminate shimmer (no fake percentages)
  - tips that rotate every ~8 seconds
  - `aria-live="polite"` announcements
  - respect for `prefers-reduced-motion`

  Use the copy "keep this tab open". Don't promise that the user can leave.
- **Episode states** come from `has_script` and `has_audio`, plus whether a request is in flight and whether the quiz is finished:
  - Not generated
  - Writing script
  - Script ready
  - Recording audio
  - Audio ready
  - Done

  The API doesn't store quiz completion, so for now track "Done" on the client per episode (for example in `localStorage`), or leave it out and ask.
- **Course progress:** `GET /api/courses` returns `episodes_done` and `episodes_total`. Use those for the CourseCard progress bar.
- **Review:** `POST /courses/:id/reviews` returns `{episode_id}`; route to that episode. If it returns 409, nothing is due, so show the green "Nothing is due" message, not an error.
- **Quiz:** choosing an answer immediately calls `POST /questions/:id/attempt`. The response is `{correct, answer_index, explanation}`. Show Correct or Incorrect with an icon and words, never color alone.
- **Upload:** check everything on the client before submitting:
  - 1–10 PDFs
  - each file is a PDF (by type and extension; the server also checks the `%PDF` bytes)
  - 20 MB total
  - `voice_a` and `voice_b` are different

  Show server 400 and 413 messages in the same inline spots.
- **Voices:** Puck, Kore, Charon, Aoede, Fenrir, Leda, Orus, Zephyr. The ▶ preview has no backend support, so either leave it as a disabled button labelled "Preview coming soon" or ask.
- **Rot mode:** when the course's `options.rot` is 75 or higher:
  - wrap the episode page in `data-theme="dark"` and use the rot palette
  - the Tung avatar replaces Sam's
  - a **muted, looping** gameplay video sits next to the player (a YouTube embed with `mute=1&loop=1&playlist=<id>`, and a "Hide gameplay" toggle). Ask the user for the video ID; until then use the placeholder.
- **Chat:** keep the history on the client and send `{history, question}`. Show the typing dots while the request is pending.
- **Desktop Course has no tabs.** That was a deliberate design choice: the episodes list sits next to Concept mastery and Chat. Only mobile uses the Episodes / Concepts / Chat tabs.

## Known quirks in the Figma file
- A component's text property shows the **same default text in every variant**, for example every Toast variant says "The AI service failed…". Use the screens for real copy, not the component defaults.
- The positions of the RotSlider and seek-bar handles are approximate at non-default widths. Use a native `<input type="range">` styled with CSS.
- The CourseCard progress bar in the screens may not match the percentage exactly. Compute it from the data.

## The current frontend (cleanup first)
These are fixes, not design work:
- `src/router/index.js` imports `views/Feedback.vue` and `components/Chatbot.vue`, which don't exist, **so the build is currently broken**.
- The old views (`Home`, `Upload`, `Output`) and components (`FileUpload`, `AudioPlayer`) call the removed `/upload` route. Delete them and replace them with the new views.
- `vite.config.js` has **no `/api` proxy** yet, although the docs say it does. Add `server.proxy['/api'] = 'http://localhost:5000'`.
- The styles live at `src/assets/styles.css`. The docs say `src/styles.css`, so move them there and update the import in `main.js`.
- `vuetify` and `axios` are in `package.json`, but the plan is plain CSS and `fetch`. Remove them unless you find a real need. Keep `pinia` and `@vueuse/core` only if you use them.

## Rules
- Plain CSS with the token custom properties only, so no one-off hex values in components. `<script setup>` everywhere.
- **No secrets in the frontend.** Anything in the Vite bundle is public; the Gemini key stays in `adea-backend/.env`.
- Put every API call in one small `src/api.js`, which uses `fetch`, parses `{error}` bodies and throws readable errors.
- **Accessibility:**
  - WCAG AA (the token pairs are already checked; see the Foundations board)
  - a visible `:focus-visible` ring (3px `--color-focus`)
  - touch targets of 44px or more
  - real buttons, links and labels
  - `aria-current` for the active nav item and the active transcript line
- Write tests with Vitest and `@vue/test-utils`: at minimum `api.js` error handling, upload validation, and the quiz state machine. Mock `fetch`.

## Workflow
1. Do the cleanup above, and get `npm run build` passing on an empty shell.
2. Add the tokens and base styles, then the app shell (Sidebar and TopBar).
3. Build the components in dependency order, comparing each with its Figma component.
4. Build the views in order: Today, NewCourse, Course, Episode, rot mode, and the shared states.
5. Run it against the real backend:
   - `cd adea-backend && .venv/Scripts/python -m flask --app app run --debug`
   - `cd adea-frontend && npm run dev`

   Check every frame at 1440 and 390 widths.
6. Make small, logical commits with conventional messages on a branch off `main`. When you're done, update `docs/STRUCTURE.md` and `CHANGELOG.md`, then open a PR.

## Out of scope
- Changing the backend or API.
- Accounts or login (the app is single-user).
- Streaks (not tracked).
- Real gameplay footage, or copied Tung Tung Tung Sahur art.
