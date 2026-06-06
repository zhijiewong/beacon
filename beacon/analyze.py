"""Join price snapshots to capability data and compute per-tier indices.

  python3 -m beacon.analyze            # report on the latest snapshot

Output is ILLUSTRATIVE until data/benchmarks.csv is calibrated with verified
scores (see data/README.md). The join + index math is real and unit-tested;
the capability inputs are what need verifying.
"""
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from beacon import index

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
BENCHMARKS_CSV = DATA_DIR / "benchmarks.csv"


def read_benchmarks(path: str) -> List[dict]:
    """Read benchmarks.csv, ignoring blank and '#'-comment lines."""
    lines = [
        ln for ln in Path(path).read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    return list(csv.DictReader(lines))


def build_capability_map(
    rows: List[dict], include_unverified: bool = False
) -> Dict[str, Dict[str, float]]:
    """Group benchmark rows into {model_id: {benchmark: score}}.

    Rows with verified != 'yes' are excluded unless include_unverified=True,
    so a production run never silently uses placeholder scores.
    """
    cap: Dict[str, Dict[str, float]] = {}
    for row in rows:
        if not include_unverified and row.get("verified") != "yes":
            continue
        try:
            score = float(row["score"])
        except (TypeError, ValueError, KeyError):
            continue
        cap.setdefault(row["model_id"], {})[row["benchmark"]] = score
    return cap


def join_prices_to_scores(
    listings: List[dict], cap: Dict[str, Dict[str, float]], benchmark: str
) -> List[Tuple[float, float]]:
    """Pair (blended_mtok, score) for listings whose model has `benchmark`."""
    pairs = []
    for listing in listings:
        scores = cap.get(listing["model"])
        if scores and benchmark in scores:
            pairs.append((listing["blended_mtok"], scores[benchmark]))
    return pairs


def compute_tier(
    listings: List[dict],
    cap: Dict[str, Dict[str, float]],
    benchmark: str,
    threshold: float,
) -> dict:
    """Compute iso-quality and spread for one capability tier (methodology 7)."""
    pairs = join_prices_to_scores(listings, cap, benchmark)
    qualifying = [price for price, score in pairs if score >= threshold]
    spread: Optional[float] = index.spread(qualifying) if len(qualifying) >= 2 else None
    return {
        "benchmark": benchmark,
        "threshold": threshold,
        "n_scored": len(pairs),
        "n_qualifying": len(qualifying),
        "iso_quality": index.iso_quality(pairs, threshold),
        "spread": spread,
    }


def latest_snapshot_path() -> Optional[Path]:
    snaps = sorted(SNAPSHOT_DIR.glob("*.json"))
    return snaps[-1] if snaps else None


def main() -> int:
    snap_path = latest_snapshot_path()
    if snap_path is None:
        print("No snapshot found. Run: python3 -m beacon.collector")
        return 1
    snapshot = json.loads(snap_path.read_text())
    rows = read_benchmarks(str(BENCHMARKS_CSV))

    cap = build_capability_map(rows, include_unverified=False)
    illustrative = False
    if not cap:
        cap = build_capability_map(rows, include_unverified=True)
        illustrative = True

    print(f"Snapshot: {snap_path.name}  ({snapshot['listing_count']} priced listings)")
    if illustrative:
        print("!! ILLUSTRATIVE ONLY — benchmarks.csv has no verified scores yet.")
        print("!! Calibrate data/benchmarks.csv before treating output as real.\n")

    # Provisional GPQA-Diamond tiers (methodology section 6). Frontier ~>=90;
    # "GPT-4-class" ~>=50 (original GPT-4 GPQA-Diamond milestone). Final
    # thresholds belong in tiers.json during full calibration.
    print("  GPQA-Diamond capability tiers (iso-quality = cheapest $/Mtok to reach):")
    for name, threshold in [("frontier", 90), ("strong", 70), ("gpt-4-class", 50), ("broad", 0)]:
        tier = compute_tier(snapshot["listings"], cap, "GPQA-Diamond", threshold)
        iso = tier["iso_quality"]
        iso_s = f"${iso:.3f}/Mtok" if iso is not None else "n/a"
        spread_s = f"{tier['spread']:.2f}x" if tier["spread"] is not None else "n/a"
        print(
            f"    {name:<12} (>={threshold:>3}): "
            f"qualifying={tier['n_qualifying']:>2}  "
            f"iso-quality={iso_s:<14} spread(P90/P10)={spread_s}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
