# Handoff: Figma design for Podcastify

You're designing the UI for Podcastify in Figma. The backend is done; the Vue frontend is built **from your Figma file** afterwards, so the design has to map cleanly to components. Read this whole file first, and skim `README.md`, `docs/ARCHITECTURE.md` and `docs/API.md` for context.

**Your deliverable** is a new Figma file with design tokens, components and screens (listed below), then a link to it for the user. **The user reviews it before any frontend code is written.** Don't write Vue code yourself.

## Start from the reference board
**`docs/Podcastify study-loop UI board.png`** is the user's concept board. Open it first. It's the visual direction, not a pixel spec: build it properly in Figma and improve it where you see fit. The user said to feel free to change things up.

**Keep from the board:**
- **Look:** a warm off-white background, deep green primary, and a lime accent; rounded cards; and the friendly lime **headphone mascot** in the review cards.
- **Type:** Manrope with a 12 / 14 / 16 / 24 / 32 px scale. Radii of 8 / 12 / 20.
- **Tokens:** as read from the board, so confirm them by eye:

  | Token | Hex |
  |---|---|
  | `color/bg` | `#F7F6F2` |
  | `color/text` | `#202922` |
  | `color/primary` | `#245842` |
  | `color/host-a` | green |
  | `color/host-b` | purple (about `#6542B8`) |
  | `rot/acid` | `#D8EF85` |
  | `rot/coral` | `#F7785D` |

- **Voice and copy:**
  - "A little review goes a long way."
  - "Study more. Scroll less."
  - "Small steps. Big retention."
  - "Stay focused… (ish)" in rot mode
  - The status lines on episodes: "Audio ready · 10:00", "Script ready", "Not generated yet".
- **Layout:**
  - desktop has a left sidebar nav (Today, Courses, New course); mobile has a top bar with a hamburger menu
  - Course has **Episodes / Concepts / Chat** tabs
  - Episode has a green player card, chapter pills, a transcript, and the quiz side by side (tabs on mobile)
  - Rot mode is dark, with a "ROT 88" badge, a 9:16 gameplay placeholder, and coral or acid Tung lines
- **Extra sections:** the design-tokens strip, the UI components strip and the shared-states strip at the bottom. Build them as real Figma variables, components and frames.

**Fix these where the board doesn't match the backend:**
1. **Rot is a 0–100 slider**, not 4 chips, and it isn't "for later" because it's built. Show the tier labels (Normal, Casual, Brainrot, Tung Tung Tung Sahur) as marks under the slider.
2. **Upload limit:** 1–10 PDFs, **20 MB total per course**, not "50 MB each".
3. **Host picker:** the hosts are fixed names, **Alex** (explains) and **Sam** (curious student). The user picks a **voice** for each from: Puck, Kore, Charon, Aoede, Fenrir, Leda, Orus, Zephyr. The board labels a host "Puck", which is a voice name. Show the host name with a voice dropdown, ideally with a ▶ preview icon.
4. **Episode states:** the "Generate" button on not-generated episodes is right. Also add the **generating** states (script takes about 1–3 min, audio about 1 min). These are slow, so they need real loading designs, not a spinner.
5. **Tung Tung Tung Sahur avatar:** the board's cartoon log is fine as a direction. Keep it an **original drawing**, not copied fan art.
6. **No streaks yet:** "Keep your streak going!" implies data the backend doesn't track. Use copy that doesn't promise a streak count, or mark streaks as a clearly labeled future idea.

## What the product is
Podcastify is a **study loop**, not just a "PDF to podcast" tool:
1. Upload course PDFs, which make a **course**.
2. Each PDF becomes a **lesson episode**: two hosts explain it in conversation, with chapters.
3. Each episode ends with a **quiz**, and every question is tagged with a **concept**.
4. Wrong answers and due concepts come back as short **review episodes**, on a spaced-repetition schedule (Leitner boxes 1–5).
5. You can **chat** with your course PDFs.

**Rot factor (0–100 slider):** brainrot delivery mode. At 75+, the co-host becomes **Tung Tung Tung Sahur** (the meme character), and a muted, looping gameplay video plays behind the player. This is a fun, signature feature, so make rot mode feel deliberately chaotic while normal mode stays calm and focused.

**Audience:** students. **Tone:** friendly, focused and a bit playful. Don't make it a generic SaaS dashboard.

## Screens (desktop 1440 wide, plus a mobile 390 wide for each)
Name frames exactly like this; the names map to Vue views and components.

### 1. `Today` (route `/`)
- **Review card** (the hero element): "4 concepts due · ~4 min" plus a **Start review** button. One card per course with `due_count > 0`.
- **Course library:** cards showing the title, a progress bar (`episodes_done / episodes_total`) and a due badge.
- **New course** button.
- Empty state: no courses yet, with an upload CTA.

