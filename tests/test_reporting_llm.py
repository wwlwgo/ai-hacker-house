import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.relay.core import Relay, RelayStateError
from src.reporting.llm import build_approved_report_package, request_deepseek_report


FIXTURE = Path(__file__).resolve().parents[1] / "demo-fixtures" / "sc-pipe-inspection" / "case.json"


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class LiveReportTests(unittest.TestCase):
    def setUp(self):
        self.relay = Relay(FIXTURE, enable_live_llm=True)

    def approve_case(self):
        self.relay.run_round_1()
        self.relay.apply_human_correction()
        self.relay.run_round_2()
        self.relay.approve_by_director()

    @patch("src.relay.core.request_deepseek_report", return_value="# 真实草稿")
    @patch("src.relay.core.load_local_env")
    def test_live_report_receives_only_approved_package(self, _load_env, request):
        self.approve_case()
        package = request.call_args.args[0]
        serialized = json.dumps(package, ensure_ascii=False)
        self.assertEqual(self.relay.case.report_source, "真实 LLM")
        self.assertEqual(package["trace_id"], self.relay.case.trace_id)
        self.assertIn("总监 Human Adapter 已批准", package["approval_context"])
        self.assertNotIn("challenge.raised", serialized)
        self.assertNotIn("rejected", serialized)
        self.assertNotIn("pending", serialized)
        self.assertNotIn("照片外观可单独证明", serialized)
        self.assertNotIn("通信专业台账可证明", serialized)
        self.assertNotIn("messages", package)
        self.assertNotIn("timeline", package)

    @patch("src.relay.core.request_deepseek_report", side_effect=RuntimeError("DeepSeek 请求超时"))
    @patch("src.relay.core.load_local_env")
    def test_api_failure_falls_back_to_mock(self, _load_env, _request):
        self.approve_case()
        self.assertEqual(self.relay.case.report_source, "Mock 回退")
        self.assertEqual(self.relay.case.report_fallback_reason, "DeepSeek 请求超时")
        self.assertIn("已确认事实", self.relay.case.report_draft)

    def test_live_llm_cannot_run_before_director_approval(self):
        self.relay.run_round_1()
        self.relay.apply_human_correction()
        self.relay.run_round_2()
        with self.assertRaises(RelayStateError):
            self.relay.generate_report()

    def test_missing_key_is_handled_by_relay_fallback(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            with patch("src.relay.core.load_local_env"):
                self.approve_case()
        self.assertEqual(self.relay.case.report_source, "Mock 回退")
        self.assertIn("未配置", self.relay.case.report_fallback_reason)

    def test_empty_api_content_is_rejected(self):
        package = build_approved_report_package(
            "t-1",
            "事项",
            {"approved_facts": ["已批准事实"], "approved_conclusion": "已批准结论", "evidence_refs": ["ev-01"]},
        )
        response = {"choices": [{"message": {"content": "   "}}]}
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=False):
            with patch("src.reporting.llm.urlopen", return_value=_FakeResponse(json.dumps(response))):
                with self.assertRaisesRegex(RuntimeError, "空草稿"):
                    request_deepseek_report(package)


if __name__ == "__main__":
    unittest.main()
