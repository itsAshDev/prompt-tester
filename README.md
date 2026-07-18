# Prompt Tester

Compare two prompt versions against the same input using the Gemini API — see both outputs side by side with token counts, latency, cost estimation, consistency checks, word-level diffs, and LLM-as-judge scoring.

## Features (Phase 1 Completed)

*   **Cost Display**: Post-call cost badges indicating the USD cost of each run based on model token counts.
*   **Consistency & Variance Testing**: Run the same comparison 1–5 times concurrently to measure performance and token/length variance.
*   **API Rate Limit Protection**: Features a concurrency cap (maximum 2 parallel API calls) and automatic retry with dynamic backoff on `429` / `RESOURCE_EXHAUSTED` responses.
*   **Word-Level Diff Highlighting**: View color-coded additions (green) and deletions (red) in outputs side by side. Handles multi-run selections dynamically.
*   **LLM-as-Judge Mode**: Runs a structured third Gemini call to analyze and choose which candidate output better fits the test input, detailing its reasoning.

---

## Prerequisites

- Python 3.10+
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

## Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. (Optional) Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Edit .env and replace 'your-key-here' with your real Gemini API key

# 5. Start the server
python3 main.py
```

Open **http://localhost:8000** in your browser.

---

## Architecture

```
prompt-tester/
├── ai-docs/                 # PRD and test artifacts
├── backend/
│   ├── main.py              # FastAPI app — routes + static file serving
│   ├── models.py            # Pydantic request/response schemas
│   ├── gemini_client.py     # Gemini API wrapper (google-genai SDK, concurrency & retry)
│   ├── pricing.py           # Model pricing configurations
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html           # Single-page UI with diff toggles and judge verdict card
│   ├── style.css            # Dark-mode glassmorphism design
│   └── app.js               # Client-side diff highlighting, runs selection, and rendering
├── README.md
└── .gitignore
```

---

## API Endpoints

| Method | Path            | Description                            |
| ------ | --------------- | -------------------------------------- |
| GET    | `/health`       | Liveness check → `{"status": "ok"}`    |
| POST   | `/api/compare`  | Run comparisons and optionally score   |

### `POST /api/compare` — Request

```json
{
  "prompt_a": "be concise",
  "prompt_b": "be verbose",
  "test_input": "what is gravity",
  "model": "gemini-3.1-flash-lite",
  "use_system_instruction": true,
  "runs": 3,
  "enable_judge": true
}
```

### Response

```json
{
  "result_a": {
    "output": "Gravity is the force...",
    "input_tokens": 7,
    "output_tokens": 85,
    "latency_ms": 1396,
    "estimated_cost": 0.00012925
  },
  "result_b": {
    "output": "To understand gravity...",
    "input_tokens": 7,
    "output_tokens": 1089,
    "latency_ms": 5054,
    "estimated_cost": 0.00163525
  },
  "runs_a": [
    { "output": "...", "input_tokens": 7, "output_tokens": 85, "latency_ms": 1396, "estimated_cost": 0.00012925 }
  ],
  "runs_b": [
    { "output": "...", "input_tokens": 7, "output_tokens": 1089, "latency_ms": 5054, "estimated_cost": 0.00163525 }
  ],
  "variance_a": {
    "run_count": 3,
    "output_length_min": 85,
    "output_length_max": 85,
    "output_length_range": 0,
    "outputs_identical": true,
    "total_cost": 0.00038775
  },
  "variance_b": {
    "run_count": 3,
    "output_length_min": 1089,
    "output_length_max": 1089,
    "output_length_range": 0,
    "outputs_identical": true,
    "total_cost": 0.00490575
  },
  "judge_verdict": {
    "choice": "B",
    "reasoning": "Output B provides a much more comprehensive, engaging, and well-structured explanation..."
  }
}
```

## License

MIT
