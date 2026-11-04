"""頁面物件資料類別的單元測試。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kof_notebooklm_mcp.client.pages.notebook_detail import (
    SELECTORS,
    NotebookDetail,
    NotebookDetailPage,
    SourceExtractionError,
    SourceInfo,
    detect_answer_ui_pollution,
)
from kof_notebooklm_mcp.client.pages.notebooks import NotebookInfo


def test_current_notebook_title_selector_is_supported():
    """目前 NotebookLM 的標題欄位應可直接被重新命名流程找到。"""
    assert "input.title-input" in SELECTORS["notebook_title_input"]
    assert "input.title-input" not in SELECTORS["title_input"]


def test_current_source_list_selectors_are_supported():
    """目前 NotebookLM 的來源面板、列與標題應有優先選擇器。"""
    assert SELECTORS["sources_panel"][0] == "section.source-panel"
    assert SELECTORS["source_items"][0] == "div.single-source-container"
    assert SELECTORS["source_title"][0] == "div.source-title"


def test_current_copied_text_submit_selector_precedes_global_buttons():
    """來源對話框的插入按鈕必須先於可能被遮住的全頁按鈕。"""
    assert SELECTORS["submit_button"][0] == 'mat-dialog-container button:has-text("插入")'


def test_current_ai_response_and_citation_selectors_are_supported():
    """新版 NotebookLM 的回答與引用浮層應使用目前可見的 DOM。"""
    assert SELECTORS["ai_message"][0] == (
        "mat-card-content.to-user-message-inner-content"
    )
    assert SELECTORS["citation_detail"][0] == ".citation-tooltip-panel"
    assert SELECTORS["citation_title"][0] == ".citation-tooltip-header"
    assert SELECTORS["citation_excerpt"][0] == ".citation-tooltip-content"


@pytest.mark.asyncio
async def test_extract_citations_deduplicates_repeated_markers():
    """同一來源摘錄被多次標記時，只回傳一次，避免虛增引用數。"""
    citation_elems = MagicMock()
    citation_elems.count = AsyncMock(return_value=2)
    citation_elems.nth.side_effect = [MagicMock(), MagicMock()]
    message = MagicMock()
    message.locator.return_value = citation_elems

    detail = NotebookDetailPage(MagicMock())
    repeated = {
        "source_id": "citation_1",
        "source_title": "研究來源",
        "excerpt": "相同摘錄內容",
    }
    detail._extract_single_citation = AsyncMock(  # type: ignore[method-assign]
        side_effect=[repeated, repeated.copy()]
    )

    citations = await detail._extract_citations(message)

    assert citations == [repeated]


@pytest.mark.asyncio
async def test_count_ai_messages_uses_first_nonempty_current_selector():
    """計數應採第一個有命中的回答容器，供連續提問判斷新回覆。"""
    page = MagicMock()
    empty = MagicMock()
    empty.count = AsyncMock(return_value=0)
    current = MagicMock()
    current.count = AsyncMock(return_value=3)
    page.locator.side_effect = [empty, current]

    detail = NotebookDetailPage(page)

    assert await detail._count_ai_messages() == 3
    assert page.locator.call_args_list[0].args[0] == SELECTORS["ai_message"][0]


def test_answer_ui_pollution_rejects_captured_workspace_chrome():
    """工作區功能與評分按鈕文字不可被當成 AI 回答。"""
    text = (
        "系統現在會儲存所有工作階段的對話記錄，可在這裡刪除跳到最底部"
        "根據來源生成 AI 簡報根據來源內容生成 AI 學習卡"
        "根據來源內容生成 AI 互動式測驗根據來源內容生成 AI 資訊圖表"
        "根據來源內容生成 AI Podcast根據來源內容生成 AI 心智圖"
        "按一下即可開啟引用內容詳細資料複製答得好有待加強"
    )

    assert detect_answer_ui_pollution(text)


def test_answer_ui_pollution_allows_normal_notebooklm_discussion():
    """正常文章即使提到少數 NotebookLM 功能，也不應被誤殺。"""
    text = (
        "NotebookLM 的 AI 簡報適合快速建立共同脈絡，但不能取代來源驗證。"
        "若要保留成組織知識，仍需記錄主張、證據、適用邊界與反例。"
    )

    assert detect_answer_ui_pollution(text) == []


def test_answer_ui_pollution_rejects_source_generation_menu_alone():
    """只有「根據來源」選單重複達門檻時，也必須判為污染，不可回傳空清單。"""
    text = (
        "根據來源生成摘要。根據來源生成大綱。"
        "根據來源生成時間軸。根據來源生成常見問題。"
    )

    assert detect_answer_ui_pollution(text)


def test_answer_ui_pollution_rejects_english_source_generation_menu_alone():
    """英文介面的 based on your sources 重複達門檻時，同樣判為污染。"""
    text = (
        "Create a summary based on your sources. Create an outline based on your sources. "
        "Create a timeline based on your sources. Create FAQs based on your sources."
    )

    assert detect_answer_ui_pollution(text)


def test_answer_ui_pollution_allows_answer_citing_sources_below_threshold():
    """正常回答提到「根據來源」少於門檻，三條規則都不成立，不判污染。"""
    text = (
        "根據來源一，主張 A 有兩份實驗支持。根據來源二，反例出現在小樣本。"
        "根據來源三，適用邊界是資料量大於一千筆。"
    )

    assert detect_answer_ui_pollution(text) == []


@pytest.mark.asyncio
async def test_latest_ai_candidate_skips_polluted_selector():
    """第一個 selector 若誤抓介面，應繼續嘗試下一個精確候選。"""
    page = MagicMock()
    polluted_messages = MagicMock()
    polluted_messages.count = AsyncMock(return_value=1)
    polluted_messages.last = MagicMock()
    valid_messages = MagicMock()
    valid_messages.count = AsyncMock(return_value=1)
    valid_messages.last = MagicMock()
    page.locator.side_effect = [polluted_messages, valid_messages]

    detail = NotebookDetailPage(page)
    detail._extract_answer_text = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            "跳到最底部按一下即可開啟引用內容詳細資料答得好有待加強",
            "這是一段有根據、可被進一步研究的有效回答。",
        ]
    )

    message, answer, diagnostics = await detail._get_latest_ai_candidate()

    assert message is valid_messages.last
    assert answer == "這是一段有根據、可被進一步研究的有效回答。"
    assert diagnostics["selector"] == SELECTORS["ai_message"][1]
    assert diagnostics["rejected_candidates"] == 1


@pytest.mark.asyncio
async def test_extract_response_fails_closed_for_polluted_candidates():
    """所有候選都像介面文字時，應回傳明確錯誤而非假成功。"""
    page = MagicMock()
    messages = MagicMock()
    messages.count = AsyncMock(return_value=1)
    messages.last = MagicMock()
    page.locator.return_value = messages

    detail = NotebookDetailPage(page)
    detail._extract_answer_text = AsyncMock(  # type: ignore[method-assign]
        return_value="跳到最底部按一下即可開啟引用內容詳細資料答得好有待加強"
    )

    response = await detail._extract_response()

    assert response["answer"] == ""
    assert response["error_code"] == "ANSWER_EXTRACTION_FAILED"
    assert response["details"]["pollution_marker_count"] >= 2


@pytest.mark.asyncio
async def test_missing_source_panel_is_not_reported_as_empty_notebook():
    """找不到來源面板代表解析失敗，不代表筆記本真的有零個來源。"""
    detail = NotebookDetailPage(MagicMock())
    detail._find_sources_panel = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(SourceExtractionError):
        await detail._find_source_items()


@pytest.mark.asyncio
async def test_extract_source_id_skips_missing_link_without_waiting_for_attributes():
    """沒有來源連結時不應對不存在的元素讀取屬性而等到逾時。"""
    page = MagicMock()
    item = MagicMock()
    item.get_attribute = AsyncMock(return_value=None)
    links = MagicMock()
    links.count = AsyncMock(return_value=0)
    item.locator.return_value = links

    detail = NotebookDetailPage(page)
    source_id = await detail._extract_source_id(item)

    assert source_id is None
    links.count.assert_awaited_once()


@pytest.mark.asyncio
async def test_detects_current_markdown_source_as_text():
    """新版 UI 用 markdown 圖示標示貼上文字來源。"""
    item = MagicMock()
    item.text_content = AsyncMock(return_value="markdown\n# 研究準則")
    item.get_attribute = AsyncMock(return_value=None)

    detail = NotebookDetailPage(MagicMock())

    assert await detail._detect_source_type(item) == "text"


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
