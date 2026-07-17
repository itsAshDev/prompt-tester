# PRD: Prompt A/B Diff Tester

**Project type:** AI sprint project (1–2 hr build)
**Status:** Draft — source of truth for implementation
**Stack:** Python (FastAPI) backend, HTML/JS frontend, Google Gemini API

---

## 1. Problem Statement

Prompt engineers routinely tweak prompts and eyeball 2–3 outputs to judge whether a change helped — there's no systematic, fast way to compare two prompt versions against the same input and see the difference side by side. This tool solves that: paste two prompt versions, run them against one test input, see both outputs immediately.

## 2. Goal

Ship a working tool where a user can:

1. Enter Prompt A and Prompt B (system or full prompt text).
2. Enter one test input/user message.
3. Click "Compare".
4. See both model outputs rendered side by side, plus basic diff metadata (token count, word count, latency).

Out of scope for v1 (explicitly not building): auth, persistence/database, multi-turn conversations, batch testing, LLM-as-judge scoring, user accounts.

## 3. Success Criteria (Definition of Done)

- [ ] User can submit two prompts + one input via a single form.
- [ ] Backend calls the Gemini API twice (once per prompt) with the same input.
- [ ] Both responses render in a side-by-side (or stacked-on-mobile) layout.
- [ ] Each output shows: response text, token count (input/output), latency in ms.
- [ ] Errors (bad API key, rate limit, empty fields) show a user-visible message, not a silent failure or stack trace.
- [ ] Runs locally with a documented setup (`.env.example`, `requirements.txt`, README with run steps).

## 4. Architecture

```
prompt-ab-tester/
├── backend/
│   ├── main.py              # FastAPI app, routes
│   ├── models.py            # Pydantic request/response schemas
│   ├── gemini_client.py     # Gemini API wrapper
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── README.md
└── .gitignore
```

FastAPI serves the static frontend directly (no separate frontend server) to keep the sprint scope tight. `app.js` calls the backend via `fetch`.

## 5. API Contract

### `POST /api/compare`

**Request body:**

```json
{
  "prompt_a": "string, required",
  "prompt_b": "string, required",
  "test_input": "string, required",
  "model": "string, optional, default: gemini-2.5-flash"
}
```

**Response body:**

```json
{
  "result_a": {
    "output": "string",
    "input_tokens": 0,
    "output_tokens": 0,
    "latency_ms": 0
  },
  "result_b": {
    "output": "string",
    "input_tokens": 0,
    "output_tokens": 0,
    "latency_ms": 0
  }
}
```

**Error response (4xx/5xx):**

```json
{ "error": "human-readable message" }
```

### `GET /health`

Returns `{ "status": "ok" }` — used to confirm the server is running.

## 6. Frontend Requirements

- Single page, one form with three text areas: Prompt A, Prompt B, Test Input.
- One "Compare" button, disabled while a request is in flight, with a loading state.
- Results area: two columns (stack vertically below a breakpoint) showing output text and metadata (tokens, latency) per side.
- Minimal styling is fine — clarity over polish for v1.

## 7. Environment & Config

`.env` (not committed — see `.gitignore`):

```
GOOGLE_API_KEY=AIza...
```

`.env.example` (committed, no real key):

```
GOOGLE_API_KEY=your-key-here
```

## 8. Version Control Strategy

- `main` branch is always deployable/demoable.
- Feature branches: `feat/<short-description>` (e.g. `feat/compare-endpoint`, `feat/results-ui`).
- Commit convention: [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `chore:`, `docs:`.
- Suggested commit sequence for this sprint:
  1. `chore: scaffold FastAPI app + static file serving`
  2. `feat: add /api/compare endpoint with Gemini client`
  3. `feat: add frontend form and results rendering`
  4. `feat: add error handling and loading states`
  5. `docs: add README with setup instructions`
- No direct commits to `main` once the first feature branch is opened — PR (even self-reviewed) merges only.

## 9. Non-Functional Requirements

- API key must never be exposed to the frontend/client — all Gemini calls happen server-side.
- Timeout on Gemini calls (suggest 30s) with a clear error if exceeded.
- CORS: not needed if frontend is served by the same FastAPI app; add permissive CORS only if frontend is split out later.

## 10. Stretch Goals (only if time remains)

- Run each prompt N times and show variance (consistency check).
- Simple heuristic diff highlighting (word-level diff between outputs).
- "Judge" mode: a third Gemini call scores which output better followed the test input.
- Save comparisons to a local JSON file or SQLite for session history.

## 11. Open Questions

- Which Gemini model should be the default? (Suggest `gemini-2.5-flash` for speed/cost during the sprint; swap to `gemini-2.5-pro` if quality matters more than latency — confirm current model names against Google's docs before building, as these change.)
- Should Prompt A/B be treated as system instructions (`system_instruction` param) or as part of the user turn? (Recommend: user-selectable toggle, default to `system_instruction` for both.)
- Which SDK: the newer `google-genai` package or the older `google-generativeai`? (Recommend `google-genai` — it's Google's current unified SDK; confirm it's still the recommended package before building.)

---

_This document is the single source of truth for scope during the sprint. Changes to scope should be reflected here first, then implemented._
