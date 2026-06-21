from __future__ import annotations

from sampark.core.impact import project_impact
from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer


def print_run(customer_id: str = "c001") -> None:
    orchestrator = SamparkOrchestrator()
    run = orchestrator.run(get_customer(customer_id), get_bank_mitra())
    impact = project_impact()

    print("\nPROJECT SAMPARK - BANK MITRA AGENTIC COPILOT")
    print("=" * 56)
    print(f"Audit: {run.audit_id}")
    print(f"Bank Mitra: {run.bank_mitra.name} | {run.bank_mitra.outlet}")
    print(f"Customer: {run.customer.name} | {run.customer.village} | {run.customer.language}")
    print(f"Goal: {run.goal}\n")
    print("LISTEN -> PLAN -> CO-EXECUTE -> VERIFY -> LEARN")
    for index, step in enumerate(run.steps, start=1):
        print(f"{index}. [{step.status}] {step.agent}: {step.title}")
        print(f"   {step.detail}")
    print("\nVERIFY")
    print(f"Passed: {run.verification.get('passed')}")
    for warning in run.verification.get("warnings", []):
        print(f"Warning: {warning}")
    for blocked in run.verification.get("blocked", []):
        print(f"Blocked: {blocked}")
    print(f"\nOutcome: {run.outcome['journey_status']}")
    print(
        "Impact model: "
        f"{impact['annual_incremental_activations']:,} yearly activations, "
        f"~Rs {impact['annual_value_crore_rs']} crore/year illustrative value."
    )

