from __future__ import annotations

import unittest

from sampark.evaluation.benchmark import ScenarioResult, summarize


def _result(**overrides):
    base = dict(
        customer_id="c001",
        customer_name="Test",
        expected_outcome="ready",
        actual_outcome="ready",
        scenario_correct=True,
        step_count=1,
        narrated_step_count=1,
        accepted_step_count=1,
        narration_scores=[90],
        narration_rounds=[1],
        latency_seconds=2.0,
        llm_calls=2,
        llm_cost_usd=0.001,
    )
    base.update(overrides)
    return ScenarioResult(**base)


class SummarizeTest(unittest.TestCase):
    def test_all_correct_scenarios_yield_full_correctness_rate(self):
        summary = summarize([_result(), _result(customer_id="c002")])
        self.assertEqual(summary["scenario_correctness_rate"], 1.0)
        self.assertEqual(summary["scenarios_tested"], 2)

    def test_one_incorrect_scenario_lowers_correctness_rate(self):
        summary = summarize(
            [_result(), _result(customer_id="c003", scenario_correct=False, actual_outcome="ready", expected_outcome="blocked")]
        )
        self.assertEqual(summary["scenario_correctness_rate"], 0.5)

    def test_narration_acceptance_rate_computed_across_all_steps(self):
        summary = summarize(
            [
                _result(narrated_step_count=2, accepted_step_count=1),
                _result(customer_id="c002", narrated_step_count=2, accepted_step_count=2),
            ]
        )
        # 3 accepted out of 4 narrated steps total
        self.assertEqual(summary["narration_acceptance_rate"], 0.75)

    def test_cost_and_call_totals_are_summed(self):
        summary = summarize([_result(llm_cost_usd=0.001, llm_calls=2), _result(llm_cost_usd=0.002, llm_calls=3)])
        self.assertAlmostEqual(summary["total_llm_cost_usd"], 0.003, places=6)
        self.assertEqual(summary["total_llm_calls"], 5)

    def test_errored_scenario_excluded_from_latency_stats_but_counted_as_incorrect(self):
        summary = summarize(
            [_result(), _result(customer_id="c999", actual_outcome="error", scenario_correct=False, error="boom", latency_seconds=0.0)]
        )
        self.assertEqual(summary["scenarios_tested"], 2)
        self.assertEqual(summary["scenario_correctness_rate"], 0.5)
        # Only the non-errored scenario's latency (2.0s) should count.
        self.assertEqual(summary["avg_latency_seconds"], 2.0)

    def test_empty_results_do_not_divide_by_zero(self):
        summary = summarize([])
        self.assertEqual(summary["scenarios_tested"], 0)
        self.assertEqual(summary["scenario_correctness_rate"], 0.0)
        self.assertIsNone(summary["avg_narration_score"])
        self.assertIsNone(summary["avg_latency_seconds"])


if __name__ == "__main__":
    unittest.main()
