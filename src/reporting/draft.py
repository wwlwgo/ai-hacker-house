from typing import Any, Dict


def render_markdown_report(trace_id: str, title: str, conclusion: Dict[str, Any]) -> str:
    """Render only the already approved conclusion package into a draft."""
    facts = "\n".join("- {0}".format(fact) for fact in conclusion["confirmed_facts"])
    evidence = "\n".join("- `{0}`".format(ref) for ref in conclusion["evidence_refs"])
    return """# {title}

> 演示草稿 | 追踪编号：`{trace_id}` | 仅基于已批准的结论包生成，不构成正式签发文件。

## 已确认事实

{facts}

## 总监已确认的拟定结论

总监已确认两个专业节点完成第二轮补充核查，并同意将已确认事实与证据引用用于本报告草稿。系统保留该结论在批准前为“拟定结论”的审计记录。

## 证据引用

{evidence}

## 人工确认

本草稿已在 Relay 审计链中记录总监 Human Adapter 的批准动作；正式对外交付仍需由人工按既有流程复核、签发和发送。
""".format(
        title=title,
        trace_id=trace_id,
        facts=facts,
        evidence=evidence,
    )
