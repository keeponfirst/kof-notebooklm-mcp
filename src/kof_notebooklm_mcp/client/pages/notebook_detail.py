"""
筆記本詳細頁面物件。

處理單一筆記本的詳細資訊和來源列表操作。
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from playwright.async_api import Locator, Page

from ...config import Config
from .base import BasePage

logger = logging.getLogger(__name__)


class NotebookPageExtractionError(RuntimeError):
    """NotebookLM 詳細頁尚未就緒，或目前 DOM 無法可靠解析。"""


class SourceExtractionError(NotebookPageExtractionError):
    """來源面板無法可靠解析。"""


_ANSWER_UI_CONTROL_MARKERS = (
    "跳到最底部",
    "按一下即可開啟引用內容詳細資料",
    "答得好",
    "有待加強",
    "jump to the bottom",
    "click to open citation details",
    "good response",
    "needs improvement",
)

_ANSWER_UI_FEATURE_MARKERS = (
    "ai 簡報",
    "ai 學習卡",
    "ai 互動式測驗",
    "ai 資訊圖表",
    "ai podcast",
    "ai 心智圖",
    "audio overview",
    "video overview",
    "study guide",
    "flashcards",
    "infographic",
)


def detect_answer_ui_pollution(text: str) -> list[str]:
    """辨識誤把 NotebookLM 工作區介面當成回答正文的情況。"""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if not normalized:
        return []

    control_hits = [marker for marker in _ANSWER_UI_CONTROL_MARKERS if marker in normalized]
    feature_hits = [marker for marker in _ANSWER_UI_FEATURE_MARKERS if marker in normalized]
    source_generation_count = normalized.count("根據來源") + normalized.count(
        "based on your sources"
    )

    if len(control_hits) >= 2 or len(feature_hits) >= 4 or source_generation_count >= 4:
        return [*control_hits, *feature_hits]
    return []


# NotebookLM 筆記本詳細頁面選擇器
SELECTORS = {
    # 筆記本標題
    "notebook_title": [
        '[data-testid="notebook-title"]',
        'h1',
        '[class*="notebook"][class*="title"]',
        '[contenteditable="true"]',
    ],
    # 來源面板
    "sources_panel": [
        "section.source-panel",  # NotebookLM current source panel
        '[data-testid="sources-panel"]',
        '[aria-label*="Sources"]',
        '[aria-label*="來源"]',
        '[class*="sources"]',
        '[class*="source-list"]',
    ],
    # 單一來源項目
    "source_items": [
        "div.single-source-container",  # NotebookLM current source row
        '[data-testid="source-item"]',
        '[role="listitem"]',
        '[class*="source-item"]',
        '[class*="source"][class*="card"]',
    ],
    # 來源標題
    "source_title": [
        "div.source-title",  # NotebookLM current source title
        '[data-testid="source-title"]',
        'h3',
        'h4',
        '[class*="title"]',
        '[class*="name"]',
    ],
    # 來源類型圖示/標籤
    "source_type": [
        '[data-testid="source-type"]',
        '[class*="type"]',
        '[class*="icon"]',
        'svg',
    ],
    # 聊天輸入框
    "chat_input": [
        '[data-testid="chat-input"]',
        'textarea[placeholder*="Ask"]',
        'textarea[placeholder*="問"]',
        'textarea',
        '[contenteditable="true"]',
    ],
    # 新增來源按鈕
    "add_source_button": [
        'button.add-source-button',  # 當前 UI
        'button[aria-label="新增來源"]',
        'button:has-text("新增來源")',
        'button[aria-label="Add source"]',
        'button:has-text("Add source")',
        '[data-testid="add-source"]',
        '[class*="add"][class*="source"]',
    ],
    # 新增來源對話框
    "add_source_dialog": [
        'mat-dialog-container',  # Angular Material Dialog
        '[data-testid="add-source-dialog"]',
        '[role="dialog"]',
        '[class*="dialog"]',
        '[class*="modal"]',
    ],
    # URL 輸入選項
    "url_option": [
        'button:has(mat-icon:has-text("link"))',  # 當前 UI (網址)
        '[data-testid="url-option"]',
        'button:has-text("Website")',
        'button:has-text("Link")',
        'button:has-text("網站")',
        'button:has-text("連結")',
    ],
    # 文字輸入選項
    "text_option": [
        'button:has(mat-icon:has-text("content_paste"))',  # 當前 UI (複製的文字)
        'button:has-text("複製的文字")',
        '[data-testid="text-option"]',
        'button:has-text("Copied text")',
        'button:has-text("Paste text")',
        'button:has-text("貼上文字")',
    ],
    # URL 輸入欄位
    "url_input": [
        'textarea[placeholder*="網址"]',  # 當前 UI
        'textarea[placeholder*="連結"]',
        '[data-testid="url-input"]',
        'input[type="url"]',
        'input[placeholder*="http"]',
        'input[name*="url"]',
    ],
    # 文字輸入欄位
    "text_input": [
        'textarea[placeholder*="貼上的文字"]',  # 當前 UI (中文)
        'textarea[placeholder*="Paste text"]',  # 當前 UI (英文)
        '[data-testid="text-input"]',
        'textarea[placeholder*="Paste"]',
        'textarea[placeholder*="貼上"]',
        'textarea:not([placeholder*="Ask"])',
    ],
    # 筆記本標題輸入欄位
    "notebook_title_input": [
        "input.title-input",  # NotebookLM current notebook title field
        '[data-testid="notebook-title-input"]',
    ],
    # 來源標題輸入欄位（貼上文字來源的對話框可能顯示）
    "title_input": [
        '[data-testid="title-input"]',
        'input[placeholder*="Title"]',
        'input[placeholder*="標題"]',
        'input[name*="title"]',
    ],
    # 提交/插入按鈕
    "submit_button": [
        'mat-dialog-container button:has-text("插入")',  # NotebookLM current copied-text dialog
        'mat-dialog-container button:has-text("Insert")',
        '[role="dialog"] button:has-text("插入")',
        '[role="dialog"] button:has-text("Insert")',
        '[data-testid="submit-source"]',
        'button[type="submit"]',
        'button:has-text("Insert")',
        'button:has-text("Add")',
        'button:has-text("插入")',
        'button:has-text("新增")',
    ],
    # 處理中指示器
    "processing_indicator": [
        '[data-testid="processing"]',
        '[class*="loading"]',
        '[class*="spinner"]',
        '[class*="processing"]',
        '[aria-busy="true"]',
    ],
    # 成功訊息
    "success_message": [
        '[data-testid="success"]',
        '[class*="success"]',
        '[role="alert"]',
    ],
    # 錯誤訊息
    "error_message": [
        '[data-testid="error"]',
        '[class*="error"]',
        '[role="alert"][class*="error"]',
    ],
    # ===== 聊天/查詢相關選擇器 (2026-01 更新) =====
    # 聊天面板
    "chat_panel": [
        '.chat-panel-content',
        '[data-testid="chat-panel"]',
        '[aria-label*="Chat"]',
        '[class*="chat"]',
    ],
    # 聊天輸入框（更精確）
    "chat_textarea": [
        'textarea.query-box-input',  # 當前 UI
        '[data-testid="chat-input"]',
        'textarea[placeholder*="Ask"]',
        'textarea[placeholder*="問"]',
    ],
    # 發送按鈕
    "send_button": [
        'button.actions-enter-button',  # 當前 UI
        '[data-testid="send-button"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="發送"]',
        'button[aria-label*="Submit"]',
        'button:has(mat-icon:has-text("arrow_forward"))',
    ],
    # AI 回應容器 (備用)
    "response_container": [
        '.chat-message-pair:has(.to-user-message-inner-content)',  # 當前 UI
        '[data-testid="ai-response"]',
    ],
    # 回應文字內容
    "response_text": [
        '.message-text-content',  # 當前 UI
        '[data-testid="response-text"]',
        '.to-user-message-inner-content [class*="markdown"]',
    ],
    # 回應中的引用/來源參考
    "citation": [
        '.citation-marker',  # 當前 UI
        '[class*="citation"]',
        '[class*="reference"]',
        '[class*="source-ref"]',
        'sup',
        '[class*="footnote"]',
    ],
    # 引用詳細資訊（懸停或點擊後顯示）
    "citation_detail": [
        '.citation-tooltip-panel',  # 當前 UI
        '.citation-tooltip',
        '[data-testid="citation-detail"]',
        '[class*="citation"][class*="popup"]',
        '[class*="citation"][class*="tooltip"]',
        '[class*="reference"][class*="detail"]',
        '[role="tooltip"]',
    ],
    # 引用詳細資訊中的來源標題
    "citation_title": [
        '.citation-tooltip-header',  # 當前 UI
        '[data-testid="citation-title"]',
        '[class*="citation"][class*="title"]',
    ],
    # 引用詳細資訊中的原文摘錄
    "citation_excerpt": [
        '.citation-tooltip-content',  # 當前 UI
        '[data-testid="citation-excerpt"]',
        '[class*="citation"][class*="content"]',
    ],
    # 正在輸入/思考指示器
    "typing_indicator": [
        '[data-testid="typing-indicator"]',
        '.typing-indicator',
        '.thinking-indicator',
        '.generating-indicator',
        '[aria-label*="typing"]',
        '[aria-label*="thinking"]',
    ],
    # 停止生成按鈕
    "stop_button": [
        '[data-testid="stop-button"]',
        'button[aria-label*="Stop"]',
        'button[aria-label*="停止"]',
        'button:has-text("Stop")',
        '[class*="stop"] button',
    ],
    # 聊天訊息項目
    "chat_message": [
        '[data-testid="chat-message"]',
        '[class*="message"]',
        '[role="listitem"]',
        '[class*="chat"][class*="item"]',
    ],
    # 使用者訊息
    "user_message": [
        '[data-testid="user-message"]',
        '[class*="message"][class*="user"]',
        '[class*="message"][class*="human"]',
        '[class*="user"][class*="chat"]',
    ],
    # AI 訊息
    "ai_message": [
        'mat-card-content.to-user-message-inner-content',  # 當前 UI
        '.to-user-message-inner-content',
        'chat-message:has(.to-user-message-card-content) '
        'mat-card-content.message-content',
        '[data-testid="ai-message"]',
    ],
    # 建議問題
    "suggested_questions": [
        'chip-list button',  # 當前 UI (通常是 chip 按鈕)
        '[data-testid="suggested-questions"]',
        '[class*="suggested"]',
        '[class*="follow-up"]',
        '[class*="related"][class*="questions"]',
    ],
}


SourceType = Literal["url", "text", "pdf", "gdoc", "gslides", "youtube", "audio", "unknown"]


@dataclass
class SourceInfo:
    """來源資訊。"""

    id: str
    title: str
    type: SourceType
    url: str | None = None
    added_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "url": self.url,
            "added_at": self.added_at,
        }


@dataclass
class NotebookDetail:
    """筆記本詳細資訊。"""

    id: str
    name: str
    source_count: int
    created_at: str | None = None
    updated_at: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        return {
            "id": self.id,
            "name": self.name,
            "source_count": self.source_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "description": self.description,
        }


class NotebookDetailPage(BasePage):
    """
    NotebookLM 筆記本詳細頁面。

    處理單一筆記本的檢視、來源管理和查詢操作。
    """

    def __init__(self, page: Page, config: Config | None = None):
        super().__init__(page, config)
        self.base_url = "https://notebooklm.google.com"
        self._current_notebook_id: str | None = None

    async def navigate_to_notebook(self, notebook_id: str) -> None:
        """
        導航到指定筆記本。

        Args:
            notebook_id: 筆記本 ID
        """
        logger.info(f"正在導航到筆記本: {notebook_id}")
        url = f"{self.base_url}/notebook/{notebook_id}"
        await self.navigate(url)
        self._current_notebook_id = notebook_id
        await self._wait_for_notebook_ready()

    async def _wait_for_notebook_ready(self, timeout_ms: int = 15000) -> None:
        """等待詳細頁的核心 UI 出現，避免把載入中頁面判成空筆記本。"""
        ready_selector = ", ".join(
            [
                SELECTORS["notebook_title_input"][0],
                SELECTORS["sources_panel"][0],
                SELECTORS["chat_textarea"][0],
            ]
        )
        try:
            await self.page.locator(ready_selector).first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise NotebookPageExtractionError(
                "NotebookLM 詳細頁在時限內未完成載入"
            ) from exc

        # 核心容器出現後，Angular 仍可能正在填入標題與來源列。
        await self.page.wait_for_timeout(750)

    async def _get_notebook_title(self) -> str:
        """取得筆記本標題。"""
        for selector in SELECTORS["notebook_title_input"]:
            try:
                elem = self.page.locator(selector).first
                if await elem.is_visible():
                    value = await elem.input_value()
                    if value.strip():
                        return value.strip()
            except Exception:
                continue

        for selector in SELECTORS["notebook_title"]:
            try:
                elem = self.page.locator(selector).first
                text = await self.safe_get_text(elem)
                if text.strip():
                    return text.strip()
            except Exception:
                continue

        raise NotebookPageExtractionError("無法可靠提取筆記本標題")

    async def _find_sources_panel(self) -> Locator | None:
        """尋找來源面板。"""
        for selector in SELECTORS["sources_panel"]:
            try:
                panel = self.page.locator(selector).first
                if await panel.is_visible():
                    return panel
            except Exception:
                continue

        return None

    async def _find_source_items(self) -> list[Locator]:
        """尋找所有來源項目。"""
        # 先嘗試找來源面板
        panel = await self._find_sources_panel()
        if panel is None:
            raise SourceExtractionError("找不到來源面板，無法確認來源數量")

        for selector in SELECTORS["source_items"]:
            try:
                items = panel.locator(selector)
                count = await items.count()
                if count > 0:
                    logger.debug(f"使用選擇器 '{selector}' 找到 {count} 個來源項目")
                    return [items.nth(i) for i in range(count)]
            except Exception:
                continue

        return []

    async def _extract_source_id(self, item: Locator) -> str | None:
        """從來源項目提取 ID。"""
        # 嘗試從各種屬性取得 ID
        for attr in ["data-source-id", "data-id", "id"]:
            value = await self.safe_get_attribute(item, attr)
            if value:
                return value

        # 嘗試從連結取得
        try:
            links = item.locator("a")
            if await links.count() > 0:
                href = await self.safe_get_attribute(links.first, "href")
                if href:
                    match = re.search(r"source[=/]([^/?&]+)", href)
                    if match:
                        return match.group(1)
        except Exception:
            pass

        # 使用索引作為備用 ID
        return None

    async def _extract_source_title(self, item: Locator) -> str:
        """從來源項目提取標題。"""
        for selector in SELECTORS["source_title"]:
            try:
                title_elem = item.locator(selector).first
                text = await self.safe_get_text(title_elem)
                if text.strip():
                    return text.strip()
            except Exception:
                continue

        # 備用：使用項目的第一行文字
        full_text = await self.safe_get_text(item)
        if full_text:
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            if lines:
                return lines[0]

        return "未命名來源"

    async def _detect_source_type(self, item: Locator) -> SourceType:
        """
        偵測來源類型。

        根據 UI 元素、圖示或文字推斷來源類型。
        """
        text = (await self.safe_get_text(item)).lower()

        # 根據文字內容推斷
        if any(x in text for x in ["youtube", "youtu.be", "影片", "video"]):
            return "youtube"
        if any(x in text for x in ["pdf", ".pdf"]):
            return "pdf"
        if any(x in text for x in ["google doc", "docs.google", "文件"]):
            return "gdoc"
        if any(x in text for x in ["google slide", "簡報", "slides.google"]):
            return "gslides"
        if any(x in text for x in ["audio", "音訊", "mp3", "wav"]):
            return "audio"
        if any(x in text for x in ["http://", "https://", "www."]):
            return "url"
        if any(x in text for x in ["pasted text", "貼上文字", "text", "markdown"]):
            return "text"

        # 嘗試從 data 屬性取得類型
        type_attr = await self.safe_get_attribute(item, "data-source-type")
        if type_attr:
            type_lower = type_attr.lower()
            if type_lower in ["url", "text", "pdf", "gdoc", "gslides", "youtube", "audio"]:
                return type_lower  # type: ignore

        return "unknown"

    async def _extract_source_url(self, item: Locator) -> str | None:
        """從來源項目提取 URL。"""
        # 嘗試從連結取得
        try:
            links = item.locator("a[href^='http']")
            count = await links.count()
            if count > 0:
                href = await self.safe_get_attribute(links.first, "href")
                # 排除 NotebookLM 內部連結
                if href and "notebooklm.google.com" not in href:
                    return href
        except Exception:
            pass

        # 嘗試從文字中提取 URL
        text = await self.safe_get_text(item)
        urls = re.findall(r'https?://[^\s<>"]+', text)
        for url in urls:
            if "notebooklm.google.com" not in url:
                return url

        return None

    async def get_notebook_detail(self, notebook_id: str) -> NotebookDetail:
        """
        取得筆記本詳細資訊。

        Args:
            notebook_id: 筆記本 ID

        Returns:
            筆記本詳細資訊
        """
        logger.info(f"正在取得筆記本詳細資訊: {notebook_id}")

        # 導航到筆記本（如果還沒在該頁面）
        current_url = await self.get_current_url()
        if notebook_id not in current_url:
            await self.navigate_to_notebook(notebook_id)
        else:
            await self._wait_for_notebook_ready()

        # 取得標題
        name = await self._get_notebook_title()

        # 計算來源數量
        source_items = await self._find_source_items()
        source_count = len(source_items)

        logger.info(f"筆記本 '{name}' 有 {source_count} 個來源")

        return NotebookDetail(
            id=notebook_id,
            name=name,
            source_count=source_count,
            created_at=None,  # NotebookLM UI 可能不顯示這些
            updated_at=None,
            description=None,
        )

    async def list_sources(self, notebook_id: str) -> list[SourceInfo]:
        """
        列出筆記本中的所有來源。

        Args:
            notebook_id: 筆記本 ID

        Returns:
            來源資訊列表
        """
        logger.info(f"正在列出筆記本 {notebook_id} 的來源...")

        # 導航到筆記本
        current_url = await self.get_current_url()
        if notebook_id not in current_url:
            await self.navigate_to_notebook(notebook_id)
        else:
            await self._wait_for_notebook_ready()

        # 尋找來源項目
        items = await self._find_source_items()
        logger.info(f"找到 {len(items)} 個來源項目")

        sources: list[SourceInfo] = []

        for idx, item in enumerate(items):
            try:
                source_id = await self._extract_source_id(item)
                if not source_id:
                    source_id = f"source_{idx}"

                title = await self._extract_source_title(item)
                source_type = await self._detect_source_type(item)
                url = await self._extract_source_url(item)

                sources.append(
                    SourceInfo(
                        id=source_id,
                        title=title,
                        type=source_type,
                        url=url,
                        added_at=None,
                    )
                )
            except Exception as e:
                logger.warning(f"處理來源項目時發生錯誤: {e}")
                continue

        logger.info(f"成功提取 {len(sources)} 個來源資訊")
        return sources

    async def is_chat_available(self) -> bool:
        """檢查聊天功能是否可用。"""
        for selector in SELECTORS["chat_input"]:
            try:
                elem = self.page.locator(selector).first
                if await elem.is_visible():
                    return True
            except Exception:
                continue

        return False

    async def _click_add_source_button(self) -> bool:
        """
        點擊新增來源按鈕。

        Returns:
            是否成功點擊
        """
        logger.info("正在尋找並點擊新增來源按鈕...")

        for selector in SELECTORS["add_source_dialog"]:
            try:
                dialog = self.page.locator(selector).first
                if await dialog.is_visible():
                    logger.info("新增來源對話框已開啟")
                    return True
            except Exception:
                continue

        for selector in SELECTORS["add_source_button"]:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=3000):
                    await button.click()
                    logger.debug(f"成功點擊新增來源按鈕 (選擇器: {selector})")
                    await self.page.wait_for_timeout(1000)  # 等待對話框開啟
                    return True
            except Exception as e:
                logger.debug(f"選擇器 '{selector}' 失敗: {e}")
                continue

        logger.warning("找不到新增來源按鈕")
        return False

    async def _wait_for_dialog(self) -> bool:
        """
        等待新增來源對話框出現。

        Returns:
            對話框是否出現
        """
        for selector in SELECTORS["add_source_dialog"]:
            try:
                dialog = self.page.locator(selector).first
                await dialog.wait_for(timeout=5000, state="visible")
                logger.debug(f"對話框已開啟 (選擇器: {selector})")
                return True
            except Exception:
                continue

        # 如果沒找到對話框，可能是直接顯示輸入欄位
        return True

    async def _select_url_option(self) -> bool:
        """
        選擇 URL 來源選項。

        Returns:
            是否成功選擇
        """
        logger.info("正在選擇 URL 來源類型...")

        for selector in SELECTORS["url_option"]:
            try:
                option = self.page.locator(selector).first
                if await option.is_visible(timeout=3000):
                    await option.click()
                    logger.debug(f"成功選擇 URL 選項 (選擇器: {selector})")
                    await self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue

        # URL 選項可能已經是預設選項
        logger.debug("找不到 URL 選項按鈕，可能已是預設選項")
        return True

    async def _select_text_option(self) -> bool:
        """
        選擇文字來源選項。

        Returns:
            是否成功選擇
        """
        logger.info("正在選擇文字來源類型...")

        for selector in SELECTORS["text_option"]:
            try:
                option = self.page.locator(selector).first
                if await option.is_visible(timeout=3000):
                    await option.click()
                    logger.debug(f"成功選擇文字選項 (選擇器: {selector})")
                    await self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue

        logger.warning("找不到文字選項按鈕")
        return False

    async def _input_url(self, url: str) -> bool:
        """
        輸入 URL。

        Args:
            url: 要輸入的 URL

        Returns:
            是否成功輸入
        """
        logger.info(f"正在輸入 URL: {url[:50]}...")

        for selector in SELECTORS["url_input"]:
            try:
                input_elem = self.page.locator(selector).first
                if await input_elem.is_visible(timeout=3000):
                    await input_elem.fill(url)
                    logger.debug(f"成功輸入 URL (選擇器: {selector})")
                    return True
            except Exception:
                continue

        logger.warning("找不到 URL 輸入欄位")
        return False

    async def _input_text(self, text: str) -> bool:
        """
        輸入文字內容。

        Args:
            text: 要輸入的文字

        Returns:
            是否成功輸入
        """
        logger.info(f"正在輸入文字內容 ({len(text)} 字元)...")

        for selector in SELECTORS["text_input"]:
            try:
                input_elem = self.page.locator(selector).first
                if await input_elem.is_visible(timeout=3000):
                    await input_elem.fill(text)
                    logger.debug(f"成功輸入文字 (選擇器: {selector})")
                    return True
            except Exception:
                continue

        logger.warning("找不到文字輸入欄位")
        return False

    async def _input_title(self, title: str) -> bool:
        """
        輸入標題（可選）。

        Args:
            title: 標題

        Returns:
            是否成功輸入
        """
        logger.info(f"正在輸入標題: {title}")

        for selector in SELECTORS["title_input"]:
            try:
                input_elem = self.page.locator(selector).first
                if await input_elem.is_visible(timeout=2000):
                    await input_elem.fill(title)
                    logger.debug(f"成功輸入標題 (選擇器: {selector})")
                    return True
            except Exception:
                continue

        logger.debug("找不到標題輸入欄位，可能不是必填")
        return False

    async def _click_submit(self) -> bool:
        """
        點擊提交按鈕。

        Returns:
            是否成功點擊
        """
        logger.info("正在點擊提交按鈕...")

        for selector in SELECTORS["submit_button"]:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=3000):
                    # 檢查按鈕是否可用
                    is_disabled = await button.is_disabled()
                    if not is_disabled:
                        await button.click()
                        logger.debug(f"成功點擊提交按鈕 (選擇器: {selector})")
                        return True
            except Exception:
                continue

        logger.warning("找不到或無法點擊提交按鈕")
        return False

    async def _wait_for_processing(self, timeout_ms: int = 60000) -> str:
        """
        等待來源處理完成。

        Args:
            timeout_ms: 逾時時間（毫秒）

        Returns:
            處理狀態: "complete", "processing", "failed"
        """
        logger.info("正在等待來源處理...")

        start_time = await self.page.evaluate("Date.now()")

        while True:
            # 檢查是否有錯誤訊息
            for selector in SELECTORS["error_message"]:
                try:
                    error = self.page.locator(selector).first
                    if await error.is_visible(timeout=500):
                        error_text = await self.safe_get_text(error)
                        logger.warning(f"發現錯誤訊息: {error_text}")
                        return "failed"
                except Exception:
                    pass

            # 檢查是否有成功訊息
            for selector in SELECTORS["success_message"]:
                try:
                    success = self.page.locator(selector).first
                    if await success.is_visible(timeout=500):
                        logger.info("來源新增成功")
                        return "complete"
                except Exception:
                    pass

            # 檢查處理中指示器
            is_processing = False
            for selector in SELECTORS["processing_indicator"]:
                try:
                    indicator = self.page.locator(selector).first
                    if await indicator.is_visible(timeout=500):
                        is_processing = True
                        break
                except Exception:
                    pass

            if not is_processing:
                # 沒有處理中指示器，檢查對話框是否已關閉
                dialog_visible = False
                for selector in SELECTORS["add_source_dialog"]:
                    try:
                        dialog = self.page.locator(selector).first
                        if await dialog.is_visible(timeout=500):
                            dialog_visible = True
                            break
                    except Exception:
                        pass

                if not dialog_visible:
                    logger.info("對話框已關閉，假設處理完成")
                    return "complete"

            # 檢查逾時
            current_time = await self.page.evaluate("Date.now()")
            if current_time - start_time > timeout_ms:
                logger.warning("等待處理逾時")
                return "processing"

            await self.page.wait_for_timeout(1000)

    async def add_url_source(self, notebook_id: str, url: str) -> dict[str, Any]:
        """
        新增 URL 來源到筆記本。

        Args:
            notebook_id: 筆記本 ID
            url: 要新增的 URL

        Returns:
            操作結果字典
        """
        logger.info(f"正在新增 URL 來源到筆記本 {notebook_id}: {url}")

        # 導航到筆記本
        current_url = await self.get_current_url()
        if notebook_id not in current_url:
            await self.navigate_to_notebook(notebook_id)

        # 點擊新增來源按鈕
        if not await self._click_add_source_button():
            return {
                "success": False,
                "error": "找不到新增來源按鈕",
            }

        # 等待對話框
        await self._wait_for_dialog()

        # 選擇 URL 選項
        await self._select_url_option()

        # 輸入 URL
        if not await self._input_url(url):
            return {
                "success": False,
                "error": "無法輸入 URL",
            }

        # 點擊提交
        if not await self._click_submit():
            return {
                "success": False,
                "error": "無法點擊提交按鈕",
            }

        # 等待處理
        status = await self._wait_for_processing()

        # 嘗試取得新增的來源標題
        await self.page.wait_for_timeout(2000)
        title = url.split("/")[-1] or url  # 使用 URL 最後一段作為預設標題

        return {
            "success": status != "failed",
            "source_id": None,  # NotebookLM 不一定會顯示 ID
            "title": title,
            "processing_status": status,
            "message": (
                "來源已新增"
                if status == "complete"
                else "來源正在處理中"
                if status == "processing"
                else "新增來源失敗"
            ),
        }

    async def add_text_source(
        self,
        notebook_id: str,
        text: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        """
        新增文字來源到筆記本。

        Args:
            notebook_id: 筆記本 ID
            text: 文字內容
            title: 標題（可選）

        Returns:
            操作結果字典
        """
        logger.info(f"正在新增文字來源到筆記本 {notebook_id} ({len(text)} 字元)")

        # 導航到筆記本
        current_url = await self.get_current_url()
        if notebook_id not in current_url:
            await self.navigate_to_notebook(notebook_id)

        # 點擊新增來源按鈕
        if not await self._click_add_source_button():
            return {
                "success": False,
                "error": "找不到新增來源按鈕",
            }

        # 等待對話框
        await self._wait_for_dialog()

        # 選擇文字選項
        if not await self._select_text_option():
            return {
                "success": False,
                "error": "找不到文字來源選項",
            }

        # 輸入標題（如果提供）
        final_title = title or f"文字來源 ({len(text)} 字元)"
        await self._input_title(final_title)

        # 輸入文字內容
        if not await self._input_text(text):
            return {
                "success": False,
                "error": "無法輸入文字內容",
            }

        # 點擊提交
        if not await self._click_submit():
            return {
                "success": False,
                "error": "無法點擊提交按鈕",
            }

        # 等待處理
        status = await self._wait_for_processing()

        return {
            "success": status != "failed",
            "source_id": None,
            "title": final_title,
            "processing_status": status,
            "message": (
                "來源已新增"
                if status == "complete"
                else "來源正在處理中"
                if status == "processing"
                else "新增來源失敗"
            ),
        }

    # ===== 查詢/Ask 相關方法 =====

    async def _find_chat_input(self) -> Locator | None:
        """
        尋找聊天輸入框。

        Returns:
            輸入框 Locator，找不到則為 None
        """
        for selector in SELECTORS["chat_textarea"]:
            try:
                input_elem = self.page.locator(selector).first
                if await input_elem.is_visible(timeout=3000):
                    logger.debug(f"找到聊天輸入框 (選擇器: {selector})")
                    return input_elem
            except Exception:
                continue

        logger.warning("找不到聊天輸入框")
        return None

    async def _find_send_button(self) -> Locator | None:
        """
        尋找發送按鈕。

        Returns:
            按鈕 Locator，找不到則為 None
        """
        for selector in SELECTORS["send_button"]:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=2000):
                    logger.debug(f"找到發送按鈕 (選擇器: {selector})")
                    return button
            except Exception:
                continue

        logger.warning("找不到發送按鈕")
        return None

    async def _input_question(self, question: str) -> bool:
        """
        在聊天輸入框輸入問題。

        Args:
            question: 要輸入的問題

        Returns:
            是否成功輸入
        """
        logger.info("正在輸入問題 (question_length=%d)", len(question))

        input_elem = await self._find_chat_input()
        if not input_elem:
            return False

        try:
            await input_elem.fill(question)
            await self.page.wait_for_timeout(300)  # 等待輸入完成
            return True
        except Exception as e:
            logger.warning(f"輸入問題失敗: {e}")
            return False

    async def _submit_question(self) -> bool:
        """
        提交問題（點擊發送或按 Enter）。

        Returns:
            是否成功提交
        """
        logger.info("正在提交問題...")

        # 嘗試點擊發送按鈕
        send_button = await self._find_send_button()
        if send_button:
            try:
                is_disabled = await send_button.is_disabled()
                if not is_disabled:
                    await send_button.click()
                    logger.debug("透過點擊發送按鈕提交問題")
                    return True
            except Exception:
                pass

        # 備用方案：按 Enter 鍵
        input_elem = await self._find_chat_input()
        if input_elem:
            try:
                await input_elem.press("Enter")
                logger.debug("透過按 Enter 鍵提交問題")
                return True
            except Exception:
                pass

        logger.warning("無法提交問題")
        return False

    async def _count_ai_messages(self) -> int:
        """計算目前 AI 回覆數量，優先使用第一個能命中的選擇器。"""
        for selector in SELECTORS["ai_message"]:
            try:
                count = await self.page.locator(selector).count()
                if count > 0:
                    return count
            except Exception:
                continue
        return 0

    async def _get_latest_ai_candidate(
        self,
    ) -> tuple[Locator | None, str, dict[str, Any]]:
        """取得最新且通過介面污染檢查的 AI 回答候選。"""
        rejected_candidates = 0
        pollution_markers: set[str] = set()
        selectors_checked = 0

        for selector in SELECTORS["ai_message"]:
            selectors_checked += 1
            try:
                messages = self.page.locator(selector)
                count = await messages.count()
                if count == 0:
                    continue

                message = messages.last
                text = await self._extract_answer_text(message)
                if not text:
                    rejected_candidates += 1
                    continue

                pollution = detect_answer_ui_pollution(text)
                if pollution:
                    rejected_candidates += 1
                    pollution_markers.update(pollution)
                    logger.warning(
                        "拒絕疑似 NotebookLM 介面文字的回答候選 "
                        "(selector=%s, text_length=%d, marker_count=%d)",
                        selector,
                        len(text),
                        len(pollution),
                    )
                    continue

                return message, text, {
                    "selector": selector,
                    "selectors_checked": selectors_checked,
                    "rejected_candidates": rejected_candidates,
                }
            except Exception:
                continue

        return None, "", {
            "selectors_checked": selectors_checked,
            "rejected_candidates": rejected_candidates,
            "pollution_marker_count": len(pollution_markers),
        }

    async def _get_latest_ai_answer_text(self) -> str:
        """取得目前最後一則 AI 回覆文字，供串流完成判斷。"""
        _, text, _ = await self._get_latest_ai_candidate()
        return text

    async def _is_response_in_progress(self) -> bool:
        """檢查精確的生成中指示器，避免廣域 loading class 誤判整頁。"""
        for selector in [*SELECTORS["typing_indicator"], *SELECTORS["stop_button"]]:
            try:
                if await self.page.locator(selector).first.is_visible(timeout=300):
                    return True
            except Exception:
                continue
        return False

    async def _wait_for_response(
        self,
        timeout_ms: int = 90000,
        initial_ai_message_count: int = 0,
        initial_answer_text: str = "",
    ) -> dict[str, Any] | None:
        """
        等待 AI 回應完成。

        Args:
            timeout_ms: 逾時時間（毫秒）
            initial_ai_message_count: 送出問題前已有的 AI 回覆數量
            initial_answer_text: 送出問題前最後一則有效 AI 回覆

        Returns:
            回應資訊字典，包含 answer 和 citations
        """
        logger.info("正在等待 AI 回應...")

        start_time = await self.page.evaluate("Date.now()")

        # 首先等待回應開始（出現 typing indicator 或新訊息）
        response_started = False
        while not response_started:
            if await self._is_response_in_progress():
                response_started = True
                logger.debug("偵測到 AI 正在回應")

            # 檢查是否有新的 AI 訊息。不能只判斷「有訊息」，否則第二次提問
            # 會立刻把上一則回答誤當成這次的結果。
            if await self._count_ai_messages() > initial_ai_message_count:
                response_started = True
                logger.debug("偵測到新的 AI 訊息")

            latest_answer_text = await self._get_latest_ai_answer_text()
            if latest_answer_text and latest_answer_text != initial_answer_text:
                response_started = True
                logger.debug("偵測到 AI 回應內容變更")

            # 檢查逾時
            current_time = await self.page.evaluate("Date.now()")
            if current_time - start_time > timeout_ms:
                logger.warning("等待回應開始逾時")
                return None

            await self.page.wait_for_timeout(500)

        # 等待回應完成（typing indicator 消失）
        logger.info("AI 正在生成回應，等待完成...")

        last_answer_text = ""
        stable_answer_checks = 0
        stable_invalid_checks = 0

        while True:
            is_typing = await self._is_response_in_progress()

            if not is_typing:
                has_new_message = await self._count_ai_messages() > initial_ai_message_count
                _, current_answer_text, diagnostics = (
                    await self._get_latest_ai_candidate()
                )
                has_changed_answer = bool(
                    current_answer_text and current_answer_text != initial_answer_text
                )

                if has_changed_answer and current_answer_text == last_answer_text:
                    stable_answer_checks += 1
                else:
                    stable_answer_checks = 0
                    last_answer_text = current_answer_text

                # 新版 UI 可能沒有可辨識的 typing indicator，因此除了訊息數量，
                # 還要求回答文字連續三次（約三秒）不再變動，避免截到串流中的半成品。
                if has_changed_answer and stable_answer_checks >= 3:
                    logger.info("AI 回應完成")
                    return await self._extract_response()

                # 新訊息已穩定出現，但所有候選都無效時，不再等滿 90 秒才回報。
                if has_new_message and not current_answer_text:
                    stable_invalid_checks += 1
                    if stable_invalid_checks >= 3:
                        logger.warning(
                            "新 AI 訊息無法可靠解析 (diagnostics=%s)", diagnostics
                        )
                        return await self._extract_response()
                else:
                    stable_invalid_checks = 0

            # 檢查逾時
            current_time = await self.page.evaluate("Date.now()")
            if current_time - start_time > timeout_ms:
                logger.warning("等待回應完成逾時")
                return {
                    "error_code": "TIMEOUT",
                    "error": "等待 AI 回應完成逾時",
                }

            await self.page.wait_for_timeout(1000)

    async def _extract_response(self) -> dict[str, Any]:
        """
        提取最新的 AI 回應內容和引用。

        Returns:
            包含 answer、citations、follow_up_questions 的字典
        """
        logger.info("正在提取 AI 回應內容...")

        follow_up_questions: list[str] = []
        ai_message, answer, diagnostics = await self._get_latest_ai_candidate()

        if ai_message is None or not answer:
            return {
                "answer": "",
                "citations": [],
                "follow_up_questions": [],
                "error_code": "ANSWER_EXTRACTION_FAILED",
                "error": "NotebookLM 已產生回應，但無法可靠定位回答正文",
                "details": diagnostics,
            }

        citations = await self._extract_citations(ai_message)

        # 提取建議問題
        follow_up_questions = await self._extract_suggested_questions()

        return {
            "answer": answer,
            "citations": citations,
            "follow_up_questions": follow_up_questions,
        }

    async def _extract_answer_text(self, message_elem: Locator) -> str:
        """
        從訊息元素提取回應文字。

        Args:
            message_elem: 訊息元素 Locator

        Returns:
            回應文字
        """
        # 嘗試從特定的文字容器提取
        for selector in SELECTORS["response_text"]:
            try:
                text_elem = message_elem.locator(selector).last
                text = await self.safe_get_text(text_elem)
                if text.strip():
                    logger.debug(f"從 {selector} 提取到回應文字")
                    return text.strip()
            except Exception:
                continue

        # 備用：直接取得元素的文字內容
        text = await self.safe_get_text(message_elem)
        if text.strip():
            return text.strip()

        return ""

    async def _extract_citations(self, message_elem: Locator) -> list[dict[str, Any]]:
        """
        從訊息元素提取引用資訊。

        Args:
            message_elem: 訊息元素 Locator

        Returns:
            引用資訊列表
        """
        citations: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for selector in SELECTORS["citation"]:
            try:
                citation_elems = message_elem.locator(selector)
                count = await citation_elems.count()

                for i in range(count):
                    elem = citation_elems.nth(i)
                    citation_info = await self._extract_single_citation(elem)
                    if citation_info:
                        dedupe_key = (
                            str(citation_info.get("source_id") or ""),
                            str(citation_info.get("source_title") or ""),
                            str(citation_info.get("excerpt") or ""),
                        )
                        if dedupe_key not in seen:
                            citations.append(citation_info)
                            seen.add(dedupe_key)

                if citations:
                    logger.debug(f"從 {selector} 提取到 {len(citations)} 個引用")
                    break
            except Exception:
                continue

        return citations

    async def _extract_single_citation(self, elem: Locator) -> dict[str, Any] | None:
        """
        提取單一引用的資訊。

        Args:
            elem: 引用元素 Locator

        Returns:
            引用資訊字典
        """
        try:
            # 取得引用文字/編號
            text = await self.safe_get_text(elem)

            # 嘗試取得來源 ID 或標題
            source_id = await self.safe_get_attribute(elem, "data-source-id")
            source_title = await self.safe_get_attribute(elem, "title")
            source_title = source_title or await self.safe_get_attribute(elem, "aria-label")

            # 嘗試懸停以取得更多資訊
            excerpt = None
            try:
                await elem.hover()
                await self.page.wait_for_timeout(500)

                for detail_selector in SELECTORS["citation_detail"]:
                    try:
                        detail = self.page.locator(detail_selector).first
                        if await detail.is_visible(timeout=1000):
                            for title_selector in SELECTORS["citation_title"]:
                                try:
                                    title_elem = detail.locator(title_selector).first
                                    title_text = await self.safe_get_text(title_elem)
                                    if title_text.strip():
                                        source_title = title_text.strip()
                                        break
                                except Exception:
                                    continue

                            for excerpt_selector in SELECTORS["citation_excerpt"]:
                                try:
                                    excerpt_elem = detail.locator(excerpt_selector).first
                                    excerpt_text = await self.safe_get_text(excerpt_elem)
                                    if excerpt_text.strip():
                                        excerpt = excerpt_text.strip()
                                        break
                                except Exception:
                                    continue

                            if not excerpt:
                                excerpt = await self.safe_get_text(detail)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            if source_id or source_title or text.strip():
                return {
                    "source_id": source_id or f"citation_{text.strip()}",
                    "source_title": source_title or text.strip(),
                    "excerpt": excerpt,
                }
        except Exception as e:
            logger.debug(f"提取引用失敗: {e}")

        return None

    async def _extract_suggested_questions(self) -> list[str]:
        """
        提取建議的後續問題。

        Returns:
            建議問題列表
        """
        questions: list[str] = []

        for selector in SELECTORS["suggested_questions"]:
            try:
                container = self.page.locator(selector).first
                if await container.is_visible(timeout=2000):
                    # 尋找容器內的按鈕或連結
                    buttons = container.locator("button, a, [role='button']")
                    count = await buttons.count()

                    for i in range(min(count, 5)):  # 最多取 5 個
                        text = await self.safe_get_text(buttons.nth(i))
                        if text.strip() and len(text.strip()) > 5:
                            questions.append(text.strip())

                    if questions:
                        break
            except Exception:
                continue

        return questions

    async def ask(
        self,
        notebook_id: str,
        question: str,
        include_citations: bool = True,
        timeout_ms: int = 90000,
    ) -> dict[str, Any]:
        """
        向筆記本提問並取得 AI 回應。

        Args:
            notebook_id: 筆記本 ID
            question: 要提問的問題
            include_citations: 是否提取引用資訊
            timeout_ms: 等待回應的逾時時間（毫秒）

        Returns:
            包含 answer、citations、follow_up_questions 的結果字典
        """
        logger.info(
            "正在向筆記本 %s 提問 (question_length=%d)",
            notebook_id,
            len(question),
        )

        # 導航到筆記本
        current_url = await self.get_current_url()
        if notebook_id not in current_url:
            await self.navigate_to_notebook(notebook_id)
        else:
            await self._wait_for_notebook_ready()

        # 檢查聊天功能是否可用
        chat_input = await self._find_chat_input()
        if not chat_input:
            return {
                "success": False,
                "error": "找不到聊天輸入框，請確認筆記本有來源",
            }

        # 輸入問題
        if not await self._input_question(question):
            return {
                "success": False,
                "error": "無法輸入問題",
            }

        initial_ai_message_count = await self._count_ai_messages()
        initial_answer_text = await self._get_latest_ai_answer_text()

        # 提交問題
        if not await self._submit_question():
            return {
                "success": False,
                "error": "無法提交問題",
            }

        # 等待回應
        response = await self._wait_for_response(
            timeout_ms=timeout_ms,
            initial_ai_message_count=initial_ai_message_count,
            initial_answer_text=initial_answer_text,
        )

        if not response:
            return {
                "success": False,
                "error_code": "TIMEOUT",
                "error": "等待 AI 回應逾時",
            }

        if response.get("error_code"):
            return {
                "success": False,
                "error_code": response["error_code"],
                "error": response.get("error", "無法取得 AI 回應"),
                "details": response.get("details", {}),
            }

        # 處理結果
        answer = response.get("answer", "")
        if not answer:
            return {
                "success": False,
                "error_code": "ANSWER_EXTRACTION_FAILED",
                "error": "無法提取 AI 回應內容",
            }

        result: dict[str, Any] = {
            "success": True,
            "answer": answer,
        }

        if include_citations:
            result["citations"] = response.get("citations", [])

        result["follow_up_questions"] = response.get("follow_up_questions", [])

        logger.info(f"成功取得回應 ({len(answer)} 字元，{len(result.get('citations', []))} 個引用)")

        return result

    async def rename_notebook(self, new_title: str) -> bool:
        """
        重新命名筆記本。

        Args:
            new_title: 新標題

        Returns:
            是否成功
        """
        logger.info(f"正在將筆記本重新命名為: {new_title}")

        # 1. 嘗試直接找輸入框（有些 UI 可能直接顯示）
        input_elem = None
        for selector in SELECTORS["notebook_title_input"]:
            try:
                elem = self.page.locator(selector).first
                if await elem.is_visible(timeout=1000):
                    input_elem = elem
                    break
            except Exception:
                continue

        # 2. 如果沒找到輸入框，嘗試點擊標題
        if not input_elem:
            logger.debug("找不到標題輸入框，嘗試點擊標題以啟用編輯...")
            title_elem = None
            for selector in SELECTORS["notebook_title"]:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.is_visible(timeout=1000):
                        title_elem = elem
                        break
                except Exception:
                    continue

            if title_elem:
                try:
                    await title_elem.click()
                    await self.page.wait_for_timeout(500)

                    # 再次尋找輸入框
                    for selector in SELECTORS["notebook_title_input"]:
                        try:
                            elem = self.page.locator(selector).first
                            if await elem.is_visible(timeout=2000):
                                input_elem = elem
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

        if input_elem:
            try:
                await input_elem.fill(new_title)
                await input_elem.press("Enter")
                await self.page.wait_for_timeout(1000) # 等待存檔
                logger.info("重新命名成功")
                return True
            except Exception as e:
                logger.error(f"重新命名失敗: {e}")
                return False

        logger.warning("無法執行重新命名（找不到輸入框或標題）")
        return False
