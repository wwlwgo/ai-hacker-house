from html import escape
from pathlib import Path

import streamlit as st

from src.relay.core import Relay, RelayStateError
from src.relay.models import CaseStatus


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "demo-fixtures" / "sc-pipe-inspection" / "case.json"

STATUS_LABELS = {
    CaseStatus.NEW: "新建事项",
    CaseStatus.DISPATCHED: "已派发",
    CaseStatus.EVIDENCE_COLLECTING: "证据收集中",
    CaseStatus.AWAITING_HUMAN_CORRECTION: "等待人工纠偏",
    CaseStatus.CLARIFICATION_REQUIRED: "需要定向澄清",
    CaseStatus.HUMAN_CONFIRMATION: "待总监确认",
    CaseStatus.APPROVED: "已批准",
    CaseStatus.REPORT_DRAFTED: "报告草稿已生成",
}

ROLE_LABELS = {
    "owner": "发起方",
    "integrated_monitoring": "综合监控 Agent",
    "communications": "通信 Agent",
    "reconciler": "汇总 Agent",
    "director_human": "总监 Human Adapter",
}


def get_relay() -> Relay:
    if "relay" not in st.session_state:
        st.session_state.relay = Relay(FIXTURE, enable_live_llm=True)
    return st.session_state.relay


def latest_event(relay: Relay, role: str):
    for message in reversed(relay.case.messages):
        if message.sender.role == role or message.receiver.role == role:
            return message.event_type
    return None


def role_state(relay: Relay, role: str) -> str:
    status = relay.case.status
    if role == "owner":
        return "已发起事项"
    if role in ("integrated_monitoring", "communications"):
        if status in (CaseStatus.NEW, CaseStatus.DISPATCHED):
            return "等待核查任务"
        if relay.case.current_round == 1:
            return "初步证据已提交"
        return "补充证据已提交"
    if role == "reconciler":
        return "已形成拟定结论" if relay.case.proposed_conclusion else "等待第二轮证据"
    if status == CaseStatus.HUMAN_CONFIRMATION:
        return "待确认拟定结论"
    if status == CaseStatus.REPORT_DRAFTED:
        return "已批准并生成草稿"
    if status == CaseStatus.CLARIFICATION_REQUIRED:
        return "已发出纠偏，等待澄清"
    return "等待人工介入"


def message_summary(message) -> str:
    payload = message.payload
    if "summary" in payload:
        return payload["summary"]
    if "claim" in payload:
        return payload["claim"]
    if "task" in payload:
        return payload["task"]
    if "proposed_conclusion" in payload:
        return payload["proposed_conclusion"]
    if "title" in payload:
        return "已生成 {0} 格式报告草稿（{1}）".format(payload["format"], payload.get("source", "未知来源"))
    return "已记录结构化消息"


def event_label(message) -> str:
    labels = {
        "human.correction": "人工纠偏",
        "conclusion.proposed": "拟定结论 / 待人工确认",
        "human.approval": "总监批准",
        "report.drafted": "报告草稿",
    }
    return labels.get(message.event_type, message.event_type)


def run_action(relay: Relay, action) -> None:
    try:
        action()
        st.session_state.action_error = None
    except RelayStateError as error:
        st.session_state.action_error = str(error)
    st.rerun()


