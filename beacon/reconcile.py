"""Cross-source price reconciliation — multi-source robustness for the rate.

A single price source is both a point of failure and a manipulation surface. This
module combines listings from several independent sources into one reconciled price
per model: the **median** across sources (so no single source can swing it once ≥3
agree), plus a provenance + dispersion record so the index can prefer well-corroborated
models and flag disagreements.

Pure functions only — no network. The collector fetches each source; this combines them.
"""
import re
import statistics
from typing import Dict, List, Sequence

# If sources disagree by more than this fraction of the median, flag the model
# `disputed` so downstream logic can treat it with caution (methodology 4.5).
DEFAULT_MAX_SPREAD_RATIO = 0.25


def canonical_key(model: str) -> str:
    """Normalize a model identifier for cross-source matching.

    Lowercase; drop a trailing ``:variant`` suffix (e.g. ``:free``); turn ``. _ space``
    into ``-``; keep only ``[a-z0-9/-]``; collapse repeated/edge dashes. Keeps an
    optional ``vendor/slug`` shape so ``OpenAI/GPT-4o`` and ``openai/gpt-4o`` match.
    """
    s = model.strip().lower()
    s = s.split(":", 1)[0]  # strip ":free" / ":beta" style variant suffixes
    s = re.sub(r"[._ ]+", "-", s)
    s = re.sub(r"[^a-z0-9/-]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def reconcile_listings(
    listings: Sequence[dict],
    primary: str = "openrouter",
    max_spread_ratio: float = DEFAULT_MAX_SPREAD_RATIO,
) -> List[dict]:
    """Combine listings from multiple sources into one reconciled listing per model.

    Listings are grouped by :func:`canonical_key` of their ``model``. Each group's
    price fields become the **median** across sources. The representative identity
    (``model``/``provider``/``name``) is taken from the ``primary`` source when present
    (so the downstream benchmark join — keyed on the OpenRouter model id — still
    matches), otherwise from the first listing in the group.

    Each reconciled listing gains: ``sources`` (sorted unique), ``n_sources``,
    ``source_spread_ratio`` ((max-min)/median of blended price), and ``disputed``.
    """
    groups: Dict[str, List[dict]] = {}
    for ls in listings:
        groups.setdefault(canonical_key(ls["model"]), []).append(ls)

    out: List[dict] = []
    for _key, group in groups.items():
        # Collapse each source to ONE vote (the median over its hosts) before combining,
        # so a source's host count can't dominate and one bad host can't blow it up.
        by_source: Dict[str, List[dict]] = {}
        for ls in group:
            by_source.setdefault(ls.get("source", "?"), []).append(ls)

        def _src_median(src_listings, field):
            return statistics.median([ls[field] for ls in src_listings])

        per_source_blended = [_src_median(v, "blended_mtok") for v in by_source.values()]
        median_blended = statistics.median(per_source_blended)
        spread = (
            (max(per_source_blended) - min(per_source_blended)) / median_blended
            if median_blended else 0.0
        )
        sources = sorted(by_source)

        rep = next((ls for ls in group if ls.get("source") == primary), group[0])
        reconciled = dict(rep)  # keep the representative identity + any extra fields
        reconciled["input_mtok"] = statistics.median(
            [_src_median(v, "input_mtok") for v in by_source.values()])
        reconciled["output_mtok"] = statistics.median(
            [_src_median(v, "output_mtok") for v in by_source.values()])
        reconciled["blended_mtok"] = median_blended
        reconciled["sources"] = sources
        reconciled["n_sources"] = len(sources)
        reconciled["source_spread_ratio"] = spread
        reconciled["disputed"] = spread > max_spread_ratio
        reconciled.pop("source", None)  # superseded by `sources`
        out.append(reconciled)
    return out
