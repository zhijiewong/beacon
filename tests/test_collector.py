"""Tests for beacon.collector — snapshot assembly and persistence.

Network fetching is isolated in collector.fetch_openrouter(); everything
testable here is pure (build_snapshot) or local file I/O (write_snapshot).
"""
import json
import tempfile
import unittest
from pathlib import Path

from beacon import collector


RAW_MODELS = [
    {
        "id": "anthropic/claude-test",
        "name": "Anthropic: Claude Test",
        "context_length": 200000,
        "pricing": {"prompt": "0.0000005", "completion": "0.0000025"},
    },
    {
        "id": "vendor/free-model",
        "name": "Free Model",
        "context_length": 8000,
        "pricing": {"prompt": "0", "completion": "0"},  # excluded
    },
]


class BuildSnapshot(unittest.TestCase):
    def test_excludes_free_models_and_counts_listings(self):
        snap = collector.build_snapshot(RAW_MODELS, observed_at="2026-06-07")
        self.assertEqual(snap["observed_at"], "2026-06-07")
        self.assertEqual(snap["source"], "openrouter")
        self.assertEqual(snap["listing_count"], 1)
        self.assertEqual(len(snap["listings"]), 1)

    def test_listing_carries_normalized_fields(self):
        snap = collector.build_snapshot(RAW_MODELS, observed_at="2026-06-07")
        listing = snap["listings"][0]
        self.assertEqual(listing["provider"], "anthropic")
        self.assertAlmostEqual(listing["blended_mtok"], 1.0)

    def test_records_methodology_version(self):
        snap = collector.build_snapshot(RAW_MODELS, observed_at="2026-06-07")
        self.assertIn("methodology_version", snap)


class MultiSourceSnapshot(unittest.TestCase):
    def _listings(self):
        from beacon import pricing
        orl = pricing.parse_openrouter_model(
            {"id": "openai/gpt-4o", "name": "GPT-4o",
             "pricing": {"prompt": "0.000010", "completion": "0.000010"}},  # blended 10.0
            observed_at="2026-06-07",
        )
        md = pricing.parse_modelsdev_payload(
            {"host": {"name": "H", "models": {
                "openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                                  "cost": {"input": 12, "output": 12}}}}},  # blended 12.0
            observed_at="2026-06-07",
        )
        return {"openrouter": [orl.to_dict()], "models.dev": [m.to_dict() for m in md]}

    def test_reconciles_price_across_sources(self):
        snap = collector.build_snapshot_from_listings(self._listings(), observed_at="2026-06-07")
        self.assertEqual(snap["sources"], ["models.dev", "openrouter"])
        self.assertEqual(snap["listing_count"], 1)
        self.assertEqual(snap["multi_source_count"], 1)
        listing = snap["listings"][0]
        self.assertEqual(listing["model"], "openai/gpt-4o")  # primary id preserved for the join
        self.assertEqual(listing["n_sources"], 2)
        self.assertEqual(listing["blended_mtok"], 11.0)  # median of 10 and 12

    def test_degrades_gracefully_to_one_source(self):
        only_or = {"openrouter": self._listings()["openrouter"]}
        snap = collector.build_snapshot_from_listings(only_or, observed_at="2026-06-07")
        self.assertEqual(snap["sources"], ["openrouter"])
        self.assertEqual(snap["multi_source_count"], 0)
        self.assertEqual(snap["listings"][0]["n_sources"], 1)


class WriteSnapshot(unittest.TestCase):
    def test_writes_dated_json_that_roundtrips(self):
        snap = collector.build_snapshot(RAW_MODELS, observed_at="2026-06-07")
        with tempfile.TemporaryDirectory() as d:
            path = collector.write_snapshot(snap, out_dir=d)
            self.assertEqual(Path(path).name, "2026-06-07.json")
            reloaded = json.loads(Path(path).read_text())
            self.assertEqual(reloaded, snap)


if __name__ == "__main__":
    unittest.main()
