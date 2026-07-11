from __future__ import annotations

import os
import unittest
from unittest import mock

from sampark.llm.providers import _extract_retry_delay_seconds, build_provider_clients


class ExtractRetryDelaySecondsTest(unittest.TestCase):
    def test_parses_gemini_style_retry_delay(self):
        error_text = (
            "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, "
            "'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
            "'retryDelay': '5s'}]}}"
        )
        self.assertEqual(_extract_retry_delay_seconds(error_text), 5.0)

    def test_parses_fractional_retry_delay(self):
        self.assertEqual(_extract_retry_delay_seconds("retryDelay: '5.69s'"), 5.69)

    def test_returns_none_when_no_hint_present(self):
        self.assertIsNone(_extract_retry_delay_seconds("some unrelated error text"))


class BuildProviderClientsTest(unittest.TestCase):
    def test_returns_empty_dict_when_no_keys_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            clients = build_provider_clients()
        self.assertEqual(clients, {})

    def test_builds_anthropic_client_when_key_present(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}, clear=True):
            clients = build_provider_clients()
        self.assertIn("anthropic", clients)
        self.assertNotIn("gemini", clients)

    def test_gemini_key_absent_means_gemini_client_absent(self):
        with mock.patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk-test-123", "GEMINI_API_KEY": ""}, clear=True
        ):
            clients = build_provider_clients()
        self.assertIn("anthropic", clients)
        self.assertNotIn("gemini", clients)


if __name__ == "__main__":
    unittest.main()
