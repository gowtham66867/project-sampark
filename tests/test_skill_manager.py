from __future__ import annotations

import unittest

from sampark.core.models import Customer
from sampark.skills.skill_manager import SkillManager


def _customer(**overrides):
    base = dict(
        customer_id="c999",
        name="Test Customer",
        village="Testville",
        language="Hindi",
        segment="PMJDY customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="inactive",
        upi_status="inactive",
        digital_txn_count=0,
        products=[],
        consent=True,
    )
    base.update(overrides)
    return Customer(**base)


class SkillManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = SkillManager()

    def test_all_six_playbooks_are_discovered(self):
        expected = {
            "pmjdy_first_activation",
            "dormant_reactivation",
            "merchant_qr_onboarding",
            "senior_citizen_yono",
            "rd_suitability_offer",
            "low_connectivity_assisted_save",
        }
        self.assertEqual(set(self.manager.list_skills()), expected)

    def test_generic_customer_gets_pmjdy_skill_for_upi_activation(self):
        skill = self.manager.select_skill("UPI activation", _customer())
        self.assertEqual(skill.skill_id, "pmjdy_first_activation")

    def test_dormant_reactivation_matches_account_reactivation_title(self):
        skill = self.manager.select_skill("Account reactivation", _customer())
        self.assertEqual(skill.skill_id, "dormant_reactivation")

    def test_merchant_qr_title_matches_merchant_skill(self):
        skill = self.manager.select_skill("Merchant QR onboarding", _customer())
        self.assertEqual(skill.skill_id, "merchant_qr_onboarding")

    def test_rd_offer_title_matches_suitability_skill(self):
        skill = self.manager.select_skill("Next-best product", _customer())
        self.assertEqual(skill.skill_id, "rd_suitability_offer")

    def test_senior_citizen_segment_overrides_generic_yono_skill(self):
        skill = self.manager.select_skill(
            "YONO onboarding", _customer(segment="Senior citizen pension customer")
        )
        self.assertEqual(skill.skill_id, "senior_citizen_yono")

    def test_low_connectivity_condition_overrides_generic_upi_skill(self):
        skill = self.manager.select_skill(
            "UPI activation", _customer(channel_conditions=["LOW_CONNECTIVITY"])
        )
        self.assertEqual(skill.skill_id, "low_connectivity_assisted_save")

    def test_unmatched_title_returns_none(self):
        skill = self.manager.select_skill("Unrelated action", _customer())
        self.assertIsNone(skill)


if __name__ == "__main__":
    unittest.main()
