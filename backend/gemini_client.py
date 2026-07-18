"""Thin wrapper around the google-genai SDK for Gemini API calls."""

import asyncio
import logging
import re
import time

from google import genai
from google.genai import types

from models import JudgeVerdict, ResultItem
from pricing import estimate_cost

logger = logging.getLogger(__name__)

_sem: asyncio.Semaphore = None


def get_semaphore() -> asyncio.Semaphore:
    """Get the global concurrency semaphore for Gemini calls."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(2)  # Cap concurrent calls at 2
    return _sem


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

    cost = estimate_cost(model, input_tokens, output_tokens)

    return ResultItem(
        output=response.text or "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=elapsed_ms,
        estimated_cost=cost,
    )


async def _generate_with_semaphore(
    client: genai.Client,
    prompt: str,
    user_input: str,
    model: str,
    use_system_instruction: bool,
) -> ResultItem:
    """Acquire concurrency semaphore and run the API call."""
    sem = get_semaphore()
    async with sem:
        return await asyncio.to_thread(
            _generate_sync,
            client,
            prompt,
            user_input,
            model,
            use_system_instruction,
        )


async def generate(
    client: genai.Client,
    prompt: str,
    user_input: str,
    model: str,
    use_system_instruction: bool,
    retries_left: int = 2,
) -> ResultItem:
    """Async wrapper with retry-on-429 logic. Releases semaphore before sleeping."""
    try:
        return await _generate_with_semaphore(
            client,
            prompt,
            user_input,
            model,
            use_system_instruction,
        )
    except Exception as exc:
        exc_str = str(exc)
        if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
            if retries_left > 0:
                # Try to parse retryDelay (e.g. 'retryDelay': '22s' or similar)
                match = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", exc_str)
                delay = 5.0  # default fallback delay
                if match:
                    try:
                        delay = float(match.group(1))
                    except ValueError:
                        pass
                logger.warning(
                    "Encountered 429 rate limit. Waiting for %s seconds before retry. Retries left: %d",
                    delay,
                    retries_left,
                )
                await asyncio.sleep(delay)
                return await generate(
                    client,
                    prompt,
                    user_input,
                    model,
                    use_system_instruction,
                    retries_left=retries_left - 1,
                )
        raise exc


JUDGE_SYSTEM_INSTRUCTION = (
    "You are an objective AI judge. Your task is to evaluate two candidate outputs (Output A and Output B) "
    "generated in response to a given user test input.\n\n"
    "Evaluate which output is better based on correctness, helpfulness, formatting, tone, and adherence "
    "to any instructions implied by the test input. You must output a structured JSON response specifying "
    "the choice ('A', 'B', or 'Tie') and a concise reasoning explaining your decision."
)


def _generate_judge_sync(
    client: genai.Client,
    test_input: str,
    output_a: str,
    output_b: str,
    model: str,
) -> JudgeVerdict:
    """Run a single structured Gemini generation to act as a judge comparing A and B."""
    contents = (
        f"User Test Input:\n\"\"\"{test_input}\"\"\"\n\n"
        f"Candidate Output A:\n\"\"\"{output_a}\"\"\"\n\n"
        f"Candidate Output B:\n\"\"\"{output_b}\"\"\"\n\n"
        f"Compare Output A and Output B and provide your structured verdict."
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=JudgeVerdict,
        ),
    )

    import json
    try:
        data = json.loads(response.text)
        return JudgeVerdict(**data)
    except Exception as e:
        logger.error("Failed to parse judge output JSON: %s. Raw text: %s", e, response.text)
        return JudgeVerdict(
            choice="Tie",
            reasoning=f"Failed to parse judge response: {response.text}"
        )


async def _generate_judge_with_semaphore(
    client: genai.Client,
    test_input: str,
    output_a: str,
    output_b: str,
    model: str,
) -> JudgeVerdict:
    """Acquire concurrency semaphore and run the API call for the judge."""
    sem = get_semaphore()
    async with sem:
        return await asyncio.to_thread(
            _generate_judge_sync,
            client,
            test_input,
            output_a,
            output_b,
            model,
        )


async def generate_judge(
    client: genai.Client,
    test_input: str,
    output_a: str,
    output_b: str,
    model: str,
    retries_left: int = 2,
) -> JudgeVerdict:
    """Async wrapper for the judge model call with retry-on-429 logic. Releases semaphore before sleeping."""
    try:
        return await _generate_judge_with_semaphore(
            client,
            test_input,
            output_a,
            output_b,
            model,
        )
    except Exception as exc:
        exc_str = str(exc)
        if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
            if retries_left > 0:
                # Try to parse retryDelay (e.g. 'retryDelay': '22s' or similar)
                match = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", exc_str)
                delay = 5.0  # default fallback delay
                if match:
                    try:
                        delay = float(match.group(1))
                    except ValueError:
                        pass
                logger.warning(
                    "Judge call encountered 429 rate limit. Waiting for %s seconds before retry. Retries left: %d",
                    delay,
                    retries_left,
                )
                await asyncio.sleep(delay)
                return await generate_judge(
                    client,
                    test_input,
                    output_a,
                    output_b,
                    model,
                    retries_left=retries_left - 1,
                )
        raise exc