def summary_card(label: str, value: str) -> None:
    st.markdown(
        "<div class='summary-card'><div class='summary-label'>{0}</div>"
        "<div class='summary-value'>{1}</div></div>".format(escape(label), escape(value)),
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="工程协同 Agent Relay", page_icon="R", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #f3f7f6; color: #20313d; }
      .block-container { max-width: 1480px; padding-top: 1.6rem; padding-bottom: 2rem; }
      h1 { letter-spacing: 0 !important; }
      .eyebrow { color: #0f766e; font-size: 0.78rem; font-weight: 700; letter-spacing: 0 !important; }
      .relay-panel { border-top: 3px solid #0f766e; padding-top: 0.55rem; }
      .role-row { border-bottom: 1px solid #d7e0df; padding: 0.62rem 0; }
      .role-name { font-weight: 700; color: #20313d; }
      .role-detail { color: #5d6a70; font-size: 0.86rem; }
      .evidence-ref { display: inline-block; background: #e1f0ed; color: #155e5a; padding: 0.3rem 0.48rem; margin: 0.2rem 0.2rem 0 0; border-radius: 4px; font-family: monospace; font-size: 0.76rem; }
      .summary-card { background: #ffffff; border: 1px solid #d7e0df; border-radius: 6px; min-height: 5.5rem; padding: 0.7rem 0.85rem; }
      .summary-label { color: #5d6a70; font-size: 0.82rem; margin-bottom: 0.35rem; }
      .summary-value { color: #20313d; font-size: 1.2rem; font-weight: 700; overflow-wrap: anywhere; }
      .stButton > button { border-radius: 5px; min-height: 2.45rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

relay = get_relay()
case = relay.case

st.markdown("<div class='eyebrow'>LOCAL MOCK RELAY / HUMAN-IN-THE-LOOP</div>", unsafe_allow_html=True)
st.title("工程协同 Agent Relay")
st.caption("协同指挥台：异构角色通过统一消息链协作，专业判断、证据与最终责任始终可回溯。")

header_left, header_middle, header_right, header_mock = st.columns((2.1, 1.2, 1.1, 1.6))
with header_left:
    summary_card("演示事项", case.title)
with header_middle:
    summary_card("追踪编号", case.trace_id)
with header_right:
    summary_card("当前轮次", "Round {0}/2".format(case.current_round))
with header_mock:
    summary_card("事项状态 / {0}".format(STATUS_LABELS[case.status]), case.status.value)
st.info("Mock nodes / anonymized demo data - 仅验证协作协议与人工控制，不代表真实项目结论。")

if st.session_state.get("action_error"):
    st.error(st.session_state.action_error)

roles_column, timeline_column, evidence_column = st.columns((1.0, 1.65, 1.2), gap="large")

with roles_column:
    st.markdown("<div class='relay-panel'></div>", unsafe_allow_html=True)
    st.subheader("角色轨道")
    for role in ("owner", "integrated_monitoring", "communications", "reconciler", "director_human"):
        last_event = latest_event(relay, role)
        event_text = " / {0}".format(last_event) if last_event else ""
        st.markdown(
            "<div class='role-row'><div class='role-name'>{0}</div>"
            "<div class='role-detail'>{1}{2}</div></div>".format(
                ROLE_LABELS[role], role_state(relay, role), event_text
            ),
            unsafe_allow_html=True,
        )

with timeline_column:
    st.markdown("<div class='relay-panel'></div>", unsafe_allow_html=True)
    st.subheader("协同消息时间线")
    for index, message in enumerate(case.messages, start=1):
        sender = ROLE_LABELS.get(message.sender.role, message.sender.role)
        receiver = ROLE_LABELS.get(message.receiver.role, message.receiver.role)
        prefix = "R{0}".format(message.round)
        special_marker = ""
        if message.event_type == "human.correction":
            special_marker = " [人工介入]"
        elif message.event_type == "conclusion.proposed":
            special_marker = " [待人工确认]"
        if special_marker:
            label = "{0} |{1} | {2} -> {3} | {4}".format(
                prefix, special_marker, sender, receiver, event_label(message)
            )
        else:
            label = "{0} | {1} -> {2} | {3}".format(prefix, sender, receiver, event_label(message))
        with st.expander(label, expanded=index == len(case.messages)):
            st.caption(message_summary(message))
            st.code(message.message_id, language=None)
            st.json({"evidence_refs": message.evidence_refs, "payload": message.payload})

with evidence_column:
    st.markdown("<div class='relay-panel'></div>", unsafe_allow_html=True)
    st.subheader("证据与结论")
    evidence_refs = []
    for message in case.messages:
        for evidence_ref in message.evidence_refs:
            if evidence_ref not in evidence_refs:
                evidence_refs.append(evidence_ref)
    st.caption("当前审计链已引用的脱敏证据")
    for evidence_ref in evidence_refs:
        st.markdown("<span class='evidence-ref'>{0}</span>".format(evidence_ref), unsafe_allow_html=True)

    if case.proposed_conclusion:
        st.divider()
        st.markdown("#### 拟定结论")
        for fact in case.proposed_conclusion["confirmed_facts"]:
            st.write("- {0}".format(fact))
        st.warning(case.proposed_conclusion["proposed_conclusion"])
        if case.status == CaseStatus.HUMAN_CONFIRMATION:
            st.caption("结论仍待总监 Human Adapter 批准，不会生成报告草稿。")

    if case.report_draft:
        st.divider()
        st.markdown("#### Markdown 报告草稿")
        if case.report_source == "真实 LLM":
            st.success("报告来源：真实 LLM。Report Agent 仅接收已批准结论包。")
        else:
            st.info("报告来源：Mock 回退。{0}".format(case.report_fallback_reason or "未使用真实 LLM。"))
        if st.button("重新演示", key="reset_from_report", use_container_width=True):
            run_action(relay, relay.reset_case)
        st.markdown(case.report_draft)

st.divider()
st.markdown("### Human Adapter 控制")
st.caption("每次操作都会写入同一条审计时间线。系统不自动跨越人工纠偏或总监批准。")

controls = st.columns(5, gap="small")
with controls[0]:
    if st.button("重置案例", use_container_width=True):
        run_action(relay, relay.reset_case)
with controls[1]:
    if st.button("运行 Round 1", use_container_width=True, disabled=case.status != CaseStatus.NEW):
        run_action(relay, relay.run_round_1)
with controls[2]:
    if st.button(
        "人工纠偏",
        use_container_width=True,
        disabled=case.status != CaseStatus.AWAITING_HUMAN_CORRECTION,
    ):
        run_action(relay, relay.apply_human_correction)
with controls[3]:
    if st.button(
        "运行 Round 2",
        use_container_width=True,
        disabled=case.status != CaseStatus.CLARIFICATION_REQUIRED,
    ):
        run_action(relay, relay.run_round_2)
with controls[4]:
    if st.button(
        "总监批准并生成报告",
        type="primary",
        use_container_width=True,
        disabled=case.status != CaseStatus.HUMAN_CONFIRMATION,
    ):
        run_action(relay, relay.approve_by_director)

if case.status == CaseStatus.AWAITING_HUMAN_CORRECTION:
    st.warning("预设纠偏：{0}".format(case.fixture["human_correction"]["summary"]))
