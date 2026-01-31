"""
基礎頁面物件類別。

提供所有 NotebookLM 頁面物件共用的方法。
"""

import logging
from typing import Any

from playwright.async_api import Page, Locator

from ...config import Config, get_config

logger = logging.getLogger(__name__)


class BasePage:
    """
    NotebookLM 頁面物件的基礎類別。

    提供通用的等待、選取和互動方法。
    """

    def __init__(self, page: Page, config: Config | None = None):
        self.page = page
        self.config = config or get_config()

    async def wait_for_load(self, timeout: int | None = None) -> None:
        """等待頁面載入完成。"""
        timeout = timeout or self.config.timeout_ms
        await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int | None = None,
        state: str = "visible",
    ) -> Locator:
        """等待元素出現並回傳。"""
        timeout = timeout or self.config.timeout_ms
        locator = self.page.locator(selector)
        await locator.wait_for(timeout=timeout, state=state)
        return locator

    async def wait_for_any_selector(
        self,
        selectors: list[str],
        timeout: int | None = None,
    ) -> Locator | None:
        """
        等待任一選擇器的元素出現。

        用於處理 UI 可能有不同版本的情況。
        """
        timeout = timeout or self.config.timeout_ms

        for selector in selectors:
            try:
                locator = self.page.locator(selector)
                await locator.wait_for(timeout=min(timeout // len(selectors), 5000), state="visible")
                return locator
            except Exception:
                continue

        return None

    async def safe_get_text(self, locator: Locator) -> str:
        """安全地取得元素文字，失敗時回傳空字串。"""
        try:
            return (await locator.text_content()) or ""
        except Exception:
            return ""

    async def safe_get_attribute(self, locator: Locator, attr: str) -> str | None:
        """安全地取得元素屬性。"""
        try:
            return await locator.get_attribute(attr)
        except Exception:
            return None

    async def click_and_wait(
        self,
        locator: Locator,
        wait_for: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """點擊元素並等待後續載入。"""
        timeout = timeout or self.config.timeout_ms
        await locator.click()

        if wait_for:
            await self.page.wait_for_selector(wait_for, timeout=timeout)
        else:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)

    async def get_current_url(self) -> str:
        """取得目前頁面 URL。"""
        return self.page.url

    async def navigate(self, url: str) -> None:
        """導航到指定 URL。"""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
