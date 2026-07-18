from typing import Optional

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """Request body for POST /api/compare."""

    prompt_a: str = Field(..., min_length=1, description="First prompt variant")
    prompt_b: str = Field(..., min_length=1, description="Second prompt variant")
    test_input: str = Field(..., min_length=1, description="User message / test input")
    model: str = Field(
        default="gemini-3.1-flash-lite",
        description="Gemini model identifier",
    )
    use_system_instruction: bool = Field(
        default=True,
        description="If True, send prompts as system_instruction; otherwise as part of the user turn",
    )
    runs: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of runs per prompt (1–5) for consistency testing",
    )
    enable_judge: bool = Field(
        default=False,
        description="If True, execute an optional third Gemini call to act as an LLM judge scoring both outputs",
    )


class ResultItem(BaseModel):
    """Output metadata for a single prompt run."""

    output: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost: float = Field(
        ..., description="Estimated cost in USD based on token counts and model pricing"
    )


class VarianceSummary(BaseModel):
    """Variance metrics across multiple runs of the same prompt."""

    run_count: int
    output_length_min: int = Field(..., description="Shortest output in characters")
    output_length_max: int = Field(..., description="Longest output in characters")
    output_length_range: int = Field(..., description="Max - min output length")
    outputs_identical: bool = Field(..., description="True if all outputs are exactly the same")
    total_cost: float = Field(..., description="Sum of estimated_cost across all runs")


class JudgeVerdict(BaseModel):
    """Structured verdict from the LLM judge."""

    choice: str = Field(..., description="Which output is better: 'A', 'B', or 'Tie'")
    reasoning: str = Field(..., description="Explanation of why this choice was made")


class CompareResponse(BaseModel):
    """Successful response for POST /api/compare."""

    result_a: ResultItem
    result_b: ResultItem
    # Multi-run fields (None when runs=1 for backward compatibility)
    runs_a: Optional[list[ResultItem]] = None
    runs_b: Optional[list[ResultItem]] = None
    variance_a: Optional[VarianceSummary] = None
    variance_b: Optional[VarianceSummary] = None
    judge_verdict: Optional[JudgeVerdict] = None


class ErrorResponse(BaseModel):
    """Error response envelope."""

    error: str

