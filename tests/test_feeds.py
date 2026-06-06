"""Tests for beacon.feeds — shaping per-tier index values into oracle feeds
that the on-chain publisher will post."""
import unittest

from beacon import feeds

LISTINGS = [
    {"model": "a", "blended_mtok": 1.0},
    {"model": "b", "blended_mtok": 2.0},
    {"model": "c", "blended_mtok": 0.5},
]
CAP = {"a": {"G": 80.0}, "b": {"G": 90.0}, "c": {"G": 60.0}}
TIERS = [("hi", 85), ("mid", 70), ("lo", 50)]


class BuildFeeds(unittest.TestCase):
    def test_one_feed_per_tier_with_iso_quality_value(self):
        out = feeds.build_feeds(LISTINGS, CAP, "G", TIERS)
        by_feed = {f["feed"]: f for f in out}
        self.assertEqual(by_feed["G:hi"]["value_usd_per_mtok"], 2.0)
        self.assertEqual(by_feed["G:mid"]["value_usd_per_mtok"], 1.0)
        self.assertEqual(by_feed["G:lo"]["value_usd_per_mtok"], 0.5)

    def test_feed_carries_threshold_and_breadth(self):
        out = feeds.build_feeds(LISTINGS, CAP, "G", TIERS)
        mid = next(f for f in out if f["feed"] == "G:mid")
        self.assertEqual(mid["threshold"], 70)
        self.assertEqual(mid["n_qualifying"], 2)

    def test_tier_with_no_qualifiers_is_omitted(self):
        out = feeds.build_feeds(LISTINGS, CAP, "G", [("none", 95)])
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
