from html import escape
from pathlib import Path

import streamlit as st

from src.relay.core import Relay, RelayStateError
from src.relay.models import CaseStatus


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "demo-fixtures" / "sc-pipe-inspection" / "case.json"
STATUS_LABELS = {CaseStatus.NEW: "新建事项", CaseStatus.DISPATCHED: "等待初判", CaseStatus.EVIDENCE_COLLECTING: "核对与补证中", CaseStatus.AWAITING_HUMAN_CORRECTION: "等待人工纠偏", CaseStatus.CLARIFICATION_REQUIRED: "等待跨专业核对", CaseStatus.HUMAN_CONFIRMATION: "等待总监裁决或批准", CaseStatus.APPROVED: "已批准", CaseStatus.REPORT_DRAFTED: "报告草稿已生成"}
ROLE_LABELS = {"owner": "发起方", "integrated_monitoring": "综合监控 Agent", "communications": "通信 Agent", "director_human": "总监 Human Adapter", "relay": "Relay"}
EVENT_META = {
    "issue.created": ("事项", "issue"), "directive.issued": ("总监指令", "directive"),
    "claim.submitted": ("专业初判", "claim"), "challenge.raised": ("专业质疑", "challenge"),
    "human.correction": ("人工纠偏", "human"), "cross_check.requested": ("跨专业核对请求", "cross"),
    "cross_check.responded": ("跨专业核对回复", "cross"), "evidence.supplemented": ("补充证据", "claim"),
    "human.decision": ("总监裁决", "decision"), "human.approval": ("总监批准", "approval"), "report.drafted": ("报告草稿", "report"),
}


def get_relay():
    if "relay" not in st.session_state:
        st.session_state.relay = Relay(FIXTURE, enable_live_llm=True)
    return st.session_state.relay


def has_event(relay, event_type):
    return any(message.event_type == event_type for message in relay.case.messages)


def run_action(relay, action):
    try:
        action()
        st.session_state.action_error = None
    except RelayStateError as error:
        st.session_state.action_error = str(error)
    st.rerun()


def summary_card(label, value):
    st.markdown("<div class='summary-card'><span>{0}</span><strong>{1}</strong></div>".format(escape(label), escape(value)), unsafe_allow_html=True)


def package_panel(title, package, state):
    st.markdown("<div class='package {0}'><div class='package-kicker'>{1}</div>".format(state, escape(title)), unsafe_allow_html=True)
    for fact in package["approved_facts"]:
        st.write("- " + fact)
    st.caption("证据：" + " · ".join(package["evidence_refs"]))
    st.markdown("</div>", unsafe_allow_html=True)


st.set_page_config(page_title="工程协同 Agent Relay", page_icon="R", layout="wide")
st.markdown("""<style>
.stApp{background:#f2f5f3;color:#1d2930}.block-container{max-width:1500px;padding-top:1.2rem;padding-bottom:2rem}h1{letter-spacing:0!important}.eyebrow,.package-kicker{color:#0b756d;font-size:.76rem;font-weight:700;letter-spacing:0!important}.summary-card{background:#fff;border:1px solid #d5dfdc;border-radius:5px;min-height:4.7rem;padding:.65rem .8rem}.summary-card span{display:block;color:#617078;font-size:.78rem}.summary-card strong{display:block;margin-top:.25rem;font-size:1.05rem;overflow-wrap:anywhere}.section-rule{border-top:3px solid #0b756d;padding-top:.5rem}.role-row{border-bottom:1px solid #d5dfdc;padding:.56rem 0}.role-row strong{display:block}.role-row span{color:#617078;font-size:.82rem}.badge{display:inline-block;border-radius:3px;padding:.16rem .42rem;font-size:.72rem;font-weight:700}.issue{background:#e1ebee;color:#34515b}.directive,.human,.decision{background:#fff0d1;color:#895700}.claim{background:#dff0ec;color:#176157}.challenge{background:#fbe1df;color:#a0342d}.cross{background:#e4e9fb;color:#3e518f}.approval{background:#dcefd6;color:#306b36}.report{background:#e9e4f6;color:#604a91}.evidence-ref{display:inline-block;background:#e1f0ed;color:#155e5a;padding:.25rem .42rem;margin:.16rem .16rem 0 0;border-radius:3px;font-family:monospace;font-size:.72rem}.package{border-left:4px solid #a07315;background:#fffaf0;padding:.7rem .85rem;margin:.35rem 0}.package.approved{border-color:#176157;background:#f0faf6}.ledger-note{color:#617078;font-size:.82rem}.stButton>button{border-radius:4px;min-height:2.55rem;font-size:.86rem}.action-caption{font-size:.74rem;color:#66747b;min-height:2.1rem}.stDataFrame{border:1px solid #d5dfdc}@media(max-width:700px){.block-container{padding:1rem .75rem}.summary-card{min-height:4.2rem}.stButton>button{font-size:.77rem}}
</style>""", unsafe_allow_html=True)

relay = get_relay(); case = relay.case
st.markdown("<div class='eyebrow'>LOCAL RELAY / HUMAN CONTROLLED / ANONYMIZED</div>", unsafe_allow_html=True)
st.title("工程协同 Agent Relay")
st.caption("协同指挥台：将专业分歧、交叉核对与总监裁决留在同一条可追溯消息链中。")

head = st.columns((2.1, 1.15, 1.0, 1.55))
with head[0]: summary_card("演示事项", case.title)
with head[1]: summary_card("追踪编号", case.trace_id)
with head[2]: summary_card("当前轮次", "Round {0}/2".format(case.current_round))
with head[3]: summary_card("事项状态", STATUS_LABELS[case.status])
st.info("Mock 专业节点与脱敏资料用于演示协同协议；报告节点可在总监批准后调用真实 LLM，失败时自动回退。")
if st.session_state.get("action_error"): st.error(st.session_state.action_error)

