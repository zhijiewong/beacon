"""Tests for beacon.analyze — joining price data to capability data and
computing per-tier indices (methodology section 7)."""
import tempfile
import textwrap
import unittest
from pathlib import Path

from beacon import analyze


ROWS = [
    {"model_id": "a/m1", "benchmark": "GPQA-Diamond", "score": "80", "verified": "yes"},
    {"model_id": "a/m1", "benchmark": "MMLU", "score": "88", "verified": "yes"},
    {"model_id": "b/m2", "benchmark": "GPQA-Diamond", "score": "70", "verified": "needs_review"},
]

LISTINGS = [
    {"model": "a/m1", "blended_mtok": 1.0},
    {"model": "b/m2", "blended_mtok": 2.0},
    {"model": "c/m3", "blended_mtok": 3.0},
]


class BuildCapabilityMap(unittest.TestCase):
    def test_groups_verified_scores_by_model(self):
        cap = analyze.build_capability_map(ROWS)
        self.assertEqual(cap, {"a/m1": {"GPQA-Diamond": 80.0, "MMLU": 88.0}})

    def test_excludes_unverified_by_default(self):
        cap = analyze.build_capability_map(ROWS)
        self.assertNotIn("b/m2", cap)

    def test_can_include_unverified(self):
        cap = analyze.build_capability_map(ROWS, include_unverified=True)
        self.assertIn("b/m2", cap)


class JoinPricesToScores(unittest.TestCase):
    def test_pairs_only_models_that_have_the_benchmark(self):
        cap = {"a/m1": {"GPQA-Diamond": 80.0}, "b/m2": {"GPQA-Diamond": 70.0}}
        pairs = analyze.join_prices_to_scores(LISTINGS, cap, "GPQA-Diamond")
        self.assertEqual(sorted(pairs), [(1.0, 80.0), (2.0, 70.0)])  # c/m3 dropped


class ComputeTier(unittest.TestCase):
    def test_iso_quality_and_breadth(self):
        cap = {"a/m1": {"GPQA-Diamond": 80.0}, "b/m2": {"GPQA-Diamond": 70.0}}
        result = analyze.compute_tier(LISTINGS, cap, "GPQA-Diamond", threshold=75)
        self.assertEqual(result["n_qualifying"], 1)
        self.assertAlmostEqual(result["iso_quality"], 1.0)
        self.assertIsNone(result["spread"])  # need >=2 qualifiers for a spread


class ReadBenchmarksCsv(unittest.TestCase):
    def test_skips_comment_lines(self):
        csv_text = textwrap.dedent(
            """\
            model_id,benchmark,score,as_of,source_url,verified
            # this is a comment and must be ignored
            a/m1,GPQA-Diamond,80,,http://src,yes
            """
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.csv"
            p.write_text(csv_text)
            rows = analyze.read_benchmarks(str(p))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model_id"], "a/m1")


if __name__ == "__main__":
    unittest.main()
