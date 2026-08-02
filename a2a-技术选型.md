# 建工五方协同 Agent 平台 —— MVP 技术选型与实施蓝图

> 活动：Ship it Sunday #011（8月2日，上海）
> 目标：一天内跑通"工程变更单五方流转"闭环 demo，现场可演示、可追溯、可讲解
> 原则：**骨架先行**——数据模型、消息契约、状态机、目录结构先定死，剩下全是填代码（NAS 项目验证过的方法）

---

## 0. 设计约束（先立规矩）

| 约束 | 含义 |
|:--|:--|
| 单人可维护 | 主要靠 Codex/Hermes 生成代码，必须结构简单、可解释 |
| 本地可跑 | 现场网络不可控，全部依赖本地安装，不依赖云服务（LLM 除外，且有降级方案） |
| 一天出活 | 核心闭环优先，其他全是加分项 |
| 可演示 | 支持"手动逐步触发"（一步步展示流转）+ "一键自动跑完"两种模式 |
| 可追溯 | 所有消息、状态、审计日志落库，演示时可回放——这是核心卖点 |
| 前瞻性 | 消息契约按 A2A/MCP 风格设计，生产可迁移，但不绑架 MVP |

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit 演示层 (UI)                    │
│  五方 Agent 状态卡 │ 变更单详情 │ 消息流转时间线 │ 文档预览    │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────┐
│                   A2A 消息总线 (bus.py)                      │
│   路由 → 留痕(SQLite) → 触发对应 Agent 响应                    │
└───┬──────────┬──────────┬──────────┬──────────┬─────────────┘
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ 业主    │ │ 设计    │ │ 施工    │ │ 监理    │ │ 运营    │
│ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │
│(owner) │ │(design)│ │(contract)││(superv)│ │(oper)  │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │          │
    └──────────┴─────┬────┴──────────┴──────────┘
                     │ 每个 Agent 内含：
                     │  · 角色 System Prompt（LLM 调用）
                     │  · 技能包（复用 engineering-ai-skills 思路）
                     │  · 工具集（文档生成、校验、状态变更）
                     ▼
            ┌─────────────────────┐
            │  LLM Provider (llm.py) │
            │  DeepSeek API 主用    │
            │  Mock LLM 降级备用    │
            └─────────────────────┘
```

**核心思想：五方 Agent 不直接互相调用，全部通过消息总线收发消息。** 这是 A2A 模式的精髓——解耦 + 全程留痕 + 可观测。

---

## 2. 技术选型决策表（全部已定，直接执行）

| 项 | 选择 | 理由 |
|:--|:--|:--|
| **语言** | Python 3.10+ | 你会、AI 生成快、生态全 |
| **演示 UI** | **Streamlit** | 不写前端 JS，组件出界面；支持按钮逐步触发，天然适合演示 |
| **后端** | MVP 不单独拆服务，Streamlit 直接驱动 app 层 | 一天内最简；代码分层保留，后续可拆 FastAPI |
| **Agent 框架** | **轻量自研**（BaseAgent + 5 子类） | 不用 CrewAI/AutoGen/LangGraph：可控、可讲原理、AI 好生成、无学习成本 |
| **消息契约** | 自定义 A2A 风格 JSON（参考 Google A2A + MCP 规范） | 前瞻性卖点，生产可迁移；MVP 用内存路由+落库 |
| **LLM** | DeepSeek API（deepseek-chat）主用；**Mock LLM 降级** | 国内稳定便宜快；现场断网/欠费也有兜底 |
| **文档生成** | python-docx（Word）+ Markdown 双输出 | 监理报告/联系单要 Word 成品；Markdown 做预览 |
| **存储** | **SQLite** | 零配置、单文件、审计日志天然可回放 |
| **配置** | config.yaml | Agent 角色、LLM key、流程规则全集中，改配置不改代码 |

**为什么不引入重型 Agent 框架（评委必问，提前备好答案）：**
> "MVP 阶段用轻量自研保证可控性和可解释性——每个消息如何流转、状态如何迁移，我们一行代码就能讲清楚。生产环境可以平滑迁移到 LangGraph 或标准 A2A 协议，消息契约已经是按 A2A 风格设计的，迁移成本低。"

---

## 3. 核心数据模型（先定死，代码只是映射）

### 3.1 变更单 ChangeOrder
| 字段 | 类型 | 说明 |
|:--|:--|:--|
| id | str | CO-20260802-001 |
| title | str | 变更标题 |
| description | str | 变更内容 |
| initiator | str | 发起方（监理/业主/施工…） |
| status | str | 状态（见状态机） |
| impact_analysis | str | 工期/费用影响（LLM 生成） |
| documents | list | 关联文档（报告/联系单/批复） |
| created_at / updated_at | datetime | |
| trace_id | str | 全链路追踪 ID |

### 3.2 消息 Message（A2A 契约）
| 字段 | 类型 | 说明 |
|:--|:--|:--|
| message_id | str | 唯一消息 ID |
| trace_id | str | 关联变更单追踪 ID |
| sender | str | owner/design/contractor/supervisor/operator |
| receiver | str | 同上，或 `*`（广播） |
| event_type | str | 见事件枚举 |
| payload | json | 业务数据 |
| timestamp | datetime | |
| status | str | sent/delivered/read/processed |

### 3.3 Agent AgentProfile
| 字段 | 说明 |
|:--|:--|
| id | owner/design/contractor/supervisor/operator |
| display_name | 业主单位 / 设计单位 / 施工单位 / 监理单位 / 运营单位 |
| system_prompt | 角色定义（LLM 用） |
| skills | 技能包列表（引用工程文档 Skill） |
| inbox | 待处理消息队列 |

### 3.4 事件枚举 event_type
```
change_order.created / .submitted / .replied / .reviewed
change_order.rejected / .approved / .archived
document.generated / .signed
notification.sent
```

---

## 4. 状态机设计（核心闭环）

```
                    ┌──────────────────────────────┐
                    │  退回修改（复核不通过）       │
                    └──────────────┬───────────────┘
                                  ▼
