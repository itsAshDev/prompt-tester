"""Static Gemini pricing table and cost estimation helper.

Rates are in USD per 1 million tokens, sourced from Google's published
pricing (July 2026). Update entries here when Google revises rates or
when new models are added.
"""

import logging

logger = logging.getLogger(__name__)

# {model_id: {"input_per_1m": USD, "output_per_1m": USD}}
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-3.5-flash": {
        "input_per_1m": 1.50,
        "output_per_1m": 9.00,
    },
    "gemini-2.5-flash": {
        "input_per_1m": 0.30,
        "output_per_1m": 2.50,
    },
    "gemini-3.1-flash-lite": {
        "input_per_1m": 0.25,
        "output_per_1m": 1.50,
    },
    "gemini-2.0-flash-lite": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
    },
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for the given token counts and model.

    Returns 0.0 (with a warning) if the model is not in the pricing table.
    """
    rates = GEMINI_PRICING.get(model)
    if rates is None:
        logger.warning("No pricing data for model '%s'; returning $0.00", model)
        return 0.0

    input_cost = input_tokens * rates["input_per_1m"] / 1_000_000
    output_cost = output_tokens * rates["output_per_1m"] / 1_000_000
    return input_cost + output_cost
