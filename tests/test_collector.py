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
