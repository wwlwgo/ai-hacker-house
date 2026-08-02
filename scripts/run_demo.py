import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.relay.core import Relay  # noqa: E402


FIXTURE = ROOT / "demo-fixtures" / "sc-pipe-inspection" / "case.json"


def print_status(relay: Relay, step: str) -> None:
    print("\n== {0} ==".format(step))
    print(
        "trace_id={0} | status={1} | round={2}".format(
            relay.case.trace_id,
            relay.case.status.value,
            relay.case.current_round,
        )
    )


def main() -> None:
    relay = Relay(FIXTURE)
    print_status(relay, "重置案例 / Round 0")

    relay.run_round_1()
    print_status(relay, "Round 1：总监指令、双专业初判与专业质疑")

    relay.apply_human_correction()
    print_status(relay, "Human Adapter：人工纠偏")

    relay.run_round_2()
    print_status(relay, "Round 2：跨专业核对、补证与总监裁决")
    print("\n事件序列：")
    for message in relay.case.messages:
        print("- R{0} | {1} -> {2} | {3}".format(
            message.round, message.sender.role, message.receiver.role, message.event_type
        ))
    print("\n结论裁决台账：")
    for item in relay.case.decision_ledger:
        print("- [{0}] {1}".format(item["status"], item["decision_item"]))
    print("\n待批准结论包：")
    print(json.dumps(relay.case.pending_conclusion_package, ensure_ascii=False, indent=2))

    relay.approve_by_director()
    print_status(relay, "总监批准并生成报告")
    print("\n已批准结论包：")
    print(json.dumps(relay.case.approved_conclusion_package, ensure_ascii=False, indent=2))
    print("\nMarkdown 报告草稿：\n")
    print(relay.case.report_draft)


if __name__ == "__main__":
    main()
