from typing import Any, Dict, List


SPECIALIST_ROLES = ("integrated_monitoring", "communications")


def specialist_evidence(fixture: Dict[str, Any], role: str, round_number: int) -> Dict[str, Any]:
    if role not in SPECIALIST_ROLES:
        raise ValueError("Unknown specialist role: {0}".format(role))
    if round_number not in (1, 2):
        raise ValueError("Mock specialists only support round 1 or 2")

    response = fixture["specialist_responses"][role]["round_{0}".format(round_number)]
    return {
        "claim": response["claim"],
        "confidence": response["confidence"],
        "is_preliminary": round_number == 1,
        "source": "fixture.specialist_responses.{0}.round_{1}".format(role, round_number),
        "evidence_refs": list(response["evidence_refs"]),
    }


def reconcile(round_two_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(round_two_evidence) != 2:
        raise ValueError("A proposed conclusion requires both specialist responses")
    if any(not item["evidence_refs"] for item in round_two_evidence):
        raise ValueError("A proposed conclusion requires evidence references")

    evidence_refs = []
    for item in round_two_evidence:
        for evidence_ref in item["evidence_refs"]:
            if evidence_ref not in evidence_refs:
                evidence_refs.append(evidence_ref)

    confirmed_facts = [
        "综合监控专业：{0}".format(round_two_evidence[0]["claim"]),
        "通信专业：{0}".format(round_two_evidence[1]["claim"]),
        "照片对象识别与适用依据已作为第二轮核查内容补充。",
    ]
    return {
        "confirmed_facts": confirmed_facts,
        "evidence_refs": evidence_refs,
        "proposed_conclusion": "两个专业节点已完成第二轮补充核查；以上内容仅为拟定结论，须经总监人工确认后方可用于报告草稿。",
        "pending_human_confirmation": True,
    }
