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
    source: str = "openrouter"  # which price source produced this listing

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
        source="openrouter",
    )


def parse_modelsdev_payload(payload: dict, observed_at: str) -> "list[Listing]":
    """Parse the models.dev /api.json payload into Listings (a second price source).

    Shape: ``{provider_id: {name, models: {model_id: {id, name, cost: {input, output}}}}}``.
    Unlike OpenRouter, models.dev quotes ``cost.input``/``cost.output`` already in
    USD per 1M tokens, so no per-token conversion. Free/unpriced models are dropped.
    """
    out = []
    for _provider_id, prov in payload.items():
        models = prov.get("models") if isinstance(prov, dict) else None
        if not isinstance(models, dict):
            continue
        for model_id, m in models.items():
            cost = m.get("cost") if isinstance(m, dict) else None
            if not isinstance(cost, dict):
                continue
            try:
                input_mtok = float(cost.get("input", 0) or 0)
                output_mtok = float(cost.get("output", 0) or 0)
            except (TypeError, ValueError):
                continue
            if input_mtok < 0 or output_mtok < 0:
                continue
            if input_mtok == 0 and output_mtok == 0:
                continue
            mid = m.get("id", model_id)
            provider = mid.split("/", 1)[0] if "/" in mid else _provider_id
            out.append(Listing(
                provider=provider,
                model=mid,
                name=m.get("name", mid),
                input_mtok=input_mtok,
                output_mtok=output_mtok,
                blended_mtok=blended_price(input_mtok, output_mtok),
                context_length=(m.get("limit") or {}).get("context") if isinstance(m.get("limit"), dict) else None,
                observed_at=observed_at,
                source_type="host",
                source_url="https://models.dev/api.json",
                source="models.dev",
            ))
    return out
