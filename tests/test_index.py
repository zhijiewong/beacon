"""Tests for beacon.index — capability-normalized index construction.

Covers methodology section 7 (iso-quality, frontier, spread) and the
data-quality guard in section 8 (outlier-resistant minimum).
"""
import unittest

from beacon import index


class Percentile(unittest.TestCase):
    # Linear interpolation between closest ranks (numpy 'linear' default).
    def test_median(self):
        self.assertAlmostEqual(index.percentile([1, 2, 3, 4, 5], 50), 3.0)

    def test_p10_interpolates(self):
        self.assertAlmostEqual(index.percentile([1, 2, 3, 4, 5], 10), 1.4)

    def test_p90_interpolates(self):
        self.assertAlmostEqual(index.percentile([1, 2, 3, 4, 5], 90), 4.6)

    def test_unsorted_input_is_handled(self):
        self.assertAlmostEqual(index.percentile([5, 1, 3, 2, 4], 50), 3.0)


class Spread(unittest.TestCase):
    def test_p90_over_p10_ratio(self):
        self.assertAlmostEqual(index.spread([1, 2, 3, 4, 5]), 4.6 / 1.4)

    def test_uniform_prices_have_spread_of_one(self):
        self.assertAlmostEqual(index.spread([2.0, 2.0, 2.0]), 1.0)


class RobustMinPrice(unittest.TestCase):
    def test_returns_minimum_when_no_outlier(self):
        self.assertAlmostEqual(index.robust_min_price([1.0, 1.1, 1.2]), 1.0)

    def test_drops_extreme_low_outlier(self):
        # 0.1 is >50% below the next-cheapest (1.0) => quarantined
        self.assertAlmostEqual(index.robust_min_price([0.1, 1.0, 1.1]), 1.0)

    def test_keeps_low_price_that_is_within_threshold(self):
        # 0.5 vs next 0.9: 0.5 is NOT more than 50% below 0.9 => kept
        self.assertAlmostEqual(index.robust_min_price([0.5, 0.9]), 0.5)

    def test_single_price(self):
        self.assertAlmostEqual(index.robust_min_price([2.0]), 2.0)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            index.robust_min_price([])


class IsoQuality(unittest.TestCase):
    def _data(self):
        # (blended_price, capability_score)
        return [(1.0, 80), (2.0, 90), (0.05, 85), (3.0, 40)]

    def test_cheapest_qualifying_price_with_outlier_guard(self):
        # threshold 80: qualifiers are 1.0, 2.0, 0.05; 0.05 quarantined => 1.0
        self.assertAlmostEqual(index.iso_quality(self._data(), threshold=80), 1.0)

    def test_returns_none_when_nothing_qualifies(self):
        self.assertIsNone(index.iso_quality(self._data(), threshold=95))


class IndexValue(unittest.TestCase):
    def test_normalizes_to_base_of_100(self):
        self.assertAlmostEqual(index.index_value(1.0, base=4.0), 25.0)

    def test_base_equals_value_is_100(self):
        self.assertAlmostEqual(index.index_value(4.0, base=4.0), 100.0)


if __name__ == "__main__":
    unittest.main()
