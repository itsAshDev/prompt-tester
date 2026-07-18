from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """Request body for POST /api/compare."""

    prompt_a: str = Field(..., min_length=1, description="First prompt variant")
    prompt_b: str = Field(..., min_length=1, description="Second prompt variant")
    test_input: str = Field(..., min_length=1, description="User message / test input")
    model: str = Field(
        default="gemini-3.5-flash",
        description="Gemini model identifier",
    )
    use_system_instruction: bool = Field(
        default=True,
        description="If True, send prompts as system_instruction; otherwise as part of the user turn",
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


class CompareResponse(BaseModel):
    """Successful response for POST /api/compare."""

    result_a: ResultItem
    result_b: ResultItem


class ErrorResponse(BaseModel):
    """Error response envelope."""

    error: str
