"""Collect LLM inference prices from multiple sources and persist daily snapshots.

Sources (both public, no API key):
  - OpenRouter /models  — per-token input/output prices across ~300 models.
  - models.dev /api.json — model+pricing map ($/Mtok) across ~140 providers.

Prices are reconciled across sources into one robust value per model (cross-source
median + a `disputed` flag when sources disagree) so the rate has no single point of
failure or manipulation — see beacon.reconcile. A source failing never aborts the run.

  python3 -m beacon.collector            # fetch all sources + write today's snapshot

The pure assembly (build_snapshot, build_snapshot_from_listings) and persistence
(write_snapshot) are unit-tested; only the fetch_* functions touch the network.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from beacon import pricing, reconcile

METHODOLOGY_VERSION = "0.1"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELSDEV_URL = "https://models.dev/api.json"
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def build_snapshot(raw_models: List[dict], observed_at: str) -> dict:
    """Assemble a snapshot dict from raw OpenRouter model entries.

    Free/unpriced models are dropped per the inclusion rules (methodology 4.4).
    """
    listings = []
    for raw in raw_models:
        listing = pricing.parse_openrouter_model(raw, observed_at=observed_at)
        if listing is not None:
            listings.append(listing.to_dict())

    return {
        "observed_at": observed_at,
        "source": "openrouter",
        "methodology_version": METHODOLOGY_VERSION,
        "listing_count": len(listings),
        "listings": listings,
    }


def build_snapshot_from_listings(
    listings_by_source: dict, observed_at: str, methodology_version: str = METHODOLOGY_VERSION
) -> dict:
    """Assemble a multi-source snapshot: reconcile listings across sources into one
    robust price per model (cross-source median + provenance). Degrades gracefully —
    with a single source it's a passthrough (n_sources=1). Empty/failed sources are
    simply absent from `sources`.
    """
    all_listings = [ls for src in listings_by_source.values() for ls in src]
    reconciled = reconcile.reconcile_listings(all_listings)
    reconciled.sort(key=lambda r: r["model"])  # deterministic order for stable diffs
    sources = sorted(s for s, ls in listings_by_source.items() if ls)
    return {
        "observed_at": observed_at,
        "source": "multi" if len(sources) > 1 else (sources[0] if sources else "none"),
        "sources": sources,
        "methodology_version": methodology_version,
        "listing_count": len(reconciled),
        "multi_source_count": sum(1 for r in reconciled if r["n_sources"] >= 2),
        "disputed_count": sum(1 for r in reconciled if r["disputed"]),
        "listings": reconciled,
    }


def write_snapshot(snapshot: dict, out_dir=DEFAULT_SNAPSHOT_DIR) -> str:
    """Write a snapshot to <out_dir>/<observed_at>.json and return the path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snapshot['observed_at']}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    return str(path)


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "beacon-collector/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_openrouter(url: str = OPENROUTER_MODELS_URL, timeout: int = 30) -> List[dict]:
    """Fetch the live OpenRouter model list (network)."""
    return _get_json(url, timeout)["data"]


def fetch_modelsdev(url: str = MODELSDEV_URL, timeout: int = 30) -> dict:
    """Fetch the live models.dev model+pricing map (network)."""
    return _get_json(url, timeout)


def main() -> int:
    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Collecting inference prices from all sources ({observed_at})...")

    # Each source is fetched independently; a single source failing must NOT break
    # the run — that's the whole point of multi-source (no single point of failure).
    by_source: dict = {}
    try:
        raw = fetch_openrouter()
        by_source["openrouter"] = [
            ls.to_dict() for ls in (
                pricing.parse_openrouter_model(m, observed_at=observed_at) for m in raw
            ) if ls is not None
        ]
        print(f"  openrouter: {len(by_source['openrouter'])} priced listings")
    except Exception as e:  # noqa: BLE001 — never let one source abort the run
        print(f"  openrouter: FAILED ({e})")
    try:
        payload = fetch_modelsdev()
        by_source["models.dev"] = [ls.to_dict() for ls in pricing.parse_modelsdev_payload(payload, observed_at)]
        print(f"  models.dev: {len(by_source['models.dev'])} priced listings")
    except Exception as e:  # noqa: BLE001
        print(f"  models.dev: FAILED ({e})")

    if not any(by_source.values()):
        print("No source returned data; not writing a snapshot.")
        return 1

    snapshot = build_snapshot_from_listings(by_source, observed_at=observed_at)
    path = write_snapshot(snapshot)
    print(
        f"Wrote {snapshot['listing_count']} reconciled listings from {snapshot['sources']} "
        f"({snapshot['multi_source_count']} corroborated by >=2 sources, "
        f"{snapshot['disputed_count']} disputed) -> {path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
