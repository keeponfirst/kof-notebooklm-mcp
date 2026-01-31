"""ask 工具的單元測試。"""

import pytest

from kof_notebooklm_mcp.tools.ask import (
    AskResult,
    Citation,
    _estimate_confidence,
)


class TestCitation:
    """Citation 資料類別測試。"""

    def test_to_dict_complete(self):
        """測試完整資料的序列化。"""
        citation = Citation(
            source_id="src123",
            source_title="MCP 規格文件",
            excerpt="MCP 支援 stdio 和 HTTP 傳輸...",
        )
        d = citation.to_dict()
        assert d["source_id"] == "src123"
        assert d["source_title"] == "MCP 規格文件"
        assert d["excerpt"] == "MCP 支援 stdio 和 HTTP 傳輸..."

    def test_to_dict_minimal(self):
        """測試最小資料的序列化。"""
        citation = Citation(source_id="src1", source_title="來源一")
        d = citation.to_dict()
        assert d["source_id"] == "src1"
        assert d["source_title"] == "來源一"
        assert d["excerpt"] is None


class TestAskResult:
    """AskResult 資料類別測試。"""

    def test_to_dict_success(self):
        """測試成功結果的序列化。"""
        result = AskResult(
            answer="這是 AI 的回答...",
            citations=[
                Citation(source_id="src1", source_title="來源一"),
                Citation(source_id="src2", source_title="來源二"),
            ],
            confidence="high",
            follow_up_questions=["後續問題一？", "後續問題二？"],
        )
        d = result.to_dict()
        assert d["answer"] == "這是 AI 的回答..."
        assert len(d["citations"]) == 2
        assert d["confidence"] == "high"
        assert len(d["follow_up_questions"]) == 2

    def test_to_dict_error(self):
        """測試錯誤結果的序列化。"""
        result = AskResult(
            error={
                "code": "TIMEOUT",
                "message": "等待回應逾時",
                "recoverable": True,
            }
        )
        d = result.to_dict()
        assert "error" in d
        assert d["error"]["code"] == "TIMEOUT"
        assert "answer" not in d

    def test_to_dict_no_citations(self):
        """測試無引用時的序列化。"""
        result = AskResult(
            answer="簡短的回答",
            citations=[],
        )
        d = result.to_dict()
        assert d["answer"] == "簡短的回答"
        assert "citations" not in d  # 空列表不應出現

    def test_to_dict_no_confidence(self):
        """測試無信心程度時的序列化。"""
        result = AskResult(answer="回答")
        d = result.to_dict()
        assert "confidence" not in d


class TestEstimateConfidence:
    """信心程度估計測試。"""

    def test_high_confidence(self):
        """測試高信心程度。"""
        answer = "這是一個詳細的回答" * 20  # 超過 200 字元
        citations = [
            Citation(source_id="s1", source_title="來源一"),
            Citation(source_id="s2", source_title="來源二"),
        ]
        confidence = _estimate_confidence(answer, citations)
        assert confidence == "high"

    def test_medium_confidence_with_citation(self):
        """測試中等信心程度（有引用）。"""
        answer = "簡短回答"
        citations = [Citation(source_id="s1", source_title="來源一")]
        confidence = _estimate_confidence(answer, citations)
        assert confidence == "medium"

    def test_medium_confidence_long_answer(self):
        """測試中等信心程度（長回答）。"""
        answer = "這是一個較長的回答" * 10  # 超過 100 字元
        citations = []
        confidence = _estimate_confidence(answer, citations)
        assert confidence == "medium"

    def test_low_confidence(self):
        """測試低信心程度。"""
        answer = "短"
        citations = []
        confidence = _estimate_confidence(answer, citations)
        assert confidence == "low"

    def test_no_answer(self):
        """測試無回答時。"""
        confidence = _estimate_confidence("", [])
        assert confidence is None
