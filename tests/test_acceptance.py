"""Phase-1 acceptance test (methodology section 12).

Validates that Beacon's iso-quality method reproduces the published LLMflation
curve. We feed a16z's real historical anchor points (MMLU-42 series) through our
own `index.iso_quality` and confirm we recover a16z's headline result:
$60/Mtok (GPT-3, 2021) -> $0.06/Mtok (Llama 3.2 3B, 2024) = ~1000x over ~3 years
(~10x/year). See data/historical_anchors.csv and docs/acceptance-test.md.

Our live daily series is too short to show a multi-year decline; this validates
the *method* against an external published oracle.
"""
import csv
import datetime as dt
import unittest
from pathlib import Path

from beacon import index

ANCHORS = Path(__file__).resolve().parent.parent / "data" / "historical_anchors.csv"
A16Z_DECLINE = 1000.0   # a16z: 1000x over 3 years at MMLU-42
A16Z_ANNUAL = 10.0      # a16z: ~10x/year


def _load_series(name):
    rows = [
        ln for ln in ANCHORS.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    out = []
    for r in csv.DictReader(rows):
        if r["series"] == name:
            out.append((r["date"], float(r["mmlu"]), float(r["blended_usd_per_mtok"])))
    return out


class LLMflationReproduction(unittest.TestCase):
    def test_iso_quality_recovers_a16z_mmlu42_decline(self):
        series = _load_series("MMLU-42")
        self.assertEqual(len(series), 2)
        (d0, _, _), (d1, _, _) = series[0], series[-1]

        # iso-quality at MMLU>=42 at each date = cheapest blended price reaching it
        def iso(date):
            pairs = [(price, mmlu) for d, mmlu, price in series if d == date]
            return index.iso_quality(pairs, threshold=42)

        start, end = iso(d0), iso(d1)
        self.assertAlmostEqual(start, 60.0)
        self.assertAlmostEqual(end, 0.06)

        decline = start / end
        # reproduces a16z's ~1000x within 5%
        self.assertAlmostEqual(decline, A16Z_DECLINE, delta=A16Z_DECLINE * 0.05)

        years = (dt.date.fromisoformat(d1 + "-01") - dt.date.fromisoformat(d0 + "-01")).days / 365.25
        annual = decline ** (1 / years)
        # reproduces a16z's ~10x/year within tolerance
        self.assertTrue(8.5 <= annual <= 12.0, f"annual decline {annual:.1f}x outside ~10x/yr")


if __name__ == "__main__":
    unittest.main()
