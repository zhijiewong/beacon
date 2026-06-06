"""Tests for beacon.pricing — price normalization and OpenRouter parsing.

Run: python3 -m unittest discover -s tests -v
"""
import unittest

from beacon import pricing


class PerTokenToPerMtok(unittest.TestCase):
    def test_converts_per_token_usd_to_per_million_tokens(self):
        # OpenRouter quotes per-token USD; "0.0000005" => $0.50 per 1M tokens
        self.assertAlmostEqual(pricing.per_token_to_per_mtok(0.0000005), 0.5)

    def test_zero_stays_zero(self):
        self.assertEqual(pricing.per_token_to_per_mtok(0.0), 0.0)


class BlendedPrice(unittest.TestCase):
    def test_default_weights_are_3to1_input_output(self):
        # (3*input + 1*output) / 4
        self.assertAlmostEqual(pricing.blended_price(0.5, 2.5), 1.0)

    def test_equal_prices_blend_to_same_value(self):
        self.assertAlmostEqual(pricing.blended_price(2.0, 2.0), 2.0)

    def test_weights_are_configurable(self):
        # equal 1:1 weighting => simple mean
        self.assertAlmostEqual(
            pricing.blended_price(0.0, 4.0, w_input=1, w_output=1), 2.0
        )


class ParseOpenRouterModel(unittest.TestCase):
    def _raw(self, **over):
        raw = {
            "id": "anthropic/claude-test",
            "name": "Anthropic: Claude Test",
            "context_length": 200000,
            "pricing": {"prompt": "0.0000005", "completion": "0.0000025"},
        }
        raw.update(over)
        return raw

    def test_parses_provider_and_blended_price(self):
        listing = pricing.parse_openrouter_model(self._raw(), observed_at="2026-06-07")
        self.assertEqual(listing.provider, "anthropic")
        self.assertEqual(listing.model, "anthropic/claude-test")
        self.assertAlmostEqual(listing.input_mtok, 0.5)
        self.assertAlmostEqual(listing.output_mtok, 2.5)
        self.assertAlmostEqual(listing.blended_mtok, 1.0)  # (3*0.5+2.5)/4
        self.assertEqual(listing.context_length, 200000)
        self.assertEqual(listing.observed_at, "2026-06-07")
        self.assertEqual(listing.source_type, "host")  # OpenRouter is a host

    def test_free_model_is_excluded(self):
        # Both prices zero => not a priced listing => None
        raw = self._raw(pricing={"prompt": "0", "completion": "0"})
        self.assertIsNone(pricing.parse_openrouter_model(raw, observed_at="2026-06-07"))

    def test_missing_pricing_is_excluded(self):
        raw = self._raw()
        del raw["pricing"]
        self.assertIsNone(pricing.parse_openrouter_model(raw, observed_at="2026-06-07"))

    def test_negative_sentinel_price_is_excluded(self):
        # OpenRouter router pseudo-models (e.g. openrouter/auto) quote -1/token
        # as a "variable pricing" sentinel; these are not real priced listings.
        raw = self._raw(id="openrouter/auto", pricing={"prompt": "-1", "completion": "-1"})
        self.assertIsNone(pricing.parse_openrouter_model(raw, observed_at="2026-06-07"))

    def test_output_only_zero_is_still_priced(self):
        # A non-zero input price means it IS a priced listing.
        raw = self._raw(pricing={"prompt": "0.000001", "completion": "0"})
        listing = pricing.parse_openrouter_model(raw, observed_at="2026-06-07")
        self.assertIsNotNone(listing)
        self.assertAlmostEqual(listing.input_mtok, 1.0)
        self.assertAlmostEqual(listing.output_mtok, 0.0)


if __name__ == "__main__":
    unittest.main()
