"""Automated evaluation harness for Sampark's real LLM reasoning layer.

Unlike tests/ (79 tests, all offline against StubProviderClient), this
script runs REAL LLM calls against every mock customer scenario and
reports quality/latency/cost metrics -- mirroring the "Automated
Evaluation Benchmark" pattern from the sibling CineAgent project, but
reusing the score Sampark's own independent verifier already computes as
part of normal operation, rather than paying for a second separate judge
call per action.

Usage:
    python -m sampark.evaluation.benchmark --customers all --delay 15
    python -m sampark.evaluation.benchmark --customers c001,c003,c007

Requires a real ANTHROPIC_API_KEY and/or GEMINI_API_KEY -- this measures
real narration quality, so it cannot run in offline/stub mode.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer, list_customers
from sampark.llm.factory import build_default_reasoning_engine
from sampark.llm.memory import EpisodicMemory

RESULTS_DIR = Path(__file__).parent / "results"
ACCEPT_THRESHOLD = 85

# Expected outcome per mock customer, per the Demo Scenario Catalog in
# README.md -- "ready" means at least one step should reach
# ready_for_bank_mitra_confirmation (verification passes); "blocked" means
# the compliance gate should stop the journey (verification fails). This
# is already proven deterministically by tests/test_sampark.py -- here
# it's re-checked live as a regression guard while measuring LLM quality
# on top of it, not as the benchmark's primary claim.
EXPECTED_OUTCOME = {
    "c001": "ready",
    "c002": "ready",
    "c003": "blocked",
    "c004": "ready",
    "c005": "ready",
    "c006": "blocked",
    "c007": "blocked",
    "c008": "blocked",
    "c009": "ready",
    "c010": "ready",
}


@dataclass
class ScenarioResult:
    customer_id: str
    customer_name: str
    expected_outcome: str
    actual_outcome: str
    scenario_correct: bool
    step_count: int
    narrated_step_count: int
    accepted_step_count: int
    narration_scores: list[int] = field(default_factory=list)
    narration_rounds: list[int] = field(default_factory=list)
    latency_seconds: float = 0.0
    llm_calls: int = 0
    llm_cost_usd: float = 0.0
    error: Optional[str] = None


def _score_step(step) -> Optional[int]:
    trace = step.payload.get("reasoning_trace")
    if not trace:
        return None
    return trace[-1].get("score")


def run_benchmark(customer_ids: list[str], delay_seconds: float) -> dict[str, Any]:
    reasoning_engine = build_default_reasoning_engine()
    if reasoning_engine is None:
        raise SystemExit(
            "No LLM provider configured (set ANTHROPIC_API_KEY and/or GEMINI_API_KEY) -- "
            "the benchmark measures real LLM narration quality and cannot run in stub/offline mode."
        )

    bank_mitra = get_bank_mitra()
    results: list[ScenarioResult] = []

    for index, customer_id in enumerate(customer_ids):
        customer = get_customer(customer_id)
        usage_before = reasoning_engine.usage_summary()
        start = time.monotonic()
        try:
            orchestrator = SamparkOrchestrator(
                reasoning_engine=reasoning_engine, episodic_memory=EpisodicMemory(":memory:")
            )
            run = orchestrator.run(customer, bank_mitra)
            latency = time.monotonic() - start
            usage_after = reasoning_engine.usage_summary()

            expected_outcome = EXPECTED_OUTCOME.get(customer_id, "ready")
            actual_outcome = "ready" if run.verification.get("passed") else "blocked"

            narration_scores = [s for s in (_score_step(step) for step in run.steps) if s is not None]
            narration_rounds = [
                len(step.payload["reasoning_trace"]) for step in run.steps if step.payload.get("reasoning_trace")
            ]
            narrated_count = sum(1 for step in run.steps if step.payload.get("reasoning_trace"))
            accepted_count = sum(1 for score in narration_scores if score >= ACCEPT_THRESHOLD)

            results.append(
                ScenarioResult(
                    customer_id=customer_id,
                    customer_name=customer.name,
                    expected_outcome=expected_outcome,
                    actual_outcome=actual_outcome,
                    scenario_correct=(actual_outcome == expected_outcome),
                    step_count=len(run.steps),
                    narrated_step_count=narrated_count,
                    accepted_step_count=accepted_count,
                    narration_scores=narration_scores,
                    narration_rounds=narration_rounds,
                    latency_seconds=round(latency, 2),
                    llm_calls=usage_after["total_calls"] - usage_before["total_calls"],
                    llm_cost_usd=round(usage_after["total_cost_usd"] - usage_before["total_cost_usd"], 6),
                )
            )
        except Exception as exc:  # one bad scenario must never kill the whole benchmark run
            results.append(
                ScenarioResult(
                    customer_id=customer_id,
                    customer_name=customer.name,
                    expected_outcome=EXPECTED_OUTCOME.get(customer_id, "ready"),
                    actual_outcome="error",
                    scenario_correct=False,
                    step_count=0,
                    narrated_step_count=0,
                    accepted_step_count=0,
                    error=str(exc),
                )
            )

        if index < len(customer_ids) - 1:
            time.sleep(delay_seconds)

    return summarize(results)


def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
    total = len(results)
    correct = sum(1 for r in results if r.scenario_correct)
    all_scores = [score for r in results for score in r.narration_scores]
    all_rounds = [rounds for r in results for rounds in r.narration_rounds]
    total_narrated = sum(r.narrated_step_count for r in results)
    total_accepted = sum(r.accepted_step_count for r in results)
    total_cost = sum(r.llm_cost_usd for r in results)
    total_calls = sum(r.llm_calls for r in results)
    latencies = sorted(r.latency_seconds for r in results if r.error is None)

    p95_latency = None
    if latencies:
        p95_index = max(0, int(len(latencies) * 0.95) - 1)
        p95_latency = latencies[p95_index]

    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenarios_tested": total,
        "scenario_correctness_rate": round(correct / total, 3) if total else 0.0,
        "narration_acceptance_rate": round(total_accepted / total_narrated, 3) if total_narrated else None,
        "avg_narration_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        "avg_rounds_to_resolution": round(sum(all_rounds) / len(all_rounds), 2) if all_rounds else None,
        "avg_latency_seconds": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p95_latency_seconds": p95_latency,
        "total_llm_calls": total_calls,
        "total_llm_cost_usd": round(total_cost, 6),
        "scenarios": [asdict(r) for r in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Project Sampark's live LLM-quality benchmark.")
    parser.add_argument(
        "--customers",
        default="all",
        help="Comma-separated customer IDs (e.g. c001,c003) or 'all' for all 10 mock scenarios.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=15.0,
        help="Seconds to wait between scenarios -- keep this high on free-tier LLM quotas (default 15s).",
    )
    args = parser.parse_args()

    if args.customers == "all":
        customer_ids = [c.customer_id for c in list_customers()]
    else:
        customer_ids = [c.strip() for c in args.customers.split(",")]

    summary = run_benchmark(customer_ids, args.delay)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"benchmark_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    output_path.write_text(json.dumps(summary, indent=2))

    print(f"\nScenarios tested: {summary['scenarios_tested']}")
    print(f"Scenario correctness rate: {summary['scenario_correctness_rate'] * 100:.0f}%")
    if summary["narration_acceptance_rate"] is not None:
        print(f"Narration acceptance rate: {summary['narration_acceptance_rate'] * 100:.0f}%")
    print(f"Avg narration score: {summary['avg_narration_score']}")
    print(f"Avg rounds to resolution: {summary['avg_rounds_to_resolution']}")
    print(f"Avg latency: {summary['avg_latency_seconds']}s (p95: {summary['p95_latency_seconds']}s)")
    print(f"Total LLM cost: ${summary['total_llm_cost_usd']:.4f} across {summary['total_llm_calls']} calls")
    print(f"Full results written to {output_path}")


if __name__ == "__main__":
    main()
