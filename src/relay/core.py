import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

from src.relay.mock_nodes import SPECIALIST_ROLES, reconcile, specialist_evidence
from src.relay.models import Actor, CaseStatus, Message, RelayCase
from src.reporting.draft import render_markdown_report


class RelayStateError(RuntimeError):
    pass


class Relay:
    def __init__(self, fixture_path: Path):
        self.fixture_path = Path(fixture_path)
        self.case = None
        self.reset_case()

    def reset_case(self) -> RelayCase:
        with self.fixture_path.open(encoding="utf-8") as fixture_file:
            fixture = json.load(fixture_file)
        self.case = RelayCase(trace_id=fixture["trace_id"], title=fixture["title"], fixture=fixture)
        self._append_message(
            round_number=0,
            sender=Actor("owner", "mock_ingress"),
            receiver=Actor("relay", "local"),
            event_type="issue.created",
            payload={"summary": fixture["initial_issue"]["summary"]},
            evidence_refs=fixture["initial_issue"]["evidence_refs"],
            requires_human_approval=fixture["initial_issue"]["requires_human_approval"],
        )
        return self.case

    def run_round_1(self) -> RelayCase:
        self._require_status(CaseStatus.NEW, "Round 1 can only start from a reset case")
        self.case.current_round = 1
        self.case.status = CaseStatus.DISPATCHED
        for role in SPECIALIST_ROLES:
            self._append_message(
                round_number=1,
                sender=Actor("relay", "local"),
                receiver=Actor(role),
                event_type="verification.requested",
                payload={"task": "核对对象、壁厚和适用依据；仅提交初步证据。"},
                evidence_refs=[],
                requires_human_approval=False,
            )

        self.case.status = CaseStatus.EVIDENCE_COLLECTING
        for role in SPECIALIST_ROLES:
            evidence = specialist_evidence(self.case.fixture, role, 1)
            self._append_message(
                round_number=1,
                sender=Actor(role),
                receiver=Actor("relay", "local"),
                event_type="evidence.submitted",
                payload=evidence,
                evidence_refs=evidence["evidence_refs"],
                requires_human_approval=False,
            )
        self.case.status = CaseStatus.AWAITING_HUMAN_CORRECTION
        return self.case

    def apply_human_correction(self) -> RelayCase:
        self._require_status(
            CaseStatus.AWAITING_HUMAN_CORRECTION,
            "Human correction is required after Round 1 before Round 2 can start",
        )
        correction = self.case.fixture["human_correction"]
        self._append_message(
            round_number=1,
            sender=Actor("director_human", "human_adapter"),
            receiver=Actor("relay", "local"),
            event_type=correction["event_type"],
            payload={"summary": correction["summary"], "effect": correction["effect"]},
            evidence_refs=[],
            requires_human_approval=True,
        )
        self.case.status = CaseStatus.CLARIFICATION_REQUIRED
        return self.case

    def run_round_2(self) -> RelayCase:
        self._require_status(
            CaseStatus.CLARIFICATION_REQUIRED,
            "Round 2 requires an explicit human correction",
        )
        self.case.current_round = 2
        for role in SPECIALIST_ROLES:
            self._append_message(
                round_number=2,
                sender=Actor("relay", "local"),
                receiver=Actor(role),
                event_type="clarification.requested",
                payload={"task": "补充照片对象识别及适用依据，不得沿用未经确认的第一轮前提。"},
                evidence_refs=[],
                requires_human_approval=False,
            )

        round_two_evidence = []
        for role in SPECIALIST_ROLES:
            evidence = specialist_evidence(self.case.fixture, role, 2)
            round_two_evidence.append(evidence)
            self._append_message(
                round_number=2,
                sender=Actor(role),
                receiver=Actor("relay", "local"),
                event_type="evidence.submitted",
                payload=evidence,
                evidence_refs=evidence["evidence_refs"],
                requires_human_approval=False,
            )

        self.case.proposed_conclusion = reconcile(round_two_evidence)
        self._append_message(
            round_number=2,
            sender=Actor("reconciler", "mock"),
            receiver=Actor("director_human", "human_adapter"),
            event_type="conclusion.proposed",
            payload=self.case.proposed_conclusion,
            evidence_refs=self.case.proposed_conclusion["evidence_refs"],
            requires_human_approval=True,
        )
        self.case.status = CaseStatus.HUMAN_CONFIRMATION
        return self.case

    def approve_by_director(self) -> RelayCase:
        self._require_status(
            CaseStatus.HUMAN_CONFIRMATION,
            "Director approval requires a proposed conclusion with complete evidence",
        )
        self._append_message(
            round_number=2,
            sender=Actor("director_human", "human_adapter"),
            receiver=Actor("relay", "local"),
            event_type="human.approval",
            payload={"summary": "总监确认拟定结论可用于生成演示报告草稿。"},
            evidence_refs=list(self.case.proposed_conclusion["evidence_refs"]),
            requires_human_approval=False,
        )
        self.case.status = CaseStatus.APPROVED
        self.generate_report()
        return self.case

    def generate_report(self) -> str:
        self._require_status(CaseStatus.APPROVED, "Report generation requires director approval")
        self.case.report_draft = render_markdown_report(
            self.case.trace_id,
            self.case.title,
            self.case.proposed_conclusion,
        )
        self._append_message(
            round_number=2,
            sender=Actor("report_agent", "mock"),
            receiver=Actor("director_human", "human_adapter"),
            event_type="report.drafted",
            payload={"title": self.case.title, "format": "markdown"},
            evidence_refs=list(self.case.proposed_conclusion["evidence_refs"]),
            requires_human_approval=False,
        )
        self.case.status = CaseStatus.REPORT_DRAFTED
        return self.case.report_draft

    def timeline_as_dicts(self) -> List[Dict[str, Any]]:
        return [message.as_dict() for message in self.case.messages]

    def _append_message(
        self,
        round_number: int,
        sender: Actor,
        receiver: Actor,
        event_type: str,
        payload: Dict[str, Any],
        evidence_refs: List[str],
        requires_human_approval: bool,
    ) -> Message:
        sequence = len(self.case.messages) + 1
        message = Message(
            message_id="{0}-msg-{1:03d}".format(self.case.trace_id, sequence),
            trace_id=self.case.trace_id,
            round=round_number,
            sender=sender,
            receiver=receiver,
            event_type=event_type,
            payload=payload,
            evidence_refs=list(evidence_refs),
            requires_human_approval=requires_human_approval,
            status="delivered",
            timestamp=(self.case.started_at + timedelta(seconds=sequence - 1)).isoformat(),
        )
        self.case.messages.append(message)
        return message

    def _require_status(self, expected: CaseStatus, error_message: str) -> None:
        if self.case.status != expected:
            raise RelayStateError("{0}; current status is {1}".format(error_message, self.case.status.value))
