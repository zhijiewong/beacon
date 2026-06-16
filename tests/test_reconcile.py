"""Tests for cross-source price reconciliation (multi-source robustness)."""
import unittest

from beacon import reconcile


def L(model, blended, source, inp=None, out=None):
    """Minimal listing dict for tests."""
    return {
        "model": model,
        "provider": model.split("/")[0] if "/" in model else model,
        "name": model,
        "input_mtok": inp if inp is not None else blended,
        "output_mtok": out if out is not None else blended,
        "blended_mtok": blended,
        "source": source,
    }


class TestCanonicalKey(unittest.TestCase):
    def test_lowercases_and_keeps_vendor_slug(self):
        self.assertEqual(reconcile.canonical_key("OpenAI/GPT-4o"), "openai/gpt-4o")

    def test_bare_slug_unchanged(self):
        self.assertEqual(reconcile.canonical_key("gpt-4o"), "gpt-4o")

    def test_dots_and_spaces_become_dashes(self):
        self.assertEqual(
            reconcile.canonical_key("anthropic/claude-3.5 sonnet"),
            "anthropic/claude-3-5-sonnet",
        )

    def test_strips_variant_suffix(self):
        self.assertEqual(
            reconcile.canonical_key("meta-llama/llama-3-8b:free"),
            "meta-llama/llama-3-8b",
        )


class TestReconcile(unittest.TestCase):
    def test_single_source_passes_through(self):
        out = reconcile.reconcile_listings([L("openai/gpt-4o", 10.0, "openrouter")])
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["blended_mtok"], 10.0)
        self.assertEqual(r["n_sources"], 1)
        self.assertEqual(r["source_spread_ratio"], 0.0)
        self.assertFalse(r["disputed"])

    def test_two_sources_median_and_provenance(self):
        out = reconcile.reconcile_listings([
            L("openai/gpt-4o", 10.0, "openrouter"),
            L("OpenAI/gpt-4o", 12.0, "models.dev"),
        ])
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["blended_mtok"], 11.0)  # median of two = mean
        self.assertEqual(r["n_sources"], 2)
        self.assertEqual(sorted(r["sources"]), ["models.dev", "openrouter"])

    def test_three_sources_median_resists_outlier(self):
        out = reconcile.reconcile_listings([
            L("x/m", 100.0, "openrouter"),
            L("x/m", 102.0, "models.dev"),
            L("x/m", 500.0, "third"),  # an outlier source can't drag the median
        ])
        r = out[0]
        self.assertEqual(r["blended_mtok"], 102.0)
        self.assertTrue(r["disputed"])  # big spread is flagged

    def test_primary_source_sets_the_model_id(self):
        # Same model across sources (canonical keys align) but different raw ids.
        # The OpenRouter id must win so the downstream benchmark join still matches.
        out = reconcile.reconcile_listings([
            L("OpenAI/GPT-4o", 12.0, "models.dev"),
            L("openai/gpt-4o", 10.0, "openrouter"),
        ], primary="openrouter")
        self.assertEqual(len(out), 1)  # they merged on canonical key
        self.assertEqual(out[0]["model"], "openai/gpt-4o")

    def test_collapses_within_source_so_one_source_cannot_dominate(self):
        # models.dev lists the same model from many hosts; those must collapse to ONE
        # vote (their median), so a single source's host count can't swing the result
        # and one bad host can't blow it up.
        out = reconcile.reconcile_listings([
            L("x/m", 10.0, "models.dev"),
            L("x/m", 12.0, "models.dev"),
            L("x/m", 200.0, "models.dev"),   # one bad host
            L("x/m", 10.0, "openrouter"),
        ])
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["n_sources"], 2)          # two sources, not four listings
        # models.dev median = 12; openrouter = 10; cross-source median = 11
        self.assertEqual(r["blended_mtok"], 11.0)

    def test_within_threshold_not_disputed(self):
        out = reconcile.reconcile_listings([
            L("x/m", 100.0, "openrouter"),
            L("x/m", 110.0, "models.dev"),
        ], max_spread_ratio=0.25)
        self.assertFalse(out[0]["disputed"])  # 10% spread < 25%


if __name__ == "__main__":
    unittest.main()
