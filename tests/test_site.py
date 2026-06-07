"""Tests for beacon.site.build_context — the pure data behind the public
dashboard. HTML/SVG rendering is visual and verified by opening the page."""
import unittest

from beacon import site

SNAPSHOT = {
    "observed_at": "2026-06-07",
    "listing_count": 3,
    "methodology_version": "0.1",
    "listings": [
        {"model": "a", "blended_mtok": 1.0},
        {"model": "b", "blended_mtok": 2.0},
        {"model": "c", "blended_mtok": 0.5},
    ],
}
CAP = {
    "a": {"GPQA-Diamond": 80.0},
    "b": {"GPQA-Diamond": 90.0},
    "c": {"GPQA-Diamond": 60.0},
}
TIERS = [("hi", 85), ("mid", 70), ("lo", 50)]


class BuildContext(unittest.TestCase):
    def test_header_fields(self):
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS)
        self.assertEqual(ctx["as_of"], "2026-06-07")
        self.assertEqual(ctx["model_count"], 3)
        self.assertEqual(ctx["methodology_version"], "0.1")
        self.assertEqual(ctx["benchmark"], "GPQA-Diamond")

    def test_tiers_have_iso_quality_spread_and_breadth(self):
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS)
        by = {t["name"]: t for t in ctx["tiers"]}
        self.assertAlmostEqual(by["lo"]["value_usd_per_mtok"], 0.5)
        self.assertEqual(by["lo"]["n_qualifying"], 3)
        self.assertAlmostEqual(by["mid"]["value_usd_per_mtok"], 1.0)
        self.assertEqual(by["hi"]["n_qualifying"], 1)
        self.assertIsNone(by["hi"]["spread"])  # one qualifier -> no spread

    def test_onchain_link(self):
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS)
        self.assertEqual(ctx["onchain"]["address"], "0xABC")
        self.assertIn("0xABC", ctx["onchain"]["explorer_url"])

    def test_onchain_optional(self):
        ctx = site.build_context(SNAPSHOT, CAP, None, tiers=TIERS)
        self.assertIsNone(ctx["onchain"])


if __name__ == "__main__":
    unittest.main()
