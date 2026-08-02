import unittest
from collections import Counter
from pathlib import Path

from src.relay.core import Relay, RelayStateError
from src.relay.models import CaseStatus


FIXTURE = Path(__file__).resolve().parents[1] / "demo-fixtures" / "sc-pipe-inspection" / "case.json"


class RelayWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.relay = Relay(FIXTURE)

    def run_to_confirmation(self):
        self.relay.run_round_1()
        self.relay.apply_human_correction()
        self.relay.run_round_2()

    def test_complete_workflow_has_required_events_and_report(self):
        self.run_to_confirmation()
        self.relay.approve_by_director()

        self.assertEqual(self.relay.case.status, CaseStatus.REPORT_DRAFTED)
        self.assertIn("已确认事实", self.relay.case.report_draft)
        self.assertIn("总监已确认的拟定结论", self.relay.case.report_draft)
        self.assertIn(self.relay.case.trace_id, self.relay.case.report_draft)
        event_counts = Counter(message.event_type for message in self.relay.case.messages)
        self.assertEqual(event_counts["issue.created"], 1)
        self.assertEqual(event_counts["verification.requested"], 2)
        self.assertEqual(event_counts["evidence.submitted"], 4)
        self.assertEqual(event_counts["human.correction"], 1)
        self.assertEqual(event_counts["clarification.requested"], 2)
        self.assertEqual(event_counts["conclusion.proposed"], 1)
        self.assertEqual(event_counts["human.approval"], 1)
        self.assertEqual(event_counts["report.drafted"], 1)
        self.assertEqual(len(self.relay.case.messages), 13)

    def test_round_two_requires_human_correction(self):
        self.relay.run_round_1()
        with self.assertRaisesRegex(RelayStateError, "explicit human correction"):
            self.relay.run_round_2()

    def test_report_requires_director_approval(self):
        self.run_to_confirmation()
        with self.assertRaisesRegex(RelayStateError, "requires director approval"):
            self.relay.generate_report()

    def test_reset_restores_initial_message_and_state(self):
        self.run_to_confirmation()
        self.relay.reset_case()

        self.assertEqual(self.relay.case.status, CaseStatus.NEW)
        self.assertEqual(self.relay.case.current_round, 0)
        self.assertEqual(len(self.relay.case.messages), 1)
        self.assertEqual(self.relay.case.messages[0].event_type, "issue.created")
        self.assertIsNone(self.relay.case.proposed_conclusion)
        self.assertIsNone(self.relay.case.report_draft)

    def test_every_message_has_the_contract_fields(self):
        self.run_to_confirmation()
        self.relay.approve_by_director()
        required_fields = {
            "message_id",
            "trace_id",
            "round",
            "sender",
            "receiver",
            "event_type",
            "payload",
            "evidence_refs",
            "requires_human_approval",
            "status",
            "timestamp",
        }
        for message in self.relay.timeline_as_dicts():
            self.assertTrue(required_fields.issubset(message))


if __name__ == "__main__":
    unittest.main()
