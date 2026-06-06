"""Tests for beacon.plot — the pure data shaping behind the charts.
Rendering (ASCII/SVG) is visual presentation and not unit-tested here."""
import unittest

from beacon import plot


LISTINGS = [
    {"model": "a", "blended_mtok": 1.0},
    {"model": "b", "blended_mtok": 2.0},
    {"model": "c", "blended_mtok": 0.5},
]
CAP = {"a": {"G": 80.0}, "b": {"G": 90.0}, "c": {"G": 60.0}}


class FrontierCurve(unittest.TestCase):
    def test_cheapest_price_to_reach_each_threshold(self):
        curve = plot.frontier_curve(LISTINGS, CAP, "G", thresholds=[50, 70, 85])
        # 50: all qualify -> cheapest 0.5; 70: a,b -> 1.0; 85: only b -> 2.0
        self.assertEqual(curve, [(50, 0.5), (70, 1.0), (85, 2.0)])

    def test_threshold_above_all_models_is_none(self):
        curve = plot.frontier_curve(LISTINGS, CAP, "G", thresholds=[95])
        self.assertEqual(curve, [(95, None)])


class IsoQualitySeries(unittest.TestCase):
    def test_builds_sorted_time_series_skipping_empty_dates(self):
        snapshots = [
            ("2026-06-02", [{"model": "a", "blended_mtok": 0.8}]),
            ("2026-06-01", [{"model": "a", "blended_mtok": 1.0}]),
            ("2026-06-03", [{"model": "c", "blended_mtok": 0.5}]),  # c scores 60 < 70
        ]
        series = plot.iso_quality_series(snapshots, CAP, "G", threshold=70)
        # sorted by date; 06-03 dropped (no model >=70 that day)
        self.assertEqual(series, [("2026-06-01", 1.0), ("2026-06-02", 0.8)])


if __name__ == "__main__":
    unittest.main()
