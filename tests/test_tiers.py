"""Tests for beacon.tiers — loading capability tiers from data/tiers.json."""
import json
import tempfile
import unittest
from pathlib import Path

from beacon import tiers


class LoadTiers(unittest.TestCase):
    def _write(self, d, obj):
        p = Path(d) / "tiers.json"
        p.write_text(json.dumps(obj))
        return str(p)

    def test_returns_primary_benchmark_and_tier_pairs(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, {
                "primary_benchmark": "GPQA-Diamond",
                "base_date": "2026-06-06",
                "tiers": [
                    {"name": "frontier", "benchmark": "GPQA-Diamond", "threshold": 90},
                    {"name": "strong", "benchmark": "GPQA-Diamond", "threshold": 70},
                ],
            })
            t = tiers.load_tiers(path)
        self.assertEqual(t["primary_benchmark"], "GPQA-Diamond")
        self.assertEqual(t["base_date"], "2026-06-06")
        self.assertEqual(t["tiers"], [("frontier", 90), ("strong", 70)])

    def test_real_tiers_json_loads(self):
        # the shipped config must be valid and GPQA-Diamond primary
        t = tiers.load_tiers()
        self.assertEqual(t["primary_benchmark"], "GPQA-Diamond")
        self.assertTrue(all(isinstance(name, str) and isinstance(thr, (int, float))
                            for name, thr in t["tiers"]))
        self.assertGreaterEqual(len(t["tiers"]), 1)


if __name__ == "__main__":
    unittest.main()
