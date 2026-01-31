"""
list_notebooks 工具實作。

列出使用者 NotebookLM 帳號中的所有筆記本。
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..client.browser import get_browser_manager
from ..client.pages.notebooks import NotebooksPage, NotebookInfo

logger = logging.getLogger(__name__)


@dataclass
class ListNotebooksResult:
    """list_notebooks 操作結果。"""

    notebooks: list[NotebookInfo]
    total: int
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        return {
            "notebooks": [nb.to_dict() for nb in self.notebooks],
            "total": self.total,
        }


async def list_notebooks(limit: int = 50) -> ListNotebooksResult:
    """
    列出所有筆記本。

    Args:
        limit: 最大回傳數量（預設 50）

    Returns:
        ListNotebooksResult 包含筆記本列表或錯誤訊息
    """
    logger.info(f"執行 list_notebooks (limit={limit})")

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立頁面物件
        notebooks_page = NotebooksPage(page)

        # 導航到首頁並列出筆記本
        await notebooks_page.navigate_to_home()
        notebooks = await notebooks_page.list_notebooks(limit=limit)

        logger.info(f"成功列出 {len(notebooks)} 個筆記本")

        return ListNotebooksResult(
            notebooks=notebooks,
            total=len(notebooks),
        )

    except Exception as e:
        logger.exception("list_notebooks 執行失敗")

        error_code = "INTERNAL_ERROR"
        if "timeout" in str(e).lower():
            error_code = "TIMEOUT"
        elif "auth" in str(e).lower() or "login" in str(e).lower():
            error_code = "AUTH_REQUIRED"

        return ListNotebooksResult(
            notebooks=[],
            total=0,
            error={
                "code": error_code,
                "message": f"列出筆記本失敗: {str(e)}",
                "recoverable": error_code != "AUTH_REQUIRED",
            },
        )
