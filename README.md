# Prompt Tester

Compare two prompt versions against the same input using the Gemini API — see both outputs side by side with token counts and latency.

## Prerequisites

- Python 3.10+
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

## Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. (Optional) Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Edit .env and replace 'your-key-here' with your real Gemini API key

# 5. Start the server
python main.py
```

Open **http://localhost:8000** in your browser.

## Architecture

```
prompt-tester/
├── ai-docs/                 # PRD and test artifacts
├── backend/
│   ├── main.py              # FastAPI app — routes + static file serving
│   ├── models.py            # Pydantic request/response schemas
│   ├── gemini_client.py     # Gemini API wrapper (google-genai SDK)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html           # Single-page UI
│   ├── style.css            # Dark-mode glassmorphism design
│   └── app.js               # Client-side fetch + rendering
├── README.md
└── .gitignore
```

## API Endpoints

| Method | Path            | Description                            |
| ------ | --------------- | -------------------------------------- |
| GET    | `/health`       | Liveness check → `{"status": "ok"}`    |
| POST   | `/api/compare`  | Run two prompts and return results     |

### `POST /api/compare` — Request

```json
{
  "prompt_a": "You are a concise assistant.",
  "prompt_b": "You are a verbose storyteller.",
  "test_input": "Explain photosynthesis.",
  "model": "gemini-3.5-flash",
  "use_system_instruction": true
}
```

### Response

```json
{
  "result_a": { "output": "...", "input_tokens": 12, "output_tokens": 45, "latency_ms": 820 },
  "result_b": { "output": "...", "input_tokens": 14, "output_tokens": 210, "latency_ms": 1340 }
}
```

## License

MIT
