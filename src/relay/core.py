import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

from src.relay.models import Actor, CaseStatus, Message, RelayCase
from src.reporting.draft import render_markdown_report
from src.reporting.llm import build_approved_report_package, load_local_env, request_deepseek_report


class RelayStateError(RuntimeError):
    pass


class Relay:
    """Deterministic Relay for the anonymized, human-controlled demo scenario."""

    def __init__(self, fixture_path: Path, enable_live_llm: bool = False):
        self.fixture_path = Path(fixture_path)
        self.enable_live_llm = enable_live_llm
        self.case = None
        self.reset_case()

    def reset_case(self) -> RelayCase:
        with self.fixture_path.open(encoding="utf-8") as fixture_file:
            fixture = json.load(fixture_file)
        self.case = RelayCase(trace_id=fixture["trace_id"], title=fixture["title"], fixture=fixture)
        self._append_storyboard_message(1)
        return self.case

    # Fine-grained workflow stages. These are the future UI controls.
    def issue_directive(self) -> RelayCase:
        self._require_status(CaseStatus.NEW, "Director directive requires a reset case")
        self._append_storyboard_message(2)
        self.case.status = CaseStatus.DISPATCHED
        return self.case

    def submit_round_1_claims(self) -> RelayCase:
        self._require_status(CaseStatus.DISPATCHED, "Round 1 claims require a director directive")
        self._require_event_absent("claim.submitted", "Round 1 claims have already been submitted")
        self.case.current_round = 1
        self.case.status = CaseStatus.EVIDENCE_COLLECTING
        self._append_storyboard_message(3)
        self._append_storyboard_message(4)
        return self.case

    def raise_specialist_challenge(self) -> RelayCase:
        self._require_status(CaseStatus.EVIDENCE_COLLECTING, "A challenge requires both initial specialist claims")
        self._append_storyboard_message(5)
        self.case.status = CaseStatus.AWAITING_HUMAN_CORRECTION
        return self.case

    def apply_human_correction(self) -> RelayCase:
        self._require_status(
            CaseStatus.AWAITING_HUMAN_CORRECTION,
            "Human correction is required after the specialist challenge",
        )
        self._append_storyboard_message(6)
        self.case.status = CaseStatus.CLARIFICATION_REQUIRED
        return self.case

    def request_cross_check(self) -> RelayCase:
        self._require_status(CaseStatus.CLARIFICATION_REQUIRED, "Cross-check requires an explicit human correction")
        self.case.current_round = 2
        self._append_storyboard_message(7)
        self.case.status = CaseStatus.EVIDENCE_COLLECTING
        return self.case

    def respond_to_cross_check(self) -> RelayCase:
        self._require_status(CaseStatus.EVIDENCE_COLLECTING, "Cross-check response requires a routed request")
        self._require_event_present("cross_check.requested", "Cross-check response requires a routed request")
        self._require_event_absent("cross_check.responded", "Cross-check response has already been submitted")
        self._append_storyboard_message(8)
        return self.case

    def submit_supplemental_evidence(self) -> RelayCase:
        self._require_status(CaseStatus.EVIDENCE_COLLECTING, "Supplemental evidence requires a routed cross-check")
        self._require_event_present("cross_check.responded", "Supplemental evidence requires a cross-check response")
        self._require_event_absent("evidence.supplemented", "Supplemental evidence has already been submitted")
        self._append_storyboard_message(9)
        self.case.status = CaseStatus.HUMAN_CONFIRMATION
        return self.case

    def record_director_decision(self) -> RelayCase:
        self._require_status(
            CaseStatus.HUMAN_CONFIRMATION,
            "Director decision requires completed supplemental evidence",
        )
        if self.case.pending_conclusion_package:
            raise RelayStateError("Director decision has already been recorded")
        design = self._design()
        self.case.decision_ledger = [dict(item) for item in design["decision_ledger"]]
        self.case.pending_conclusion_package = self._build_pending_package()
        self.case.proposed_conclusion = self._compatibility_conclusion()
        self._append_message(
            round_number=2,
            sender=Actor("director_human", "human_adapter"),
            receiver=Actor("relay", "local"),
            event_type="human.decision",
            payload={
                "summary": "总监已完成 adopted、rejected、pending 裁决；仅 adopted 项可进入待批准结论包。",
                "decision_ledger": self.case.decision_ledger,
            },
            evidence_refs=list(self.case.pending_conclusion_package["evidence_refs"]),
            requires_human_approval=True,
        )
        return self.case

    def approve_by_director(self) -> RelayCase:
        self._require_status(
            CaseStatus.HUMAN_CONFIRMATION,
            "Director approval requires a recorded director decision",
        )
        if not self.case.pending_conclusion_package:
            raise RelayStateError("Director approval requires a director decision and pending conclusion package")
        self.case.approved_conclusion_package = dict(self.case.pending_conclusion_package)
        approval = self._storyboard_item(10)
        self._append_message(
            round_number=approval["round"],
            sender=Actor("director_human", "human_adapter"),
            receiver=Actor("relay", "local"),
            event_type="human.approval",
            payload={"summary": approval["summary"]},
            evidence_refs=list(self.case.approved_conclusion_package["evidence_refs"]),
            requires_human_approval=True,
        )
        self.case.status = CaseStatus.APPROVED
        self.generate_report()
        return self.case

    # Compatibility entry points for the current Streamlit controls.
    def run_round_1(self) -> RelayCase:
        self.issue_directive()
        self.submit_round_1_claims()
        return self.raise_specialist_challenge()

    def run_round_2(self) -> RelayCase:
        self.request_cross_check()
        self.respond_to_cross_check()
        self.submit_supplemental_evidence()
        return self.record_director_decision()

    def generate_report(self) -> str:
        self._require_status(CaseStatus.APPROVED, "Report generation requires director approval")
        if not self.case.approved_conclusion_package:
            raise RelayStateError("Report generation requires an adopted conclusion package")

        package = build_approved_report_package(
            self.case.trace_id,
            self.case.title,
            self.case.approved_conclusion_package,
        )
        fallback_draft = render_markdown_report(self.case.trace_id, self.case.title, package)
        if not self.enable_live_llm:
            self.case.report_draft = fallback_draft
            self.case.report_source = "Mock 回退"
            self.case.report_fallback_reason = "当前运行配置未启用真实 LLM。"
            report_adapter = "mock_fallback"
        else:
            load_local_env(self.fixture_path.parent.parent.parent / ".env")
            try:
                self.case.report_draft = request_deepseek_report(package)
                self.case.report_source = "真实 LLM"
                self.case.report_fallback_reason = None
                report_adapter = "deepseek_api"
            except RuntimeError as error:
                self.case.report_draft = fallback_draft
                self.case.report_source = "Mock 回退"
                self.case.report_fallback_reason = str(error)
                report_adapter = "mock_fallback"
        self._append_message(
            round_number=2,
            sender=Actor("report_agent", report_adapter),
            receiver=Actor("director_human", "human_adapter"),
            event_type="report.drafted",
            payload={"title": self.case.title, "format": "markdown", "source": self.case.report_source},
            evidence_refs=list(package["evidence_refs"]),
            requires_human_approval=False,
        )
        self.case.status = CaseStatus.REPORT_DRAFTED
        return self.case.report_draft

    def timeline_as_dicts(self) -> List[Dict[str, Any]]:
        return [message.as_dict() for message in self.case.messages]

    def _design(self) -> Dict[str, Any]:
        return self.case.fixture["next_iteration_design"]

    def _append_storyboard_message(self, sequence: int) -> Message:
        item = self._storyboard_item(sequence)
        adapter = "human_adapter" if item["sender"] == "director_human" else "mock"
        if item["sender"] == "owner":
            adapter = "mock_ingress"
        payload = {"summary": item["summary"]}
        if "transport" in item:
            payload["transport"] = item["transport"]
        return self._append_message(
            round_number=item["round"],
            sender=Actor(item["sender"], adapter),
            receiver=Actor(item["receiver"], "local" if item["receiver"] == "relay" else "mock"),
            event_type=item["event_type"],
            payload=payload,
            evidence_refs=item["evidence_refs"],
            requires_human_approval=item["requires_human_control"],
        )

    def _storyboard_item(self, sequence: int) -> Dict[str, Any]:
        item = next(
            (entry for entry in self._design()["message_storyboard"] if entry["sequence"] == sequence),
            None,
        )
        if not item:
            raise RelayStateError("Missing storyboard message sequence {0}".format(sequence))
        return item

    def _build_pending_package(self) -> Dict[str, Any]:
        ledger = self.case.decision_ledger or self._design()["decision_ledger"]
        adopted_refs = []
        for item in ledger:
            if item["status"] == "adopted":
                for evidence_ref in item["evidence_refs"]:
                    if evidence_ref not in adopted_refs:
                        adopted_refs.append(evidence_ref)
        design_package = self._design()["approved_conclusion_package"]
        package = {
            "approved_facts": list(design_package["approved_facts"]),
            "approved_conclusion": design_package["approved_conclusion"],
            "evidence_refs": list(design_package["evidence_refs"]),
        }
        if not set(package["evidence_refs"]).issubset(set(adopted_refs)):
            raise RelayStateError("Approved package contains non-adopted evidence")
        return package

    def _compatibility_conclusion(self) -> Dict[str, Any]:
        package = self.case.pending_conclusion_package
        return {
            "confirmed_facts": list(package["approved_facts"]),
            "evidence_refs": list(package["evidence_refs"]),
            "proposed_conclusion": package["approved_conclusion"],
            "pending_human_confirmation": True,
        }

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

    def _require_event_present(self, event_type: str, error_message: str) -> None:
        if not any(message.event_type == event_type for message in self.case.messages):
            raise RelayStateError(error_message)

    def _require_event_absent(self, event_type: str, error_message: str) -> None:
        if any(message.event_type == event_type for message in self.case.messages):
            raise RelayStateError(error_message)
