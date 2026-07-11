from __future__ import annotations

import unittest

from sampark.llm.model_manager import (
    LLMProviderError,
    LLMResponse,
    ModelManager,
    RoleConfig,
)
from sampark.llm.stub_provider import StubProviderClient


def _response(provider="primary", model="model-a", text="ok"):
    return LLMResponse(
        text=text,
        provider=provider,
        model=model,
        input_tokens=1000,
        output_tokens=500,
        latency_ms=5,
    )


class ModelManagerCompleteTest(unittest.TestCase):
    def test_returns_response_on_first_success(self):
        stub = StubProviderClient(script=[_response()])
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(roles=roles, clients={"primary": stub}, sleep_fn=lambda s: None)

        result = manager.complete(
            "drafter", system="sys", messages=[{"role": "user", "content": "hi"}], trace_id="t1"
        )

        self.assertEqual(result.text, "ok")
        self.assertEqual(manager.usage_summary()["total_calls"], 1)

    def test_retries_on_retryable_error_then_succeeds(self):
        sleeps = []
        stub = StubProviderClient(
            script=[LLMProviderError("temporary", retryable=True), _response()]
        )
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(
            roles=roles, clients={"primary": stub}, sleep_fn=lambda s: sleeps.append(s)
        )

        result = manager.complete(
            "drafter", system=None, messages=[{"role": "user", "content": "hi"}], trace_id="t1"
        )

        self.assertEqual(result.text, "ok")
        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(len(sleeps), 1)

    def test_falls_back_to_next_provider_after_retries_exhausted(self):
        primary_stub = StubProviderClient(
            script=[LLMProviderError("down", retryable=True)] * 5
        )
        fallback_stub = StubProviderClient(script=[_response(provider="secondary", model="model-b")])
        roles = {
            "drafter": RoleConfig(
                provider="primary",
                model="model-a",
                max_tokens=100,
                fallback=[{"provider": "secondary", "model": "model-b"}],
            )
        }
        manager = ModelManager(
            roles=roles,
            clients={"primary": primary_stub, "secondary": fallback_stub},
            max_retries=2,
            sleep_fn=lambda s: None,
        )

        result = manager.complete(
            "drafter", system=None, messages=[{"role": "user", "content": "hi"}], trace_id="t1"
        )

        self.assertEqual(result.provider, "secondary")
        self.assertEqual(len(primary_stub.calls), 2)
        self.assertEqual(len(fallback_stub.calls), 1)

    def test_raises_when_all_providers_exhausted(self):
        stub = StubProviderClient(script=[LLMProviderError("down", retryable=True)] * 10)
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(
            roles=roles, clients={"primary": stub}, max_retries=2, sleep_fn=lambda s: None
        )

        with self.assertRaises(LLMProviderError):
            manager.complete(
                "drafter", system=None, messages=[{"role": "user", "content": "hi"}], trace_id="t1"
            )

    def test_does_not_retry_non_retryable_error(self):
        stub = StubProviderClient(
            script=[LLMProviderError("bad request", retryable=False), _response()]
        )
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(
            roles=roles, clients={"primary": stub}, max_retries=5, sleep_fn=lambda s: None
        )

        with self.assertRaises(LLMProviderError):
            manager.complete(
                "drafter", system=None, messages=[{"role": "user", "content": "hi"}], trace_id="t1"
            )
        # Only one attempt against the non-retryable failure -- no fallback
        # hop configured, so it should not have consumed the second script
        # entry either.
        self.assertEqual(len(stub.calls), 1)

    def test_usage_summary_aggregates_cost_and_tokens_across_calls(self):
        stub = StubProviderClient(
            script=[
                _response(text="one"),
                _response(text="two"),
            ]
        )
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        pricing = {"primary": {"model-a": {"input": 3.0, "output": 15.0}}}
        manager = ModelManager(
            roles=roles, clients={"primary": stub}, pricing=pricing, sleep_fn=lambda s: None
        )

        manager.complete("drafter", system=None, messages=[], trace_id="t1")
        manager.complete("drafter", system=None, messages=[], trace_id="t2")

        summary = manager.usage_summary()
        expected_cost_per_call = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        self.assertAlmostEqual(summary["total_cost_usd"], expected_cost_per_call * 2, places=6)
        self.assertEqual(summary["total_input_tokens"], 2000)
        self.assertEqual(summary["total_output_tokens"], 1000)
        self.assertEqual(summary["by_role"]["drafter"]["calls"], 2)

    def test_honors_provider_supplied_retry_after_hint_over_default_backoff(self):
        sleeps = []
        stub = StubProviderClient(
            script=[
                LLMProviderError("quota", retryable=True, retry_after_seconds=7.0),
                _response(),
            ]
        )
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(
            roles=roles,
            clients={"primary": stub},
            backoff_base_seconds=0.5,
            sleep_fn=lambda s: sleeps.append(s),
        )

        manager.complete("drafter", system=None, messages=[], trace_id="t1")

        # Default schedule would have slept 0.5s; the server's own 7s hint
        # must win since it reflects a real quota window, not a guess.
        self.assertEqual(sleeps, [7.0])

    def test_default_backoff_used_when_no_retry_after_hint(self):
        sleeps = []
        stub = StubProviderClient(
            script=[LLMProviderError("temporary", retryable=True), _response()]
        )
        roles = {"drafter": RoleConfig(provider="primary", model="model-a", max_tokens=100)}
        manager = ModelManager(
            roles=roles,
            clients={"primary": stub},
            backoff_base_seconds=0.5,
            sleep_fn=lambda s: sleeps.append(s),
        )

        manager.complete("drafter", system=None, messages=[], trace_id="t1")

        self.assertEqual(sleeps, [0.5])

    def test_gemini_fallback_skipped_when_client_not_registered(self):
        primary_stub = StubProviderClient(script=[LLMProviderError("down", retryable=True)] * 5)
        roles = {
            "drafter": RoleConfig(
                provider="primary",
                model="model-a",
                max_tokens=100,
                fallback=[{"provider": "gemini", "model": "gemini-model"}],
            )
        }
        manager = ModelManager(
            roles=roles,
            clients={"primary": primary_stub},  # no "gemini" entry registered
            max_retries=1,
            sleep_fn=lambda s: None,
        )

        with self.assertRaises(LLMProviderError):
            manager.complete("drafter", system=None, messages=[], trace_id="t1")


if __name__ == "__main__":
    unittest.main()
