"""Prompt A/B Diff Tester — FastAPI backend."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from gemini_client import _create_client, generate, generate_judge
from models import CompareRequest, CompareResponse, ErrorResponse, ResultItem, VarianceSummary, JudgeVerdict, PromptSaveRequest
from db import init_db, save_comparison, get_history, save_prompt, list_prompts, get_prompt_version

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
    """Initialise the Gemini client and SQLite DB once on startup."""
    global gemini_client
    init_db()  # Initialize SQLite schema and folder automatically
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
# Helpers
# ---------------------------------------------------------------------------


def _compute_variance(results: list[ResultItem]) -> VarianceSummary:
    """Compute variance summary across a list of ResultItem runs."""
    lengths = [len(r.output) for r in results]
    outputs = [r.output for r in results]
    return VarianceSummary(
        run_count=len(results),
        output_length_min=min(lengths),
        output_length_max=max(lengths),
        output_length_range=max(lengths) - min(lengths),
        outputs_identical=len(set(outputs)) == 1,
        total_cost=sum(r.estimated_cost for r in results),
    )


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
async def compare(req: CompareRequest, background_tasks: BackgroundTasks):
    """Run the same input against two prompts and return both results."""

    if gemini_client is None:
        return JSONResponse(
            status_code=500,
            content={"error": "Server misconfigured — GOOGLE_API_KEY is not set."},
        )

    try:
        # Fan out N runs per prompt concurrently
        all_tasks = []
        for _i in range(req.runs):
            all_tasks.append(
                generate(
                    gemini_client,
                    req.prompt_a,
                    req.test_input,
                    req.model,
                    req.use_system_instruction,
                )
            )
        for _i in range(req.runs):
            all_tasks.append(
                generate(
                    gemini_client,
                    req.prompt_b,
                    req.test_input,
                    req.model,
                    req.use_system_instruction,
                )
            )

        all_results = await asyncio.wait_for(
            asyncio.gather(*all_tasks),
            timeout=GEMINI_TIMEOUT_S * req.runs,
        )

        results_a = list(all_results[: req.runs])
        results_b = list(all_results[req.runs :])

    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": f"Gemini API call timed out after {GEMINI_TIMEOUT_S * req.runs}s. Try again or use a faster model."
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

    # Build response — backward-compatible when runs=1
    response = CompareResponse(
        result_a=results_a[0],
        result_b=results_b[0],
    )

    if req.runs > 1:
        response.runs_a = results_a
        response.runs_b = results_b
        response.variance_a = _compute_variance(results_a)
        response.variance_b = _compute_variance(results_b)

    if req.enable_judge:
        try:
            verdict = await generate_judge(
                gemini_client,
                req.test_input,
                results_a[0].output,
                results_b[0].output,
                req.model,
            )
            response.judge_verdict = verdict
        except Exception as judge_exc:
            print(f"⚠️  LLM Judge call failed: {judge_exc}")
            response.judge_verdict = JudgeVerdict(
                choice="Tie",
                reasoning=f"LLM Judge call failed: {judge_exc}"
            )

    background_tasks.add_task(save_comparison, req.model_dump(), response.model_dump())
    return response


@app.get("/api/history")
async def history(page: int = 1, limit: int = 20):
    """Retrieve comparisons history, paginated."""
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 20
    return await get_history(page, limit)


@app.post("/api/prompts")
async def create_prompt(req: PromptSaveRequest):
    """Save a prompt template version."""
    try:
        name = req.name.strip()
        if not name:
            return JSONResponse(status_code=400, content={"error": "Prompt name cannot be empty."})
        result = await save_prompt(name, req.text)
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/prompts")
async def get_prompts():
    """List all saved prompts (names and versions)."""
    return await list_prompts()


@app.get("/api/prompts/{name}/{version}")
async def get_prompt_by_version(name: str, version: int):
    """Get a specific version of a prompt."""
    result = await get_prompt_version(name, version)
    if not result:
        return JSONResponse(status_code=404, content={"error": f"Prompt '{name}' (version {version}) not found."})
    return result


# ---------------------------------------------------------------------------
# Pydantic validation error handler
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return a simpler error message for validation errors."""
    errors = exc.errors()
    for err in errors:
        loc = err.get("loc", [])
        if "runs" in loc:
            return JSONResponse(
                status_code=400,
                content={"error": "Runs must be an integer between 1 and 5."},
            )
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
