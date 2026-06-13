"""Tests for beacon.site.build_context — the pure data behind the public
dashboard. HTML/SVG rendering is visual and verified by opening the page."""
import json
import tempfile
import unittest
from pathlib import Path

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

    def test_onchain_stack_in_context(self):
        stack = [{"name": "Index oracle", "role": "feeds", "address": "0x1", "explorer_url": "u"}]
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS, stack=stack)
        self.assertEqual(ctx["onchain"]["contracts"], stack)
        self.assertEqual(ctx["onchain"]["network"], "Base Sepolia")

    def test_onchain_stack_reads_deployed_files_and_skips_missing(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "token-deployed.json").write_text(json.dumps({"address": "0xTOKEN"}))
            (Path(d) / "staking-deployed.json").write_text(json.dumps({"address": "0xSTAKE"}))
            # deployed.json and oracle-v2-deployed.json absent -> skipped, no error
            stack = site.onchain_stack(d)
        addrs = [c["address"] for c in stack]
        self.assertEqual(addrs, ["0xTOKEN", "0xSTAKE"])  # order preserved, missing skipped
        self.assertTrue(all(c["explorer_url"].endswith(c["address"]) for c in stack))

    def test_tier_detail_cheapest_model_providers_prices(self):
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS)
        by = {t["name"]: t for t in ctx["tiers"]}
        self.assertEqual(by["lo"]["cheapest_model"], "c")   # 0.5 is cheapest qualifying
        self.assertEqual(by["lo"]["provider_count"], 3)
        self.assertEqual(sorted(by["lo"]["prices"]), [0.5, 1.0, 2.0])
        self.assertEqual(by["mid"]["cheapest_model"], "a")  # 1.0 cheapest of a,b
        self.assertEqual(by["mid"]["provider_count"], 2)

    def test_key_figures(self):
        ctx = site.build_context(SNAPSHOT, CAP, "0xABC", tiers=TIERS)
        kf = ctx["key_figures"]
        self.assertEqual(kf["providers_total"], 3)
        self.assertAlmostEqual(kf["multiple"], 4.0)  # hi 2.0 / lo 0.5


class PctChange(unittest.TestCase):
    def test_change_vs_previous_point(self):
        self.assertAlmostEqual(site.pct_change([("d1", 1.0), ("d2", 0.5)]), -50.0)

    def test_none_when_too_short(self):
        self.assertIsNone(site.pct_change([("d1", 1.0)]))


if __name__ == "__main__":
    unittest.main()
