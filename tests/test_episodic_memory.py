from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sampark.core.models import AgentAction, AuditEvent, BankMitra, Customer, SamparkRun
from sampark.llm.memory import EpisodicMemory


def _customer(**overrides):
    base = dict(
        customer_id="c001",
        name="Sita Devi",
        village="Rampur",
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


def _mitra():
    return BankMitra(mitra_id="bm-1", name="Anil Prasad", outlet="SBI CSP Rampur", language="Hindi")


def _run(audit_id="SAM-AAAAAAAA", language="Hindi", passed=True, blocked_titles=None):
    blocked_titles = blocked_titles or []
    steps = [
        AgentAction(
            agent="Digital Adoption Agent",
            title="UPI activation",
            detail="detail",
            status="blocked" if "UPI activation" in blocked_titles else "ready_for_bank_mitra_confirmation",
        )
    ]
    return SamparkRun(
        customer=_customer(language=language),
        bank_mitra=_mitra(),
        intent="digital adoption",
        goal="Activate UPI",
        steps=steps,
        verification={"passed": passed},
        outcome={"journey_status": "ready_for_assisted_submission" if passed else "requires_human_resolution"},
        audit_id=audit_id,
        audit_timeline=[AuditEvent(stage="Listen", message="x")],
    )


class EpisodicMemoryTest(unittest.TestCase):
    def test_record_returns_same_shape_as_legacy_learning_store(self):
        memory = EpisodicMemory(":memory:")
        result = memory.record(_run())
        self.assertEqual(
            set(result.keys()),
            {"runs_recorded", "completed_or_ready_steps", "blocked_steps", "language_mix", "learning_signal"},
        )

    def test_language_mix_accumulates_across_multiple_records_same_instance(self):
        memory = EpisodicMemory(":memory:")
        first = memory.record(_run(audit_id="SAM-11111111", language="Hindi"))
        second = memory.record(_run(audit_id="SAM-22222222", language="Kannada"))

        self.assertEqual(first["runs_recorded"], 1)
        self.assertEqual(second["runs_recorded"], 2)
        self.assertEqual(second["language_mix"], {"Hindi": 1, "Kannada": 1})

    def test_persists_across_reopen_when_file_backed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "learning.sqlite3")
            memory = EpisodicMemory(db_path)
            memory.record(_run(audit_id="SAM-33333333"))
            memory.close()

            reopened = EpisodicMemory(db_path)
            result = reopened.record(_run(audit_id="SAM-44444444"))
            self.assertEqual(result["runs_recorded"], 2)

    def test_skeletonize_does_not_include_raw_reasoning_trace_text(self):
        memory = EpisodicMemory(":memory:")
        run = _run()
        run.steps[0].payload["reasoning_trace"] = [{"draft": "x" * 5000}]
        memory.record(run)
        skeleton = memory._skeletonize(run)
        self.assertNotIn("reasoning_trace", skeleton["steps"][0])
        self.assertLess(len(str(skeleton)), 1000)

    def test_blocked_and_completed_counts_are_correct(self):
        memory = EpisodicMemory(":memory:")
        result = memory.record(_run(blocked_titles=["UPI activation"], passed=False))
        self.assertEqual(result["blocked_steps"], 1)
        self.assertEqual(result["completed_or_ready_steps"], 0)


if __name__ == "__main__":
    unittest.main()