[DRAFT] → [SENT_TO_CONTRACTOR] → [CONTRACTOR_REPLIED]
 监理草拟     发送给施工单位       施工回复方案
                                  │
                                  ▼
                          [SUPERVISION_REVIEW] ──不通过──▶ 退回
                           监理复核        │
                                          ▼ 通过
                                   [DESIGN_CONFIRM] ──不涉及──┐
                                    设计确认（可选）           │
                                          ▼ 涉及/通过          │
                                   [OWNER_APPROVAL] ◀─────────┘
                                    业主审批
                                    │      │
                              通过  │      │ 拒绝
                                    ▼      ▼
                              [APPROVED] [REJECTED]
                                    │
                                    ▼
                               [ARCHIVED] ──▶ 通知运营 Agent
                                归档+留痕
```

**状态枚举：** DRAFT → SENT_TO_CONTRACTOR → CONTRACTOR_REPLIED → SUPERVISION_REVIEW → DESIGN_CONFIRM → OWNER_APPROVAL → APPROVED → ARCHIVED（+ REJECTED 终止态）

**每步动作表（写死，代码照着填）：**

| 状态 | 动作 | 产出 |
|:--|:--|:--|
| DRAFT | 监理 Agent 发现问题，LLM 生成变更单 | 变更单 + 监理通知单 |
| SENT_TO_CONTRACTOR | 总线路由给施工 Agent | 消息留痕 |
| CONTRACTOR_REPLIED | 施工 Agent LLM 生成回复方案 | 施工方案文档 |
| SUPERVISION_REVIEW | 监理 Agent 复核（LLM 判断通过/退回） | 复核意见 |
| DESIGN_CONFIRM | 设计 Agent 确认技术可行性 | 设计确认单 |
| OWNER_APPROVAL | 业主 Agent 审批（成本/工期影响） | 审批意见 |
| APPROVED | 生成批复文档 | 变更批复 |
| ARCHIVED | 归档 + 通知运营 Agent | 归档记录 + 运营通知 |

---

## 5. A2A 消息契约示例（直接照抄）

```json
{
  "message_id": "msg_20260802_001",
  "trace_id": "trace_CO_20260802_001",
  "sender": "supervisor",
  "receiver": "contractor",
  "event_type": "change_order.created",
  "payload": {
    "change_order_id": "CO-20260802-001",
    "title": "综合监控系统接口协议变更",
    "description": "智能运维平台与综合监控系统接口由私有协议调整为标准协议…",
    "impact_analysis": "预计工期影响 3 天，费用增加 5 万元",
    "attachments": ["监理通知单_CO-20260802-001.docx"]
  },
  "timestamp": "2026-08-02T10:00:00+08:00",
  "status": "sent"
}
```

---

## 6. 代码结构（目录骨架先建好）

```
a2a-construction-mvp/
├── README.md
├── config.yaml                # Agent 角色 / LLM / 流程规则
├── requirements.txt
├── run_demo.py                # Streamlit 入口：streamlit run run_demo.py
├── app/
│   ├── __init__.py
│   ├── models.py              # 数据模型（3.1-3.4）
│   ├── bus.py                 # A2A 消息总线：路由 + 留痕 + 触发
│   ├── state_machine.py       # 状态机 + 每步动作表
│   ├── llm.py                 # LLM 封装（DeepSeek / Mock 双模式）
│   ├── docs.py                # 文档生成（python-docx / Markdown）
│   ├── storage.py             # SQLite 读写（消息/变更单/审计）
│   └── agents/
│       ├── __init__.py
│       ├── base.py            # BaseAgent：inbox/发送/接收/LLM 响应
│       ├── owner.py
│       ├── design.py
│       ├── contractor.py
│       ├── supervisor.py
│       └── operator.py
├── examples/
│   ├── meeting_minutes.md     # 示例输入：会议纪要（触发场景）
│   └── inspection_record.md   # 示例输入：检查记录
├── data/                      # SQLite 数据库文件（gitignore）
└── tests/
    └── test_flow.py           # 冒烟测试：跑通全流程