### 2. `NewCourse` (route `/new`)
- **Multi-PDF dropzone** (1–10 files). The file list can be **reordered**, since order equals lesson order, and files can be removed.
- An optional course title.
- Options:
  - **Length:** 5 / 10 / 15 min (segmented control)
  - **Depth:** "Intro" or "Exam review"
  - **Voices:** a picker for each host
  - **Rot factor:** a 0–100 slider with tier labels:
    - 0–24: Normal
    - 25–49: Casual
    - 50–74: Brainrot
    - 75–100: Tung Tung Tung Sahur
    - The slider should visibly escalate as it goes up.
- **Create course** button.
- States: invalid file ("x.pdf is not a PDF"), too many files, uploading.

### 3. `Course` (route `/courses/:id`)
- **Episode list:** lessons and reviews, each in one of these states:
  - not generated
  - script ready
  - audio ready
  - done (quiz finished)
- **Concept mastery:** each concept with its box level (1–5) and when it's next due.
- **Chat panel:** messages plus an input box.
- The review card again, if anything is due.

### 4. `Episode` (route `/episodes/:id`)
- **Player:** play/pause, seek, current time and duration, **speed** (1, 1.25, 1.5, 2x), and a **chapter list** you can jump through.
- **Transcript:** lines color-coded by host, the **current line highlighted**, and auto-scroll.
- **Quiz:** one question at a time, 4 choices, then correct/incorrect feedback with the explanation, then a final score that links to review if anything was missed.
- **Generating states**, which are slow, so make them feel alive:
  - "Writing script…" takes **about 1–3 minutes**
  - "Recording audio…" takes about 1 minute
  - Showing the script while the audio records is fine.

### 5. `Episode / Rot mode` (rot ≥ 75)
- The same layout, with a **muted, looping 9:16 gameplay video** behind or beside the player (a YouTube embed, so design a frame for it and use a **placeholder**, not real game footage).
- Tung Tung Tung Sahur's transcript lines get their own loud style.
- Use an original placeholder for his avatar. **Don't copy fan art or game screenshots into the file.**

### 6. Shared states
Error toast or banner (for example "The AI service failed. Please try again."), loading skeletons and 404.

## Real data shapes (use realistic content, not lorem ipsum)
From `GET /api/courses/:id`:
```json
{"id": 1, "title": "BIOL 101", "options": {"length": 10, "depth": "intro", "voice_a": "Puck", "voice_b": "Kore", "rot": 0},
 "episodes": [{"id": 1, "kind": "lesson", "position": 1, "title": "How Life Began", "has_script": true, "has_audio": true},
              {"id": 3, "kind": "review", "position": 3, "title": "Review", "has_script": true, "has_audio": false}],
 "concepts": [{"id": 1, "name": "Abiogenesis", "box": 2, "due_at": "2026-11-02T10:00:00Z"}], "due_count": 1}
```
Here's a real generated transcript line, to give a sense of tone and length:
> **Sam:** I thought my screen failed to load. Are you telling me that an entire introductory lesson comes down to an exclamation you make when finding twenty dollars in an old coat?

The hosts are **Alex** (leads and explains) and **Sam** (the curious student). At rot ≥ 75, Sam is replaced by **Tung Tung Tung Sahur**. Quiz questions have 4 choices; lessons have about 5 questions and 3–5 chapters.

## Design system requirements
- Define **Figma variables**:
  - colors (light mode required; dark mode is a nice-to-have)
  - a type scale
  - spacing (a 4px base)
  - radii
  - a **rot accent** set
  These become CSS custom properties in `adea-frontend/src/styles.css`, so name them like CSS vars (`color/bg`, `color/host-a`, `space/4`…).
- **Build components with variants** that map 1:1 to the planned Vue components:
  - `UploadForm`, `CourseCard`, `ReviewCard`, `ConceptMastery`
  - `PodcastPlayer`, `Transcript`/`TranscriptLine` (host A, host B, Tung Sahur, active)
  - `Quiz` (unanswered, correct, incorrect, score)
  - `CourseChat`, `Button`, `Toast`
- The frontend is plain CSS with no UI library, so keep it buildable without heavy custom graphics. Native `<audio>` is controlled by a custom UI.
- **Accessibility:**
  - WCAG AA contrast, including the host colors on the transcript background
  - visible focus states on every component
  - minimum 44px touch targets
  - don't rely on color alone for correct/incorrect; add icons or text
- Use one font from Google Fonts. The old app used Poppins; you can change it.

## How to work (Figma MCP)
1. Load the Figma skills first: `/figma-use` (required before `use_figma`) and `/figma-generate-design`.
2. `create_new_file` → `create_session` with that file key → `search_design_system` to check for anything reusable.
3. Build in this order: **variables, then components, then screens**. Desktop first, then mobile.
4. Give the user a link and a short summary of your design decisions. Iterate on their feedback.

## Out of scope
- Writing frontend code, or changing the backend or API.
- Real Subway Surfers footage or screenshots, and copied Tung Sahur artwork. Use labeled placeholders.
- Accounts or login. The app is single-user.

## When you're done
Update the "Design" section of `docs/DEVELOPMENT.md` with the Figma file link. The frontend session will use `get_design_context` and `get_variable_defs` on your frames, so keep frame and component names exactly as listed above.
