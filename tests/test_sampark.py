import unittest
from dataclasses import replace

from sampark.core.impact import project_impact
from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer, list_customers


def run_customer(customer_id):
    return SamparkOrchestrator().run(get_customer(customer_id), get_bank_mitra())


class SamparkTest(unittest.TestCase):
    def test_full_kyc_customer_gets_digital_adoption_plan(self):
        run = run_customer("c001")
        titles = [step.title for step in run.steps]
        self.assertIn("UPI activation", titles)
        self.assertIn("YONO onboarding", titles)
        self.assertTrue(run.verification["passed"])

    def test_min_kyc_customer_is_blocked_from_money_actions(self):
        run = run_customer("c003")
        blocked_steps = [step for step in run.steps if step.status == "blocked"]
        self.assertFalse(run.verification["passed"])
        self.assertTrue(blocked_steps)

    def test_impact_model_uses_submission_numbers(self):
        impact = project_impact()
        self.assertEqual(impact["outlets"], 82900)
        self.assertEqual(impact["annual_incremental_activations"], 7958400)
        self.assertEqual(impact["annual_value_crore_rs"], 478)

    def test_all_demo_customers_are_present(self):
        self.assertEqual(len(list_customers()), 10)

    def test_mock_customer_returns_deepcopy(self):
        customer = get_customer("c001")
        customer.name = "Changed"
        self.assertEqual(get_customer("c001").name, "Sita Devi")

    def test_unknown_customer_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_customer("missing")

    def test_consent_missing_stops_specialist_actions(self):
        run = run_customer("c006")
        self.assertFalse(run.verification["passed"])
        self.assertEqual(run.steps, [])
        self.assertIn("Customer consent missing", run.verification["blocked"][0])

    def test_suspicious_risk_blocks_digital_actions(self):
        run = run_customer("c007")
        self.assertFalse(run.verification["passed"])
        self.assertIn("Fraud/risk review", [item["name"] for item in run.verification["policy_checks"]])
        self.assertTrue(any(step.status == "blocked" for step in run.steps))

    def test_otp_failure_blocks_onboarding_restart(self):
        run = run_customer("c008")
        self.assertFalse(run.verification["passed"])
        self.assertIn("OTP and device readiness", [item["name"] for item in run.verification["policy_checks"]])

    def test_low_connectivity_adds_warning_without_blocking(self):
        run = run_customer("c009")
        self.assertTrue(run.verification["passed"])
        self.assertTrue(any("Low connectivity" in warning for warning in run.verification["warnings"]))

    def test_senior_citizen_adds_comprehension_warning(self):
        run = run_customer("c004")
        self.assertTrue(any("language comprehension" in warning for warning in run.verification["warnings"]))

    def test_merchant_customer_gets_qr_when_already_deepened(self):
        run = run_customer("c005")
        self.assertIn("Merchant QR onboarding", [step.title for step in run.steps])

    def test_digitally_active_customer_gets_rd_offer(self):
        run = run_customer("c010")
        self.assertEqual([step.title for step in run.steps], ["Next-best product"])

    def test_rd_offer_carries_mis_selling_control(self):
        run = run_customer("c010")
        self.assertIn("mis_selling_control", run.steps[0].payload)

    def test_each_action_has_reasoning_payload(self):
        run = run_customer("c001")
        for step in run.steps:
            self.assertIn("why_this_action", step.payload)
            self.assertIn("bank_mitra_must_verify", step.payload)

    def test_ready_steps_require_bank_mitra_confirmation(self):
        run = run_customer("c001")
        self.assertTrue(all(step.status == "ready_for_bank_mitra_confirmation" for step in run.steps))

    def test_blocked_steps_have_policy_payload(self):
        run = run_customer("c003")
        for step in run.steps:
            if step.status == "blocked":
                self.assertEqual(step.payload["guardrail_result"], "blocked_by_policy")

    def test_audit_timeline_contains_closed_loop_stages(self):
        run = run_customer("c001")
        stages = [event.stage for event in run.audit_timeline]
        self.assertEqual(stages, ["Listen", "Govern", "Plan", "Co-execute", "Verify", "Learn"])

    def test_blocked_journey_has_blocked_verify_event(self):
        run = run_customer("c003")
        verify_events = [event for event in run.audit_timeline if event.stage == "Verify"]
        self.assertEqual(verify_events[0].status, "blocked")

    def test_to_dict_includes_audit_timeline(self):
        payload = run_customer("c001").to_dict()
        self.assertIn("audit_timeline", payload)
        self.assertEqual(payload["audit_timeline"][0]["stage"], "Listen")

    def test_learning_records_language_mix(self):
        orchestrator = SamparkOrchestrator()
        first = orchestrator.run(get_customer("c001"), get_bank_mitra())
        second = orchestrator.run(get_customer("c002"), get_bank_mitra())
        self.assertEqual(first.outcome["learning"]["runs_recorded"], 1)
        self.assertEqual(second.outcome["learning"]["runs_recorded"], 2)
        self.assertIn("Kannada", second.outcome["learning"]["language_mix"])

    def test_planner_prioritizes_no_consent(self):
        run = run_customer("c006")
        self.assertEqual(run.goal, "Capture DPDP consent before any assisted banking journey.")

    def test_planner_prioritizes_risk_review(self):
        run = run_customer("c007")
        self.assertEqual(run.goal, "Pause digital activation and route the visit for Bank Mitra risk review.")

    def test_custom_customer_with_all_products_gets_deepening_goal(self):
        customer = replace(get_customer("c010"), products=["Savings Account", "UPI", "Recurring Deposit"])
        run = SamparkOrchestrator().run(customer, get_bank_mitra())
        self.assertEqual(run.goal, "Deepen engagement with the next relevant digital product.")

    def test_audit_id_has_expected_prefix(self):
        self.assertRegex(run_customer("c001").audit_id, r"^SAM-[0-9A-F]{8}$")

    def test_policy_checks_are_structured(self):
        run = run_customer("c001")
        first_check = run.verification["policy_checks"][0]
        self.assertIn("name", first_check)
        self.assertIn("status", first_check)
        self.assertIn("detail", first_check)


if __name__ == "__main__":
    unittest.main()
