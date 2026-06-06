"""Price normalization and OpenRouter listing parsing.

Implements the price rules from docs/methodology.md section 5:
- prices normalized to USD per 1,000,000 tokens ($/Mtok)
- blended price = (3*input + 1*output) / 4   (Epoch 3:1 input:output convention)
"""
from dataclasses import dataclass, asdict
from typing import Optional

TOKENS_PER_MILLION = 1_000_000


def per_token_to_per_mtok(per_token_usd: float) -> float:
    """Convert a per-token USD price to USD per 1M tokens."""
    return per_token_usd * TOKENS_PER_MILLION


def blended_price(
    input_mtok: float, output_mtok: float, w_input: int = 3, w_output: int = 1
) -> float:
    """Weighted blend of input and output $/Mtok prices.

    Default 3:1 reflects that typical workloads consume ~3x more input than
    output tokens (methodology section 5.2, parameter W_io).
    """
    return (w_input * input_mtok + w_output * output_mtok) / (w_input + w_output)


@dataclass
class Listing:
    """One (provider, model) price observation, normalized to $/Mtok."""

    provider: str
    model: str
    name: str
    input_mtok: float
    output_mtok: float
    blended_mtok: float
    context_length: Optional[int]
    observed_at: str
    source_type: str
    source_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_openrouter_model(raw: dict, observed_at: str) -> Optional[Listing]:
    """Parse one OpenRouter /models entry into a Listing.

    Returns None for entries that are not priced per-token text inference
    (missing pricing, or a free model with both prices zero) per the
    inclusion rules in methodology section 4.4.
    """
    pricing = raw.get("pricing")
    if not pricing:
        return None

    try:
        input_pt = float(pricing.get("prompt", 0) or 0)
        output_pt = float(pricing.get("completion", 0) or 0)
    except (TypeError, ValueError):
        return None

    # Negative prices are router/"variable pricing" sentinels, not real
    # listings (e.g. openrouter/auto quotes -1/token). Exclude them.
    if input_pt < 0 or output_pt < 0:
        return None

    # Free model (both zero) is not a priced listing.
    if input_pt == 0 and output_pt == 0:
        return None

    input_mtok = per_token_to_per_mtok(input_pt)
    output_mtok = per_token_to_per_mtok(output_pt)
    model_id = raw["id"]
    provider = model_id.split("/", 1)[0]

    return Listing(
        provider=provider,
        model=model_id,
        name=raw.get("name", model_id),
        input_mtok=input_mtok,
        output_mtok=output_mtok,
        blended_mtok=blended_price(input_mtok, output_mtok),
        context_length=raw.get("context_length"),
        observed_at=observed_at,
        source_type="host",  # OpenRouter aggregates/hosts; see methodology 4.1
        source_url="https://openrouter.ai/api/v1/models",
    )
