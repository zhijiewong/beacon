"""Collect LLM inference prices and persist daily snapshots.

Primary source: OpenRouter's public /models endpoint, which exposes
per-token input/output prices across ~340 models from all major providers.

  python3 -m beacon.collector            # fetch live + write today's snapshot

The pure assembly (build_snapshot) and persistence (write_snapshot) are
unit-tested; only fetch_openrouter() touches the network.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from beacon import pricing

METHODOLOGY_VERSION = "0.1"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
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


def write_snapshot(snapshot: dict, out_dir=DEFAULT_SNAPSHOT_DIR) -> str:
    """Write a snapshot to <out_dir>/<observed_at>.json and return the path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snapshot['observed_at']}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    return str(path)


def fetch_openrouter(url: str = OPENROUTER_MODELS_URL, timeout: int = 30) -> List[dict]:
    """Fetch the live OpenRouter model list (network)."""
    req = urllib.request.Request(url, headers={"User-Agent": "beacon-collector/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["data"]


def main() -> int:
    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Fetching OpenRouter model prices ({observed_at})...")
    raw = fetch_openrouter()
    snapshot = build_snapshot(raw, observed_at=observed_at)
    path = write_snapshot(snapshot)
    print(
        f"Wrote {snapshot['listing_count']} priced listings "
        f"(of {len(raw)} models) -> {path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
