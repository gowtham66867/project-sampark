from __future__ import annotations

import sys

from sampark.core.impact import project_impact
from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer
from sampark.llm.factory import build_default_reasoning_engine


def print_run(customer_id: str = "c001") -> None:
    # The CLI is a developer/offline demo tool, not the graded API surface
    # (see run_demo.py's /api/run, which hard-fails without an API key).
    # Here we still run in rule-based-only mode without a key, but print a
    # loud, unmissable warning so it's never mistaken for LLM output.
    reasoning_engine = build_default_reasoning_engine()
    if reasoning_engine is None:
        print(
            "WARNING: No LLM provider configured (set ANTHROPIC_API_KEY and/or "
            "GEMINI_API_KEY) -- printing RULE-BASED-ONLY output "
            "(no LLM narration, no reasoning trace).",
            file=sys.stderr,
        )

    orchestrator = SamparkOrchestrator(reasoning_engine=reasoning_engine)
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
        skill_used = step.payload.get("skill_used")
        if skill_used:
            print(f"   (skill: {skill_used})")
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
    if reasoning_engine is not None:
        usage = reasoning_engine.usage_summary()
        print(
            f"\nLLM usage this run: {usage['total_calls']} call(s), "
            f"${usage['total_cost_usd']:.4f}, "
            f"{usage['total_input_tokens']}+{usage['total_output_tokens']} tokens."
        )

