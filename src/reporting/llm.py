"""A deliberately narrow LLM adapter for approved report drafting only."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
SYSTEM_PROMPT = """你是工程专项检查报告起草助手。只依据用户提供的“已批准结论包”起草 Markdown 报告。
报告必须包括：事项、结论、依据/证据、核查过程、风险提示、后续动作。
不得捏造项目事实、数值、规范条款、责任认定或证据；信息不足时明确写“待人工补充”。
“已批准结论包”已由总监 Human Adapter 批准用于本次草稿：不得把其中结论描述为“尚未批准”“待总监确认”或“待完成”。
这只是内部草稿，不能写成正式签发、盖章或自动发送的文件。"""


@dataclass(frozen=True)
class ReportResult:
    markdown: str
    source: str
    fallback_reason: Optional[str] = None


def load_local_env(env_path: Path) -> None:
    """Load only missing local values; never logs the file or its values."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


def build_approved_report_package(trace_id: str, title: str, conclusion: Dict[str, Any]) -> Dict[str, Any]:
    """Return the sole data payload allowed to leave the Relay for report drafting."""
    return {
        "trace_id": trace_id,
        "title": title,
        "approval_context": "总监 Human Adapter 已批准该拟定结论仅用于生成内部演示报告草稿。",
        "confirmed_facts": list(conclusion["confirmed_facts"]),
        "proposed_conclusion": conclusion["proposed_conclusion"],
        "evidence_refs": list(conclusion["evidence_refs"]),
    }


def request_deepseek_report(package: Dict[str, Any], timeout: float = 18.0) -> str:
    """Request one draft. Callers handle errors to preserve the Mock fallback."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    request_body = {
        "model": DEEPSEEK_MODEL,
        "temperature": 0.2,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "以下是唯一可用的已批准结论包：\n" + json.dumps(package, ensure_ascii=False),
            },
        ],
    }
    payload = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = Request(
        DEEPSEEK_ENDPOINT,
        data=payload,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError("DeepSeek HTTP {0}".format(error.code)) from error
    except TimeoutError as error:
        raise RuntimeError("DeepSeek 请求超时") from error
    except (URLError, OSError) as error:
        raise RuntimeError("DeepSeek 网络请求失败") from error

    try:
        decoded = json.loads(response_body)
        content = decoded["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise RuntimeError("DeepSeek 返回内容无法解析") from error
    if not content:
        raise RuntimeError("DeepSeek 返回了空草稿")
    return content