```

---

## 7. 开发计划（骨架先行，分阶段）

### Phase 0 —— 今天/明天（活动前，最重要）
**目标：不接 LLM 也能跑通全流程（规则引擎模式）**
1. 建目录 + requirements.txt（streamlit, openai, python-docx, pyyaml, sqlite3 内置）
2. models.py 全量数据模型
3. bus.py 消息路由 + SQLite 留痕
4. state_machine.py 状态机 + 动作表（先写死规则：复核默认通过、设计默认确认）
5. 5 个 Agent 桩（BaseAgent + 空实现，靠规则引擎响应）
6. **冒烟测试 test_flow.py：一条变更单从 DRAFT 到 ARCHIVED 全流程跑通**
7. Streamlit UI 第一版：五方状态卡 + 消息时间线 + 逐步触发按钮

✅ **验收标准：`python test_flow.py` 绿；`streamlit run run_demo.py` 能手动点着跑完全流程**

### Phase 1 —— 活动前（有余力）
1. llm.py 接 DeepSeek API（每个 Agent 一个 System Prompt 角色卡）
2. docs.py 文档生成（变更单 Word / 施工方案 / 批复）
3. Agent 内容改为 LLM 生成（规则引擎留作 Mock 降级）
4. Streamlit 加文档预览、审计日志回放

### Phase 2 —— 现场上午
1. 真实 API 跑真实场景数据
2. 修 bug、润色 UI、准备演示数据

### Phase 3 —— 现场下午
1. 打磨路演 demo（见演示脚本）
2. 有余力：加"传统方式 vs Agent 方式"对比页（加分项）

---

## 8. 风险与对策

| 风险 | 概率 | 对策 |
|:--|:--|:--|
| 现场断网/API 失败 | 中 | Mock LLM 降级：规则引擎 + 预设文案，流程照跑 |
| 时间不够 | 高 | 核心闭环（变更单流转）优先，UI/文档/对比页全可砍 |
| Streamlit 组件问题 | 低 | 时间线用 st.chat_message + st.write 手写，不依赖第三方组件 |
| 评委问"为什么不用框架" | 必问 | 备好答案（见 §2 末尾） |
| 演示冷场 | 低 | 手动逐步模式 + 每一步配讲解词（见 §9） |

---

## 9. 现场演示脚本（5 分钟路演）

| 步骤 | 动作 | 讲解词要点 |
|:--|:--|:--|
| 1. 痛点 | 展示"传统方式"对比图 | "微信+邮件+纸质，信息分散、责任模糊、追溯困难——我 25 年每天都在经历" |
| 2. 场景 | 点"监理发现问题" | "现场检查发现接口协议问题，监理 Agent 自动生成变更单" |
| 3. 流转 | 逐步点击下一步 | "施工 Agent 收到并回复方案 → 监理复核 → 设计确认 → 业主审批" |
| 4. 可追溯 | 打开审计日志回放 | "每一步消息留痕，责任清晰——这是 Agent 协同最大的价值" |
| 5. 前瞻 | 展示消息契约 | "消息契约按 A2A 标准风格设计，生产可平滑迁移" |
| 6. 收尾 | 一键自动跑完 | "从发现问题到归档，全流程自动化，人工只在审批节点决策" |

**一句话收尾：**
> "我们把建设项目最混乱的信息流转，变成了可追溯、可自动化、责任清晰的 Agent 协同网络——这是未来工程管理的基础设施。"

---

## 10. 后续演进（生产化路径，写在文档里体现前瞻性）

1. **消息总线升级**：内存路由 → 真实 HTTP/A2A 协议（每个 Agent 独立服务）
2. **框架迁移**：轻量自研 → LangGraph（状态图）或接标准 A2A 协议
3. **技能包扩展**：复用 engineering-ai-skills 全部 4 个 Skill 作为 Agent 工具
4. **权限与审计**：接入真实审批流（人工审批门）、电子签章
5. **多项目扩展**：五方 → 任意 N 方协同（供应链、EPC、运维）

---

## 附：requirements.txt（预先定好）

```
streamlit>=1.36
openai>=1.40          # DeepSeek 兼容 OpenAI SDK
python-docx>=1.1
PyYAML>=6.0
```

（sqlite3、dataclasses、uuid、datetime 均为 Python 内置，无需安装）
