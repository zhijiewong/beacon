"""Tests for the price-source adapters (OpenRouter source tag + models.dev parser)."""
import unittest

from beacon import pricing


class TestSourceTag(unittest.TestCase):
    def test_openrouter_listing_is_tagged(self):
        raw = {
            "id": "anthropic/claude-test",
            "name": "Claude Test",
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "context_length": 200000,
        }
        listing = pricing.parse_openrouter_model(raw, observed_at="2026-06-07")
        self.assertEqual(listing.source, "openrouter")


class TestModelsDevParser(unittest.TestCase):
    def _payload(self):
        return {
            "requesty": {
                "name": "Requesty",
                "models": {
                    # cost is already $/Mtok in models.dev
                    "xai/grok-4": {"id": "xai/grok-4", "name": "Grok 4",
                                   "cost": {"input": 3, "output": 15}},
                    "free-x": {"id": "free-x", "name": "Free", "cost": {"input": 0, "output": 0}},
                    "no-cost": {"id": "no-cost", "name": "NoCost"},
                },
            }
        }

    def test_parses_priced_model_in_mtok(self):
        out = pricing.parse_modelsdev_payload(self._payload(), observed_at="2026-06-07")
        self.assertEqual(len(out), 1)  # free + no-cost dropped
        m = out[0]
        self.assertEqual(m.model, "xai/grok-4")
        self.assertEqual(m.provider, "xai")
        self.assertEqual(m.input_mtok, 3.0)   # used directly, not *1e6
        self.assertEqual(m.output_mtok, 15.0)
        self.assertEqual(m.blended_mtok, (3 * 3.0 + 15.0) / 4)  # 3:1 blend = 6.0
        self.assertEqual(m.source, "models.dev")
        self.assertEqual(m.observed_at, "2026-06-07")

    def test_handles_missing_models_key(self):
        out = pricing.parse_modelsdev_payload({"p": {"name": "P"}}, observed_at="2026-06-07")
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
