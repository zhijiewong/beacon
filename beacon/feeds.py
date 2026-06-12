"""Shape the per-tier index into oracle feeds for the on-chain publisher.

  python3 -m beacon.feeds        # print latest snapshot's feeds as JSON

Each feed = {feed, value_usd_per_mtok, threshold, n_qualifying}. The CLI adds
snapshot_date + methodology_version so the publisher can post full provenance.
The on-chain publisher converts value_usd_per_mtok to 8-decimal fixed point.
"""
import json
import sys
from typing import Dict, List, Sequence, Tuple

from beacon import analyze, tiers as tiers_cfg

# Tiers + primary benchmark come from data/tiers.json (methodology section 6).
_CFG = tiers_cfg.load_tiers()
PRIMARY_BENCHMARK = _CFG["primary_benchmark"]
DEFAULT_TIERS = _CFG["tiers"]


def build_feeds(
    listings: List[dict],
    cap: Dict[str, Dict[str, float]],
    benchmark: str,
    tiers: Sequence[Tuple[str, float]],
) -> List[dict]:
    """One feed per tier that has at least one qualifying model."""
    out = []
    for name, threshold in tiers:
        tier = analyze.compute_tier(listings, cap, benchmark, threshold)
        if tier["iso_quality"] is None:
            continue
        out.append({
            "feed": f"{benchmark}:{name}",
            "value_usd_per_mtok": tier["iso_quality"],
            "threshold": threshold,
            "n_qualifying": tier["n_qualifying"],
        })
    return out


def main() -> int:
    snap_path = analyze.SNAPSHOT_DIR
    snaps = sorted(snap_path.glob("*.json"))
    if not snaps:
        print(json.dumps({"error": "no snapshot; run beacon.collector"}))
        return 1
    snapshot = json.loads(snaps[-1].read_text())
    rows = analyze.read_benchmarks(str(analyze.BENCHMARKS_CSV))
    cap = analyze.build_capability_map(rows, include_unverified=False)
    if not cap:
        print(json.dumps({"error": "no verified benchmarks; calibrate first"}))
        return 1

    feeds = build_feeds(snapshot["listings"], cap, PRIMARY_BENCHMARK, DEFAULT_TIERS)
    payload = {
        "snapshot_date": snapshot["observed_at"].replace("-", ""),  # e.g. 20260606
        "methodology_version": snapshot.get("methodology_version", "0.1"),
        "feeds": feeds,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
