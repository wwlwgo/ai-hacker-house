from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CaseStatus(str, Enum):
    NEW = "NEW"
    DISPATCHED = "DISPATCHED"
    EVIDENCE_COLLECTING = "EVIDENCE_COLLECTING"
    AWAITING_HUMAN_CORRECTION = "AWAITING_HUMAN_CORRECTION"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    APPROVED = "APPROVED"
    REPORT_DRAFTED = "REPORT_DRAFTED"


@dataclass(frozen=True)
class Actor:
    role: str
    adapter: str = "mock"


@dataclass
class Message:
    message_id: str
    trace_id: str
    round: int
    sender: Actor
    receiver: Actor
    event_type: str
    payload: Dict[str, Any]
    evidence_refs: List[str]
    requires_human_approval: bool
    status: str
    timestamp: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelayCase:
    trace_id: str
    title: str
    fixture: Dict[str, Any]
    status: CaseStatus = CaseStatus.NEW
    current_round: int = 0
    messages: List[Message] = field(default_factory=list)
    proposed_conclusion: Optional[Dict[str, Any]] = None
    report_draft: Optional[str] = None
    report_source: Optional[str] = None
    report_fallback_reason: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.fromisoformat("2026-08-02T12:00:00+08:00"))
