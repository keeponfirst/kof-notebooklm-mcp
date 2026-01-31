"""
get_notebook 工具實作。

取得指定筆記本的詳細資訊。
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..client.browser import get_browser_manager
from ..client.pages.notebook_detail import NotebookDetailPage, NotebookDetail

logger = logging.getLogger(__name__)


@dataclass
class GetNotebookResult:
    """get_notebook 操作結果。"""

    notebook: NotebookDetail | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        if self.notebook:
            return self.notebook.to_dict()

        return {"error": {"code": "UNKNOWN", "message": "未知錯誤", "recoverable": False}}


async def get_notebook(notebook_id: str) -> GetNotebookResult:
    """
    取得筆記本詳細資訊。

    Args:
        notebook_id: 筆記本 ID

    Returns:
        GetNotebookResult 包含筆記本詳細資訊或錯誤訊息
    """
    logger.info(f"執行 get_notebook (notebook_id={notebook_id})")

    # 驗證輸入
    if not notebook_id or not notebook_id.strip():
        return GetNotebookResult(
            error={
                "code": "INVALID_INPUT",
                "message": "筆記本 ID 不能為空",
                "recoverable": False,
            }
        )

    notebook_id = notebook_id.strip()

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立頁面物件
        detail_page = NotebookDetailPage(page)

        # 取得筆記本詳細資訊
        notebook = await detail_page.get_notebook_detail(notebook_id)

        logger.info(f"成功取得筆記本: {notebook.name}")

        return GetNotebookResult(notebook=notebook)

    except Exception as e:
        logger.exception("get_notebook 執行失敗")

        error_msg = str(e).lower()
        error_code = "INTERNAL_ERROR"

        if "timeout" in error_msg:
            error_code = "TIMEOUT"
        elif "not found" in error_msg or "404" in error_msg:
            error_code = "NOT_FOUND"
        elif "auth" in error_msg or "login" in error_msg:
            error_code = "AUTH_REQUIRED"

        return GetNotebookResult(
            error={
                "code": error_code,
                "message": f"取得筆記本失敗: {str(e)}",
                "recoverable": error_code not in ["NOT_FOUND", "AUTH_REQUIRED"],
            }
        )
