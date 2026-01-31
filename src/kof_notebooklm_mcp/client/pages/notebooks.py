"""
筆記本列表頁面物件。

處理 NotebookLM 首頁的筆記本列表操作。
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from playwright.async_api import Page, Locator

from .base import BasePage
from ...config import Config

logger = logging.getLogger(__name__)


# NotebookLM UI 選擇器 (2026-01 更新)
# NotebookLM 使用 Angular Material 組件，ID 藏在標題 span 的 id 屬性中
# 格式: project-{notebook-id}-title
SELECTORS = {
    # 筆記本卡片的可能選擇器（優先順序從高到低）
    "notebook_cards": [
        'mat-card.project-button-card',  # 當前 NotebookLM 使用的主要選擇器
        '[data-testid="notebook-card"]',
        '.notebook-card',
        'a[href*="/notebook/"]',
    ],
    # 筆記本標題 - ID 可從此元素的 id 屬性提取
    # 格式: id="project-{notebook-id}-title"
    "notebook_title": [
        'span.project-button-title',  # 當前 NotebookLM 使用
        '[data-testid="notebook-title"]',
        '[class*="title"]',
    ],
    # 來源數量
    "source_count": [
        'span.project-button-subtitle-part-sources',  # 當前 NotebookLM 使用
        '[data-testid="source-count"]',
        '[class*="source"]',
    ],
    # 更新時間
    "updated_at": [
        'span.project-button-subtitle-part',  # 當前 NotebookLM 使用
        '[data-testid="updated-at"]',
        'time',
        '[class*="date"]',
    ],
    # 建立新筆記本按鈕
    "create_button": [
        'button[aria-label*="建立新的筆記本"]',  # 繁體中文 UI
        'button[aria-label*="Create new notebook"]',  # 英文 UI
        '.add-source-button',
        '[data-testid="create-notebook"]',
    ],
}


@dataclass
class NotebookInfo:
    """筆記本基本資訊。"""

    id: str
    name: str
    source_count: int | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        return {
            "id": self.id,
            "name": self.name,
            "source_count": self.source_count,
            "updated_at": self.updated_at,
        }


class NotebooksPage(BasePage):
    """
    NotebookLM 筆記本列表頁面。

    處理首頁的筆記本列表瀏覽和操作。
    """

    def __init__(self, page: Page, config: Config | None = None):
        super().__init__(page, config)
        self.base_url = "https://notebooklm.google.com"

    async def navigate_to_home(self) -> None:
        """導航到 NotebookLM 首頁。"""
        logger.info("正在導航到 NotebookLM 首頁...")
        await self.navigate(self.base_url)
        await self.page.wait_for_timeout(2000)  # 等待頁面穩定

    async def _find_notebook_cards(self) -> list[Locator]:
        """
        尋找頁面上的筆記本卡片元素。

        嘗試多種選擇器以適應可能的 UI 變化。
        """
        for selector in SELECTORS["notebook_cards"]:
            try:
                locators = self.page.locator(selector)
                count = await locators.count()
                if count > 0:
                    logger.debug(f"使用選擇器 '{selector}' 找到 {count} 個筆記本卡片")
                    return [locators.nth(i) for i in range(count)]
            except Exception as e:
                logger.debug(f"選擇器 '{selector}' 失敗: {e}")
                continue

        # 如果標準選擇器都失敗，嘗試尋找包含 notebook ID 的連結
        try:
            links = self.page.locator('a[href*="/notebook/"]')
            count = await links.count()
            if count > 0:
                logger.debug(f"透過連結找到 {count} 個筆記本")
                return [links.nth(i) for i in range(count)]
        except Exception:
            pass

        return []

    async def _extract_notebook_id(self, card: Locator) -> str | None:
        """從筆記本卡片元素中提取 ID。"""
        # 1. 嘗試從標題 span 的 id 屬性取得 (當前 NotebookLM 使用的格式)
        # 格式: id="project-{notebook-id}-title"
        try:
            title_span = card.locator('span.project-button-title').first
            span_id = await self.safe_get_attribute(title_span, "id")
            if span_id:
                match = re.search(r"project-([a-f0-9-]+)-title", span_id)
                if match:
                    logger.debug(f"從標題 span 提取到 ID: {match.group(1)}")
                    return match.group(1)
        except Exception as e:
            logger.debug(f"從標題 span 提取 ID 失敗: {e}")

        # 2. 嘗試從 href 屬性取得
        href = await self.safe_get_attribute(card, "href")
        if href:
            match = re.search(r"/notebook/([^/?]+)", href)
            if match:
                return match.group(1)

        # 3. 嘗試從 data 屬性取得
        for attr in ["data-notebook-id", "data-id", "id"]:
            value = await self.safe_get_attribute(card, attr)
            if value:
                # 如果是 project-xxx-title 格式，提取中間的 ID
                match = re.search(r"project-([a-f0-9-]+)", value)
                if match:
                    return match.group(1)
                return value

        # 4. 嘗試從子元素的連結取得
        try:
            link = card.locator('a[href*="/notebook/"]').first
            href = await self.safe_get_attribute(link, "href")
            if href:
                match = re.search(r"/notebook/([^/?]+)", href)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    async def _extract_notebook_title(self, card: Locator) -> str:
        """從筆記本卡片提取標題。"""
        for selector in SELECTORS["notebook_title"]:
            try:
                title_elem = card.locator(selector).first
                text = await self.safe_get_text(title_elem)
                if text.strip():
                    return text.strip()
            except Exception:
                continue

        # 備用：取得卡片的所有文字，使用第一行
        full_text = await self.safe_get_text(card)
        if full_text:
            lines = [l.strip() for l in full_text.split("\n") if l.strip()]
            if lines:
                return lines[0]

        return "未命名筆記本"

    async def _extract_source_count(self, card: Locator) -> int | None:
        """從筆記本卡片提取來源數量。"""
        for selector in SELECTORS["source_count"]:
            try:
                elem = card.locator(selector).first
                text = await self.safe_get_text(elem)
                if text:
                    # 嘗試從文字中提取數字
                    numbers = re.findall(r"\d+", text)
                    if numbers:
                        return int(numbers[0])
            except Exception:
                continue

        return None

    async def _extract_updated_at(self, card: Locator) -> str | None:
        """從筆記本卡片提取更新時間。"""
        for selector in SELECTORS["updated_at"]:
            try:
                elem = card.locator(selector).first
                # 優先使用 datetime 屬性
                datetime_attr = await self.safe_get_attribute(elem, "datetime")
                if datetime_attr:
                    return datetime_attr

                text = await self.safe_get_text(elem)
                if text.strip():
                    return text.strip()
            except Exception:
                continue

        return None

    async def list_notebooks(self, limit: int = 50) -> list[NotebookInfo]:
        """
        列出所有筆記本。

        Args:
            limit: 最大回傳數量

        Returns:
            筆記本資訊列表
        """
        logger.info(f"正在列出筆記本 (限制: {limit})...")

        # 確保在首頁
        current_url = await self.get_current_url()
        if "notebooklm.google.com" not in current_url or "/notebook/" in current_url:
            await self.navigate_to_home()

        # 等待頁面載入
        await self.page.wait_for_timeout(2000)

        # 尋找筆記本卡片
        cards = await self._find_notebook_cards()
        logger.info(f"找到 {len(cards)} 個筆記本卡片")

        notebooks: list[NotebookInfo] = []

        for card in cards[:limit]:
            try:
                notebook_id = await self._extract_notebook_id(card)
                if not notebook_id:
                    logger.warning("無法提取筆記本 ID，跳過此卡片")
                    continue

                name = await self._extract_notebook_title(card)
                source_count = await self._extract_source_count(card)
                updated_at = await self._extract_updated_at(card)

                notebooks.append(
                    NotebookInfo(
                        id=notebook_id,
                        name=name,
                        source_count=source_count,
                        updated_at=updated_at,
                    )
                )
            except Exception as e:
                logger.warning(f"處理筆記本卡片時發生錯誤: {e}")
                continue

        logger.info(f"成功提取 {len(notebooks)} 個筆記本資訊")
        return notebooks

    async def get_notebook_url(self, notebook_id: str) -> str:
        """取得筆記本的 URL。"""
        return f"{self.base_url}/notebook/{notebook_id}"

    async def create_notebook(self) -> str | None:
        """
        建立新筆記本。

        Returns:
            新筆記本 ID，若失敗則回傳 None
        """
        logger.info("正在建立新筆記本...")

        # 確保在首頁
        current_url = await self.get_current_url()
        if "notebooklm.google.com" not in current_url or "/notebook/" in current_url:
            await self.navigate_to_home()

        # 等待頁面載入
        await self.page.wait_for_timeout(2000)

        # 尋找並點擊建立按鈕
        create_btn = None
        for selector in SELECTORS["create_button"]:
            try:
                btn = self.page.locator(selector).first
                if await btn.is_visible():
                    create_btn = btn
                    logger.debug(f"找到建立按鈕: {selector}")
                    break
            except Exception:
                continue

        if not create_btn:
            logger.error("找不到建立新筆記本按鈕")
            return None

        # 點擊並等待導航
        try:
            async with self.page.expect_navigation(timeout=10000):
                await create_btn.click()
            
            # 等待新頁面載入
            await self.page.wait_for_timeout(3000)

            # 從 URL 提取 ID
            new_url = await self.get_current_url()
            match = re.search(r"/notebook/([^/?]+)", new_url)
            if match:
                notebook_id = match.group(1)
                logger.info(f"成功建立筆記本: {notebook_id}")
                return notebook_id
            
            logger.error(f"無法從 URL 提取新筆記本 ID: {new_url}")
            return None

        except Exception as e:
            logger.error(f"建立筆記本失敗: {e}")
            return None
