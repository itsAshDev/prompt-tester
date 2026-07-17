"""Thin wrapper around the google-genai SDK for Gemini API calls."""

import asyncio
import time

from google import genai
from google.genai import types

from models import ResultItem


def _create_client(api_key: str) -> genai.Client:
    """Create a Gemini client with the given API key."""
    return genai.Client(api_key=api_key)


def _generate_sync(
    client: genai.Client,
    prompt: str,
    user_input: str,
    model: str,
    use_system_instruction: bool,
) -> ResultItem:
    """Run a single synchronous Gemini generation and return a ResultItem."""
    start = time.perf_counter()

    if use_system_instruction:
        config = types.GenerateContentConfig(system_instruction=prompt)
        contents = user_input
    else:
        # Concatenate prompt and user input into a single user message
        contents = f"{prompt}\n\n{user_input}"
        config = types.GenerateContentConfig()

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Extract token counts from usage metadata
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count or 0 if usage else 0
    output_tokens = usage.candidates_token_count or 0 if usage else 0

    return ResultItem(
        output=response.text or "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=elapsed_ms,
    )


async def generate(
    client: genai.Client,
    prompt: str,
    user_input: str,
    model: str,
    use_system_instruction: bool,
) -> ResultItem:
    """Async wrapper — runs the blocking SDK call in a thread pool."""
    return await asyncio.to_thread(
        _generate_sync,
        client,
        prompt,
        user_input,
        model,
        use_system_instruction,
    )
