import unittest
from collections import Counter
from pathlib import Path

from src.relay.core import Relay, RelayStateError
from src.relay.models import CaseStatus


FIXTURE = Path(__file__).resolve().parents[1] / "demo-fixtures" / "sc-pipe-inspection" / "case.json"


class RelayWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.relay = Relay(FIXTURE)

    def run_to_supplemental_evidence(self):
        self.relay.issue_directive()
        self.relay.submit_round_1_claims()
        self.relay.raise_specialist_challenge()
        self.relay.apply_human_correction()
        self.relay.request_cross_check()
        self.relay.respond_to_cross_check()
        self.relay.submit_supplemental_evidence()

    def run_to_director_decision(self):
        self.run_to_supplemental_evidence()
        self.relay.record_director_decision()

    def test_complete_workflow_has_controlled_multi_round_events_and_report(self):
        self.run_to_director_decision()
        self.relay.approve_by_director()

        self.assertEqual(self.relay.case.status, CaseStatus.REPORT_DRAFTED)
        self.assertIn("已确认事实", self.relay.case.report_draft)
        self.assertIn(self.relay.case.trace_id, self.relay.case.report_draft)
        event_counts = Counter(message.event_type for message in self.relay.case.messages)
        required_events = {
            "issue.created",
            "directive.issued",
            "claim.submitted",
            "challenge.raised",
            "human.correction",
            "cross_check.requested",
            "cross_check.responded",
            "evidence.supplemented",
            "human.decision",
            "human.approval",
            "report.drafted",
        }
        self.assertTrue(required_events.issubset(event_counts))
        self.assertEqual(len(self.relay.case.messages), 12)

    def test_cross_check_is_relay_mediated_and_audited(self):
        self.run_to_supplemental_evidence()
        messages = self.relay.timeline_as_dicts()
        request = next(message for message in messages if message["event_type"] == "cross_check.requested")
        response = next(message for message in messages if message["event_type"] == "cross_check.responded")
        self.assertEqual(request["trace_id"], self.relay.case.trace_id)
        self.assertEqual(response["trace_id"], self.relay.case.trace_id)
        self.assertEqual(request["payload"]["transport"], "relay_mediated")
        self.assertEqual(response["payload"]["transport"], "relay_mediated")

    def test_report_requires_director_decision_and_approval(self):
        self.run_to_supplemental_evidence()
        with self.assertRaisesRegex(RelayStateError, "pending conclusion package"):
            self.relay.approve_by_director()
        with self.assertRaisesRegex(RelayStateError, "requires director approval"):
            self.relay.generate_report()

    def test_package_only_contains_adopted_ledger_entries(self):
        self.run_to_director_decision()
        package = self.relay.case.pending_conclusion_package
        adopted_refs = {
            ref
            for item in self.relay.case.decision_ledger
            if item["status"] == "adopted"
            for ref in item["evidence_refs"]
        }
        excluded_text = " ".join(
            item["decision_item"]
            for item in self.relay.case.decision_ledger
            if item["status"] in ("rejected", "pending")
        )
        self.assertTrue(set(package["evidence_refs"]).issubset(adopted_refs))
        self.assertFalse(any(item in " ".join(package["approved_facts"]) for item in excluded_text.split(" ")))

    def test_approved_package_is_created_only_after_human_approval(self):
        self.run_to_director_decision()
        self.assertIsNone(self.relay.case.approved_conclusion_package)
        self.assertIsNotNone(self.relay.case.pending_conclusion_package)
        self.relay.approve_by_director()
        self.assertEqual(
            self.relay.case.approved_conclusion_package,
            self.relay.case.pending_conclusion_package,
        )

    def test_controlled_stages_cannot_be_replayed(self):
        self.relay.issue_directive()
        self.relay.submit_round_1_claims()
        with self.assertRaises(RelayStateError):
            self.relay.submit_round_1_claims()
        self.relay.raise_specialist_challenge()
        self.relay.apply_human_correction()
        self.relay.request_cross_check()
        self.relay.respond_to_cross_check()
        with self.assertRaisesRegex(RelayStateError, "already been submitted"):
            self.relay.respond_to_cross_check()
        self.relay.submit_supplemental_evidence()
        self.relay.record_director_decision()
        with self.assertRaisesRegex(RelayStateError, "already been recorded"):
            self.relay.record_director_decision()

    def test_compatibility_entry_points_complete_the_new_flow(self):
        self.relay.run_round_1()
        self.assertEqual(self.relay.case.status, CaseStatus.AWAITING_HUMAN_CORRECTION)
        self.relay.apply_human_correction()
        self.relay.run_round_2()
        self.assertTrue(self.relay.case.decision_ledger)
        self.assertIsNotNone(self.relay.case.pending_conclusion_package)
        self.relay.approve_by_director()
        self.assertEqual(self.relay.case.status, CaseStatus.REPORT_DRAFTED)

    def test_reset_clears_new_state_and_report(self):
        self.run_to_director_decision()
        self.relay.approve_by_director()
        self.relay.reset_case()

        self.assertEqual(self.relay.case.status, CaseStatus.NEW)
        self.assertEqual(self.relay.case.current_round, 0)
        self.assertEqual(len(self.relay.case.messages), 1)
        self.assertIsNone(self.relay.case.proposed_conclusion)
        self.assertEqual(self.relay.case.decision_ledger, [])
        self.assertIsNone(self.relay.case.pending_conclusion_package)
        self.assertIsNone(self.relay.case.approved_conclusion_package)
        self.assertIsNone(self.relay.case.report_draft)

    def test_every_message_has_the_contract_fields(self):
        self.run_to_director_decision()
        self.relay.approve_by_director()
        required_fields = {
            "message_id", "trace_id", "round", "sender", "receiver", "event_type",
            "payload", "evidence_refs", "requires_human_approval", "status", "timestamp",
        }
        for message in self.relay.timeline_as_dicts():
            self.assertTrue(required_fields.issubset(message))


if __name__ == "__main__":
    unittest.main()
