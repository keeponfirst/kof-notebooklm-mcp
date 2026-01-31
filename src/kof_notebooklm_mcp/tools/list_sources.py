"""
list_sources 工具實作。

列出指定筆記本中的所有來源。
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..client.browser import get_browser_manager
from ..client.pages.notebook_detail import NotebookDetailPage, SourceInfo

logger = logging.getLogger(__name__)


@dataclass
class ListSourcesResult:
    """list_sources 操作結果。"""

    sources: list[SourceInfo]
    total: int
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        return {
            "sources": [src.to_dict() for src in self.sources],
            "total": self.total,
        }


async def list_sources(notebook_id: str) -> ListSourcesResult:
    """
    列出筆記本中的所有來源。

    Args:
        notebook_id: 筆記本 ID

    Returns:
        ListSourcesResult 包含來源列表或錯誤訊息
    """
    logger.info(f"執行 list_sources (notebook_id={notebook_id})")

    # 驗證輸入
    if not notebook_id or not notebook_id.strip():
        return ListSourcesResult(
            sources=[],
            total=0,
            error={
                "code": "INVALID_INPUT",
                "message": "筆記本 ID 不能為空",
                "recoverable": False,
            },
        )

    notebook_id = notebook_id.strip()

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立頁面物件
        detail_page = NotebookDetailPage(page)

        # 列出來源
        sources = await detail_page.list_sources(notebook_id)

        logger.info(f"成功列出 {len(sources)} 個來源")

        return ListSourcesResult(
            sources=sources,
            total=len(sources),
        )

    except Exception as e:
        logger.exception("list_sources 執行失敗")

        error_msg = str(e).lower()
        error_code = "INTERNAL_ERROR"

        if "timeout" in error_msg:
            error_code = "TIMEOUT"
        elif "not found" in error_msg or "404" in error_msg:
            error_code = "NOT_FOUND"
        elif "auth" in error_msg or "login" in error_msg:
            error_code = "AUTH_REQUIRED"

        return ListSourcesResult(
            sources=[],
            total=0,
            error={
                "code": error_code,
                "message": f"列出來源失敗: {str(e)}",
                "recoverable": error_code not in ["NOT_FOUND", "AUTH_REQUIRED"],
            },
        )
