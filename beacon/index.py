"""Capability-normalized index construction (methodology section 7).

Three families of indices:
- iso-quality : cheapest price to achieve a fixed capability tier
- frontier    : iso-quality applied to the top tier (a stable-ish "level")
- spread      : P90/P10 price dispersion among same-capability listings

All inputs are blended $/Mtok prices (see beacon.pricing).
"""
from typing import List, Optional, Sequence, Tuple

# Methodology section 8.3: a price more than this fraction below the
# next-cheapest qualifying listing is quarantined as a probable error.
OUTLIER_DROP_FRACTION = 0.5


def percentile(values: Sequence[float], p: float) -> float:
    """The p-th percentile (0..100) via linear interpolation between ranks."""
    if not values:
        raise ValueError("percentile() requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    frac = rank - lo
    if lo + 1 >= len(ordered):
        return float(ordered[lo])
    return ordered[lo] + frac * (ordered[lo + 1] - ordered[lo])


def spread(prices: Sequence[float]) -> float:
    """Cross-provider dispersion = P90 / P10 (methodology 7.3)."""
    p10 = percentile(prices, 10)
    p90 = percentile(prices, 90)
    return p90 / p10


def robust_min_price(prices: Sequence[float]) -> float:
    """Minimum price after dropping extreme-low outliers (methodology 8.3).

    Repeatedly discards the cheapest value while it is more than
    OUTLIER_DROP_FRACTION below the next-cheapest, then returns the minimum
    of what remains.
    """
    if not prices:
        raise ValueError("robust_min_price() requires at least one price")
    ordered = sorted(prices)
    while len(ordered) >= 2 and ordered[0] < (1 - OUTLIER_DROP_FRACTION) * ordered[1]:
        ordered.pop(0)
    return ordered[0]


def iso_quality(
    listings_scores: Sequence[Tuple[float, float]], threshold: float
) -> Optional[float]:
    """Cheapest (outlier-guarded) blended price among listings meeting a tier.

    listings_scores: sequence of (blended_mtok, capability_score).
    Returns None if no listing meets the threshold.
    """
    qualifying = [price for price, score in listings_scores if score >= threshold]
    if not qualifying:
        return None
    return robust_min_price(qualifying)


def index_value(value: float, base: float) -> float:
    """Normalize a level to an index that equals 100 at the base value."""
    return 100.0 * value / base
