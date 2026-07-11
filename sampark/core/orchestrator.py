from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from uuid import uuid4

from sampark.agents.planner import choose_goal
from sampark.agents.specialists import adoption_agent, engagement_agent, onboarding_agent
from sampark.core.guardrails import consent_gate, verify_before_submit
from sampark.core.models import AgentAction, AuditEvent, BankMitra, Customer, SamparkRun
from sampark.core.utils import new_trace_id
from sampark.llm.memory import EpisodicMemory
from sampark.llm.reasoning_engine import ReasoningEngine


class SamparkOrchestrator:
    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
    ) -> None:
        # Defaulting to an in-memory (":memory:") EpisodicMemory reproduces
        # the old in-process, per-instance-scoped LearningStore counting
        # behavior exactly -- every existing test constructs a fresh bare
        # SamparkOrchestrator(), so this keeps all of them passing
        # unmodified. run_demo.py explicitly injects a file-backed instance
        # so demo-run learning persists across requests within one server.
        self.learning_store = episodic_memory or EpisodicMemory(":memory:")
        self._reasoning_engine = reasoning_engine

    def run(self, customer: Customer, bank_mitra: BankMitra, intent: str = "digital adoption") -> SamparkRun:
        trace_id = new_trace_id()
        timeline: list[AuditEvent] = [
            AuditEvent(
                stage="Listen",
                message=f"Captured visit reason: {customer.visit_reason}.",
                evidence={"language": customer.language, "segment": customer.segment},
            )
        ]
        consent = consent_gate(customer)
        timeline.append(
            AuditEvent(
                stage="Govern",
                message=str(consent["reason"]),
                status="passed" if consent["passed"] else "blocked",
                evidence={"consent": customer.consent},
            )
        )
        goal = choose_goal(customer)
        timeline.append(
            AuditEvent(
                stage="Plan",
                message=goal,
                evidence={
                    "kyc_level": customer.kyc_level,
                    "account_status": customer.account_status,
                    "upi_status": customer.upi_status,
                    "yono_status": customer.yono_status,
                },
            )
        )
        steps = []

        if consent["passed"]:
            steps.extend(onboarding_agent(customer))
            steps.extend(adoption_agent(customer))
            steps.extend(engagement_agent(customer))
            if self._reasoning_engine is not None:
                # LLM narration runs strictly HERE: after the deterministic
                # specialist agents have decided which actions exist, and
                # BEFORE verify_before_submit runs below. It can only
                # rewrite step.detail/step.payload text -- it never touches
                # step.status, so guardrails.py remains the sole authority
                # on eligibility regardless of what the LLM writes.
                steps = self._narrate_steps(steps, customer, goal, trace_id)
            timeline.append(
                AuditEvent(
                    stage="Co-execute",
                    message=f"{len(steps)} specialist action(s) proposed.",
                    evidence={"agents": sorted({step.agent for step in steps}), "trace_id": trace_id},
                )
            )
        else:
            timeline.append(
                AuditEvent(
                    stage="Co-execute",
                    message="No specialist actions proposed because consent is blocked.",
                    status="blocked",
                )
            )

        verification = verify_before_submit(customer, steps) if consent["passed"] else consent
        timeline.append(
            AuditEvent(
                stage="Verify",
                message="Pre-submission checks passed." if verification["passed"] else "Pre-submission checks require human resolution.",
                status="passed" if verification["passed"] else "blocked",
                evidence={
                    "blocked": verification.get("blocked", []),
                    "warnings": verification.get("warnings", []),
                },
            )
        )
        outcome = {
            "journey_status": "ready_for_assisted_submission" if verification["passed"] else "requires_human_resolution",
            "north_star_metric": "digital products activated per outlet per month",
            "submission_note": "Prototype uses mocked SBI/AePS/YONO connectors; real deployment would run inside SBI VPC.",
        }
        run = SamparkRun(
            customer=customer,
            bank_mitra=bank_mitra,
            intent=intent,
            goal=goal,
            steps=steps,
            verification=verification,
            outcome=outcome,
            audit_id=f"SAM-{uuid4().hex[:8].upper()}",
            audit_timeline=timeline,
        )
        outcome["learning"] = self.learning_store.record(run)
        timeline.append(
            AuditEvent(
                stage="Learn",
                message="Outcome recorded for next-best-action tuning.",
                evidence=outcome["learning"],
            )
        )
        return run

    def _narrate_steps(
        self, steps: list[AgentAction], customer: Customer, goal: str, trace_id: str
    ) -> list[AgentAction]:
        """Runs ReasoningEngine.narrate_action per step, replacing ONLY
        step.detail and adding step.payload['reasoning_trace'] /
        ['skill_used']. Never touches step.status or step.agent -- there is
        no code path here through which LLM output could unblock an
        action. verify_before_submit (guardrails.py) always runs after this
        method returns and remains the sole authority on eligibility.

        Steps are narrated concurrently (one worker thread per step, up to
        4): each action's draft-verify-refine loop is fully independent of
        every other action's, so running them in parallel cuts the
        worst-case wall-clock time for a multi-step customer (e.g. 3
        proposed actions x up to 3 rounds x 2 calls each) roughly by the
        number of steps, instead of paying for it sequentially. Every
        thread only ever mutates its own AgentAction instance, so there is
        no shared mutable state to race on."""
        assert self._reasoning_engine is not None
        if not steps:
            return steps

        def _narrate_one(step: AgentAction) -> None:
            result = self._reasoning_engine.narrate_action(step, customer, goal, trace_id)
            step.detail = result.final_text
            step.payload["reasoning_trace"] = result.rounds
            step.payload["skill_used"] = result.skill_used

        with ThreadPoolExecutor(max_workers=min(4, len(steps))) as executor:
            futures = [executor.submit(_narrate_one, step) for step in steps]
            for future in futures:
                future.result()
        return steps
