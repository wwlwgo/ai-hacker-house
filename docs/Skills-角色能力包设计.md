# Skill 与角色能力包设计

## 1. Skill 在 Agent Relay 中的位置

工程协同 Agent Relay 不把所有知识集中到总线。每个角色保留自己的本地上下文和能力包：

```text
Relay：这个事项该找谁、下一轮是否需要发生、谁可以确认。
角色 Agent：收到任务后如何按专业规则处理。
Skill：该角色完成某类具体任务的可复用方法、模板、脚本和质量约束。
```

因此，Skill 与 Relay 是上下游关系，不是竞争关系。

## 2. 能力包模型

一个角色能力包可声明：

```json
{
  "role": "supervision_specialist",
  "capabilities": [
    "review_evidence",
    "compare_revision",
    "draft_supervision_opinion"
  ],
  "input_contract": ["task", "evidence_refs", "constraints"],
  "output_contract": ["claim", "evidence_refs", "open_questions"],
  "autonomy": "draft_only"
}
```

这不是明天要实现的配置文件，而是团队实现时应保持的概念边界：Skill 的输出必须回到 Relay 可理解的结构化结果，而不是只返回一段自由文本。

## 3. 对现有 Skill 资产的映射

| 角色 | 可复用能力 | Relay 中的触发时机 | 结果边界 |
| --- | --- | --- | --- |
| 专业总代 Agent | 方案复核、意见比对、证据定位 | 收到 `verification.requested` | 形成专业建议，不可批准 |
| 资料/监理 Agent | 联系单和报告草稿 | 事项退回或批准后 | 生成草稿，不可签发 |
| 汇总 Agent | 多资料归纳、会议纪要、周报草稿 | 多个事项需汇总时 | 引用已确认事实 |
| 安全专监 Agent | 隐患记录、整改跟踪、日报规范 | 每日事项或重大隐患触发时 | 提出处理建议，升级高风险节点 |

## 4. 明天如何可视化 Skill

不需要加载完整 Skill 文件或演示内部 Prompt。前端只需在角色详情中显示简短标签：

```text
综合监控 Agent
Capabilities: 现场证据核对 · 技术依据提取 · 澄清问题生成

Report Agent
Capabilities: 已批准结论汇总 · 专项报告草稿生成 · 证据引用整理
```

这样观众会理解：不同 Agent 并不是同一个模型换了名字，而是有不同角色上下文和能力边界。

## 5. 不应做的事

- 不把全部 Skill 包直接暴露给每一个 Agent。
- 不让报告生成 Skill 读取未批准的聊天内容。
- 不因“展示多个 Skill”而增加第二条未完成的业务链。
- 不把 Skill 当作绕过人工责任边界的自动审批工具。
