"""
add_source 工具實作。

新增 URL 或文字來源到筆記本。
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from ..client.browser import get_browser_manager
from ..client.pages.notebook_detail import NotebookDetailPage
from ..utils.validation import (
    validate_notebook_id,
    validate_source_type,
    validate_url,
    validate_text_content,
    validate_title,
)

logger = logging.getLogger(__name__)


@dataclass
class AddSourceResult:
    """add_source 操作結果。"""

    success: bool
    source_id: str | None = None
    title: str | None = None
    processing_status: Literal["complete", "processing", "failed"] | None = None
    message: str | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        return {
            "success": self.success,
            "source_id": self.source_id,
            "title": self.title,
            "processing_status": self.processing_status,
            "message": self.message,
        }


async def add_source(
    notebook_id: str,
    source_type: str,
    url: str | None = None,
    text: str | None = None,
    title: str | None = None,
) -> AddSourceResult:
    """
    新增來源到筆記本。

    Args:
        notebook_id: 筆記本 ID
        source_type: 來源類型 ("url" 或 "text")
        url: URL（當 source_type 為 "url" 時必填）
        text: 文字內容（當 source_type 為 "text" 時必填）
        title: 標題（僅用於文字來源，可選）

    Returns:
        AddSourceResult 包含操作結果或錯誤訊息
    """
    logger.info(f"執行 add_source (notebook_id={notebook_id}, type={source_type})")

    # 驗證筆記本 ID
    id_validation = validate_notebook_id(notebook_id)
    if not id_validation.valid:
        return AddSourceResult(
            success=False,
            error={
                "code": "INVALID_INPUT",
                "message": id_validation.error,
                "recoverable": False,
            },
        )
    notebook_id = id_validation.sanitized_value  # type: ignore

    # 驗證來源類型
    type_validation = validate_source_type(source_type)
    if not type_validation.valid:
        return AddSourceResult(
            success=False,
            error={
                "code": "INVALID_INPUT",
                "message": type_validation.error,
                "recoverable": False,
            },
        )
    source_type = type_validation.sanitized_value  # type: ignore

    # 根據來源類型驗證對應的輸入
    if source_type == "url":
        if not url:
            return AddSourceResult(
                success=False,
                error={
                    "code": "INVALID_INPUT",
                    "message": "來源類型為 'url' 時，必須提供 url 參數",
                    "recoverable": False,
                },
            )

        url_validation = validate_url(url)
        if not url_validation.valid:
            return AddSourceResult(
                success=False,
                error={
                    "code": "INVALID_URL",
                    "message": url_validation.error,
                    "recoverable": False,
                },
            )
        url = url_validation.sanitized_value

    elif source_type == "text":
        if not text:
            return AddSourceResult(
                success=False,
                error={
                    "code": "INVALID_INPUT",
                    "message": "來源類型為 'text' 時，必須提供 text 參數",
                    "recoverable": False,
                },
            )

        text_validation = validate_text_content(text)
        if not text_validation.valid:
            return AddSourceResult(
                success=False,
                error={
                    "code": "CONTENT_TOO_LARGE",
                    "message": text_validation.error,
                    "recoverable": False,
                },
            )
        text = text_validation.sanitized_value

        # 驗證標題（如果提供）
        if title:
            title_validation = validate_title(title)
            if not title_validation.valid:
                return AddSourceResult(
                    success=False,
                    error={
                        "code": "INVALID_INPUT",
                        "message": title_validation.error,
                        "recoverable": False,
                    },
                )
            title = title_validation.sanitized_value

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立頁面物件
        detail_page = NotebookDetailPage(page)

        # 根據來源類型執行新增
        if source_type == "url":
            result = await detail_page.add_url_source(notebook_id, url)  # type: ignore
        else:
            result = await detail_page.add_text_source(notebook_id, text, title)  # type: ignore

        # 檢查結果
        if not result.get("success", False):
            error_msg = result.get("error", "新增來源失敗")
            return AddSourceResult(
                success=False,
                error={
                    "code": "ADD_SOURCE_FAILED",
                    "message": error_msg,
                    "recoverable": True,
                },
            )

        logger.info(f"成功新增來源: {result.get('title', '未知')}")

        return AddSourceResult(
            success=True,
            source_id=result.get("source_id"),
            title=result.get("title"),
            processing_status=result.get("processing_status", "complete"),
            message=result.get("message"),
        )

    except Exception as e:
        logger.exception("add_source 執行失敗")

        error_msg = str(e).lower()
        error_code = "INTERNAL_ERROR"

        if "timeout" in error_msg:
            error_code = "TIMEOUT"
        elif "not found" in error_msg or "404" in error_msg:
            error_code = "NOT_FOUND"
        elif "auth" in error_msg or "login" in error_msg:
            error_code = "AUTH_REQUIRED"
        elif "rate" in error_msg or "limit" in error_msg:
            error_code = "RATE_LIMITED"

        return AddSourceResult(
            success=False,
            error={
                "code": error_code,
                "message": f"新增來源失敗: {str(e)}",
                "recoverable": error_code not in ["NOT_FOUND", "AUTH_REQUIRED"],
            },
        )