left, center, right = st.columns((.95, 1.7, 1.3), gap="large")
with left:
    st.markdown("<div class='section-rule'></div>", unsafe_allow_html=True); st.subheader("角色轨道")
    for role in ("owner", "integrated_monitoring", "communications", "director_human"):
        latest = next((m.event_type for m in reversed(case.messages) if m.sender.role == role or m.receiver.role == role), "等待")
        st.markdown("<div class='role-row'><strong>{0}</strong><span>{1}</span></div>".format(ROLE_LABELS[role], escape(EVENT_META.get(latest, (latest, ""))[0])), unsafe_allow_html=True)

with center:
    st.markdown("<div class='section-rule'></div>", unsafe_allow_html=True); st.subheader("协同消息时间线")
    for index, message in enumerate(case.messages, 1):
        label, kind = EVENT_META.get(message.event_type, (message.event_type, "issue"))
        sender = ROLE_LABELS.get(message.sender.role, message.sender.role); receiver = ROLE_LABELS.get(message.receiver.role, message.receiver.role)
        with st.expander("R{0} · {1} -> {2} · {3}".format(message.round, sender, receiver, label), expanded=index == len(case.messages)):
            st.markdown("<span class='badge {0}'>{1}</span>".format(kind, label), unsafe_allow_html=True)
            st.write(message.payload.get("summary", "已记录结构化消息"))
            if message.payload.get("transport") == "relay_mediated": st.caption("经 Relay 中介、记录并保留同一 trace_id")
            st.caption("证据：" + (" · ".join(message.evidence_refs) or "无"))

with right:
    st.markdown("<div class='section-rule'></div>", unsafe_allow_html=True); st.subheader("证据与结论")
    refs=[]
    for message in case.messages:
        refs += [ref for ref in message.evidence_refs if ref not in refs]
    for ref in refs: st.markdown("<span class='evidence-ref'>{0}</span>".format(ref), unsafe_allow_html=True)
    if case.pending_conclusion_package:
        st.divider(); package_panel("待总监批准结论包", case.pending_conclusion_package, "pending")
        st.caption("仅包含候选 adopted 项；批准前不会交给 Report Agent。")
    if case.approved_conclusion_package:
        st.divider(); package_panel("已批准结论包 · Report Agent 的唯一输入", case.approved_conclusion_package, "approved")
        st.success("已排除与待补充项不会进入报告或真实 LLM 请求。")
    if case.report_draft:
        st.divider(); st.markdown("#### Markdown 报告草稿")
        st.success("报告来源：真实 LLM。仅读取已批准结论包。") if case.report_source == "真实 LLM" else st.info("报告来源：Mock 回退。" + (case.report_fallback_reason or ""))
        if st.button("重新演示", key="reset_from_report", use_container_width=True): run_action(relay, relay.reset_case)
        st.markdown(case.report_draft)

if case.decision_ledger:
    st.divider(); st.markdown("### 结论裁决台账")
    st.caption("总监明确采纳、排除和待补充项。只有已采纳项才会形成结论包。")
    rows=[{"状态": item["status"], "结论项": item["decision_item"], "来源": " / ".join(item["source"]), "总监处理理由": item["director_rationale"], "证据": " · ".join(item["evidence_refs"]) or "待补充"} for item in case.decision_ledger]
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider(); st.markdown("### Human Adapter 控制")
st.caption("每个动作都写入同一审计链。专业节点只能提交判断或互证；裁决、批准与报告触发权保留给总监。")
if st.button("重置案例", use_container_width=False): run_action(relay, relay.reset_case)
actions = [
    ("发布总监指令", "明确核查边界", relay.issue_directive, case.status == CaseStatus.NEW),
    ("接收双专业初判", "记录两个独立专业判断", relay.submit_round_1_claims, case.status == CaseStatus.DISPATCHED),
    ("记录专业质疑", "指出不能直接采纳的推断", relay.raise_specialist_challenge, case.status == CaseStatus.EVIDENCE_COLLECTING and has_event(relay, "claim.submitted") and not has_event(relay, "challenge.raised")),
    ("总监人工纠偏", "收紧对象、测量和依据边界", relay.apply_human_correction, case.status == CaseStatus.AWAITING_HUMAN_CORRECTION),
    ("执行跨专业核对", "Relay 中介的核对请求", relay.request_cross_check, case.status == CaseStatus.CLARIFICATION_REQUIRED),
    ("接收核对回复", "记录专业边界与回复", relay.respond_to_cross_check, case.status == CaseStatus.EVIDENCE_COLLECTING and has_event(relay, "cross_check.requested") and not has_event(relay, "cross_check.responded")),
    ("补充证据", "补齐可追溯的对象与依据", relay.submit_supplemental_evidence, case.status == CaseStatus.EVIDENCE_COLLECTING and has_event(relay, "cross_check.responded") and not has_event(relay, "evidence.supplemented")),
    ("记录总监裁决", "形成 adopted / rejected / pending 台账", relay.record_director_decision, case.status == CaseStatus.HUMAN_CONFIRMATION and not case.pending_conclusion_package),
    ("总监批准并生成报告", "批准结论包后调用 Report Agent", relay.approve_by_director, case.status == CaseStatus.HUMAN_CONFIRMATION and bool(case.pending_conclusion_package)),
]
for row_start in range(0, len(actions), 3):
    columns = st.columns(3, gap="small")
    for column, (name, detail, action, enabled) in zip(columns, actions[row_start:row_start + 3]):
        with column:
            st.caption(detail)
            if st.button(name, type="primary" if name.startswith("总监批准") else "secondary", disabled=not enabled, use_container_width=True): run_action(relay, action)
