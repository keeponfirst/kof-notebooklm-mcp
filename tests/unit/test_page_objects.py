"""頁面物件資料類別的單元測試。"""

import pytest

from kof_notebooklm_mcp.client.pages.notebooks import NotebookInfo
from kof_notebooklm_mcp.client.pages.notebook_detail import NotebookDetail, SourceInfo


class TestNotebookInfo:
    """NotebookInfo 資料類別測試。"""

    def test_to_dict_complete(self):
        """測試完整資料的序列化。"""
        info = NotebookInfo(
            id="notebook123",
            name="測試筆記本",
            source_count=5,
            updated_at="2025-01-28T10:00:00Z",
        )
        d = info.to_dict()
        assert d["id"] == "notebook123"
        assert d["name"] == "測試筆記本"
        assert d["source_count"] == 5
        assert d["updated_at"] == "2025-01-28T10:00:00Z"

    def test_to_dict_minimal(self):
        """測試最小資料的序列化。"""
        info = NotebookInfo(id="abc", name="筆記本")
        d = info.to_dict()
        assert d["id"] == "abc"
        assert d["name"] == "筆記本"
        assert d["source_count"] is None
        assert d["updated_at"] is None


class TestNotebookDetail:
    """NotebookDetail 資料類別測試。"""

    def test_to_dict_complete(self):
        """測試完整資料的序列化。"""
        detail = NotebookDetail(
            id="notebook456",
            name="研究筆記本",
            source_count=10,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-28T12:00:00Z",
            description="這是一個研究筆記本",
        )
        d = detail.to_dict()
        assert d["id"] == "notebook456"
        assert d["name"] == "研究筆記本"
        assert d["source_count"] == 10
        assert d["created_at"] == "2025-01-01T00:00:00Z"
        assert d["updated_at"] == "2025-01-28T12:00:00Z"
        assert d["description"] == "這是一個研究筆記本"

    def test_to_dict_minimal(self):
        """測試最小資料的序列化。"""
        detail = NotebookDetail(id="xyz", name="空筆記本", source_count=0)
        d = detail.to_dict()
        assert d["id"] == "xyz"
        assert d["name"] == "空筆記本"
        assert d["source_count"] == 0
        assert d["created_at"] is None


class TestSourceInfo:
    """SourceInfo 資料類別測試。"""

    def test_to_dict_url_source(self):
        """測試 URL 來源的序列化。"""
        source = SourceInfo(
            id="src1",
            title="MCP 規格文件",
            type="url",
            url="https://modelcontextprotocol.io",
            added_at="2025-01-28T08:00:00Z",
        )
        d = source.to_dict()
        assert d["id"] == "src1"
        assert d["title"] == "MCP 規格文件"
        assert d["type"] == "url"
        assert d["url"] == "https://modelcontextprotocol.io"

    def test_to_dict_text_source(self):
        """測試文字來源的序列化。"""
        source = SourceInfo(
            id="src2",
            title="會議記錄",
            type="text",
            url=None,
        )
        d = source.to_dict()
        assert d["id"] == "src2"
        assert d["title"] == "會議記錄"
        assert d["type"] == "text"
        assert d["url"] is None

    def test_to_dict_pdf_source(self):
        """測試 PDF 來源的序列化。"""
        source = SourceInfo(
            id="src3",
            title="技術白皮書.pdf",
            type="pdf",
        )
        d = source.to_dict()
        assert d["type"] == "pdf"
