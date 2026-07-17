"""Prompt A/B Diff Tester — FastAPI backend."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from gemini_client import _create_client, generate
from models import CompareRequest, CompareResponse, ErrorResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_TIMEOUT_S = 30  # per-call timeout

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

gemini_client = None  # will be set on startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the Gemini client once on startup."""
    global gemini_client
    if not GOOGLE_API_KEY:
        print(
            "⚠️  GOOGLE_API_KEY is not set. "
            "Requests to /api/compare will fail until a valid key is provided in .env"
        )
    else:
        gemini_client = _create_client(GOOGLE_API_KEY)
        print("✅ Gemini client initialised")
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Prompt A/B Diff Tester", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Simple liveness check."""
    return {"status": "ok"}


@app.post(
    "/api/compare",
    response_model=CompareResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def compare(req: CompareRequest):
    """Run the same input against two prompts and return both results."""

    if gemini_client is None:
        return JSONResponse(
            status_code=500,
            content={"error": "Server misconfigured — GOOGLE_API_KEY is not set."},
        )

    try:
        result_a, result_b = await asyncio.wait_for(
            asyncio.gather(
                generate(
                    gemini_client,
                    req.prompt_a,
                    req.test_input,
                    req.model,
                    req.use_system_instruction,
                ),
                generate(
                    gemini_client,
                    req.prompt_b,
                    req.test_input,
                    req.model,
                    req.use_system_instruction,
                ),
            ),
            timeout=GEMINI_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": f"Gemini API call timed out after {GEMINI_TIMEOUT_S}s. Try again or use a faster model."
            },
        )
    except Exception as exc:
        # Surface API errors (auth, rate-limit, etc.) as readable messages
        msg = str(exc)
        if "API_KEY" in msg.upper() or "PERMISSION" in msg.upper():
            status = 401
        elif "RATE" in msg.upper() or "QUOTA" in msg.upper():
            status = 429
        else:
            status = 500
        return JSONResponse(status_code=status, content={"error": msg})

    return CompareResponse(result_a=result_a, result_b=result_b)


# ---------------------------------------------------------------------------
# Pydantic validation error handler
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return a simpler error message for validation errors."""
    return JSONResponse(
        status_code=400,
        content={"error": "All fields (prompt_a, prompt_b, test_input) are required and must be non-empty."},
    )


# ---------------------------------------------------------------------------
# Static files — serve the frontend
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
