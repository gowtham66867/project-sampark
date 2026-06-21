from __future__ import annotations

from uuid import uuid4

from sampark.agents.planner import choose_goal
from sampark.agents.specialists import adoption_agent, engagement_agent, onboarding_agent
from sampark.core.guardrails import consent_gate, verify_before_submit
from sampark.core.learning import LearningStore
from sampark.core.models import AuditEvent, BankMitra, Customer, SamparkRun


class SamparkOrchestrator:
    def __init__(self) -> None:
        self.learning_store = LearningStore()

    def run(self, customer: Customer, bank_mitra: BankMitra, intent: str = "digital adoption") -> SamparkRun:
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
            timeline.append(
                AuditEvent(
                    stage="Co-execute",
                    message=f"{len(steps)} specialist action(s) proposed.",
                    evidence={"agents": sorted({step.agent for step in steps})},
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
