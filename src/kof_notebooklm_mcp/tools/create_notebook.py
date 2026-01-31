"""
create_notebook 工具實作。

建立新的筆記本。
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..client.browser import get_browser_manager
from ..client.pages.notebooks import NotebooksPage
from ..client.pages.notebook_detail import NotebookDetailPage

logger = logging.getLogger(__name__)


@dataclass
class CreateNotebookResult:
    """create_notebook 操作結果。"""

    notebook_id: str | None = None
    title: str | None = None
    url: str | None = None
    renamed: bool = False
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        return {
            "notebook_id": self.notebook_id,
            "title": self.title,
            "url": self.url,
            "renamed": self.renamed,
        }


async def create_notebook(title: str | None = None) -> CreateNotebookResult:
    """
    建立新的筆記本。

    Args:
        title: 筆記本標題（選填，預設為系統預設名稱）

    Returns:
        CreateNotebookResult 包含新筆記本資訊
    """
    logger.info(f"執行 create_notebook (title={title})")

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立列表頁面物件
        notebooks_page = NotebooksPage(page)

        # 執行建立
        notebook_id = await notebooks_page.create_notebook()

        if not notebook_id:
            return CreateNotebookResult(
                error={
                    "code": "CREATE_FAILED",
                    "message": "無法建立筆記本",
                    "recoverable": True,
                }
            )

        notebook_url = await notebooks_page.get_notebook_url(notebook_id)
        current_title = "Untitled notebook" # 預設名稱
        renamed = False

        # 如果有指定標題，嘗試重新命名
        if title and title.strip():
            detail_page = NotebookDetailPage(page)
            # 確保已經在詳細頁面（create_notebook 應該已經導航過去了）
            # 執行重新命名
            if await detail_page.rename_notebook(title):
                current_title = title
                renamed = True
            else:
                logger.warning("筆記本建立成功但重新命名失敗")

        return CreateNotebookResult(
            notebook_id=notebook_id,
            title=current_title,
            url=notebook_url,
            renamed=renamed,
        )

    except Exception as e:
        logger.exception("create_notebook 執行失敗")
        return CreateNotebookResult(
            error={
                "code": "INTERNAL_ERROR",
                "message": f"建立筆記本失敗: {str(e)}",
                "recoverable": False,
            }
        )
