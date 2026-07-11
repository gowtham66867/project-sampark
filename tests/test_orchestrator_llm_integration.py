"""Integration tests for SamparkOrchestrator + ReasoningEngine wiring,
covering behavior that only shows up when multiple AgentActions are
narrated together (concurrency correctness) rather than one at a time
(already covered by tests/test_reasoning_engine.py)."""

from __future__ import annotations

import json
import unittest

from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer
from sampark.llm.model_manager import LLMResponse, ModelManager, RoleConfig
from sampark.llm.reasoning_engine import ReasoningEngine
from sampark.llm.stub_provider import StubProviderClient
from sampark.skills.skill_manager import SkillManager

ACCEPT_DRAFT = LLMResponse(
    text="Localized narration.",
    provider="draft",
    model="stub-draft",
    input_tokens=5,
    output_tokens=5,
    latency_ms=1,
)
ACCEPT_VERIFY = LLMResponse(
    text=json.dumps({"score": 95, "feedback": "Good."}),
    provider="verify",
    model="stub-verify",
    input_tokens=5,
    output_tokens=5,
    latency_ms=1,
)


def _engine_orchestrator() -> SamparkOrchestrator:
    draft_stub = StubProviderClient(provider_name="draft", script=[ACCEPT_DRAFT] * 20)
    verify_stub = StubProviderClient(provider_name="verify", script=[ACCEPT_VERIFY] * 20)
    roles = {
        "narrator_draft": RoleConfig(provider="draft", model="stub-draft", max_tokens=200),
        "narrator_verifier": RoleConfig(provider="verify", model="stub-verify", max_tokens=200),
    }
    model_manager = ModelManager(
        roles=roles, clients={"draft": draft_stub, "verify": verify_stub}, sleep_fn=lambda s: None
    )
    engine = ReasoningEngine(model_manager, SkillManager())
    return SamparkOrchestrator(reasoning_engine=engine)


class ParallelNarrationTest(unittest.TestCase):
    def test_multi_step_customer_gets_every_step_narrated_correctly(self):
        """c001 proposes 3 specialist actions (UPI activation, YONO
        onboarding, first digital transaction). Narrating them concurrently
        must not cross-assign one step's result to another step, nor drop
        any step's narration."""
        orchestrator = _engine_orchestrator()
        run = orchestrator.run(get_customer("c001"), get_bank_mitra())

        self.assertEqual(len(run.steps), 3)
        for step in run.steps:
            self.assertEqual(step.detail, "Localized narration.")
            self.assertEqual(step.payload["reasoning_trace"][-1]["score"], 95)
            self.assertIn("skill_used", step.payload)
            # Each step keeps its own identity -- title/agent are untouched
            # by the narration pass, only .detail/.payload change.
            self.assertIn(
                step.title,
                {"UPI activation", "YONO onboarding", "First digital transaction"},
            )

    def test_guardrails_still_run_after_parallel_narration_completes(self):
        """c003 (min-KYC) must still have its money actions blocked after
        the concurrent narration pass -- verify_before_submit always runs
        after ALL narration futures resolve, never interleaved with them."""
        orchestrator = _engine_orchestrator()
        run = orchestrator.run(get_customer("c003"), get_bank_mitra())

        blocked = [step for step in run.steps if step.status == "blocked"]
        self.assertTrue(blocked)
        for step in blocked:
            # Narration still ran (detail was rewritten)...
            self.assertEqual(step.detail, "Localized narration.")
            # ...but status is blocked regardless.
            self.assertEqual(step.payload["guardrail_result"], "blocked_by_policy")

    def test_single_step_customer_does_not_error_on_thread_pool_sizing(self):
        """c010 (digitally active saver) proposes exactly one action --
        exercises the ThreadPoolExecutor(max_workers=min(4, len(steps)))
        edge case at len(steps) == 1."""
        orchestrator = _engine_orchestrator()
        run = orchestrator.run(get_customer("c010"), get_bank_mitra())
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(run.steps[0].detail, "Localized narration.")

    def test_no_consent_customer_has_zero_steps_and_thread_pool_never_created(self):
        """c006 (no consent) must short-circuit before _narrate_steps is
        ever called -- confirmed by an empty steps list and no stub calls."""
        draft_stub = StubProviderClient(provider_name="draft", script=[ACCEPT_DRAFT] * 5)
        verify_stub = StubProviderClient(provider_name="verify", script=[ACCEPT_VERIFY] * 5)
        roles = {
            "narrator_draft": RoleConfig(provider="draft", model="stub-draft", max_tokens=200),
            "narrator_verifier": RoleConfig(provider="verify", model="stub-verify", max_tokens=200),
        }
        model_manager = ModelManager(
            roles=roles, clients={"draft": draft_stub, "verify": verify_stub}, sleep_fn=lambda s: None
        )
        engine = ReasoningEngine(model_manager, SkillManager())
        orchestrator = SamparkOrchestrator(reasoning_engine=engine)

        run = orchestrator.run(get_customer("c006"), get_bank_mitra())

        self.assertEqual(run.steps, [])
        self.assertEqual(len(draft_stub.calls), 0)


if __name__ == "__main__":
    unittest.main()
