"""Load capability tiers from data/tiers.json (methodology section 6).

Single source of truth for the primary benchmark + tier thresholds, so adding
or retuning a tier is a config edit, not a code change.
"""
import json
from pathlib import Path
from typing import List, Tuple

TIERS_PATH = Path(__file__).resolve().parent.parent / "data" / "tiers.json"


def load_tiers(path=TIERS_PATH) -> dict:
    """Return {primary_benchmark, base_date, tiers: [(name, threshold), ...]}."""
    cfg = json.loads(Path(path).read_text())
    tier_pairs: List[Tuple[str, float]] = [
        (t["name"], t["threshold"]) for t in cfg["tiers"]
    ]
    return {
        "primary_benchmark": cfg["primary_benchmark"],
        "base_date": cfg.get("base_date"),
        "tiers": tier_pairs,
    }


# Loaded once at import for convenient access across modules.
_DEFAULT = load_tiers()
PRIMARY_BENCHMARK: str = _DEFAULT["primary_benchmark"]
DEFAULT_TIERS = _DEFAULT["tiers"]
BASE_DATE = _DEFAULT["base_date"]
