"""
錯誤處理模組。

提供標準化的錯誤碼、錯誤類別和錯誤處理工具。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """標準錯誤碼。"""

    # 認證相關
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"

    # 輸入驗證
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_URL = "INVALID_URL"
    CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
    QUESTION_TOO_LONG = "QUESTION_TOO_LONG"

    # 資源相關
    NOT_FOUND = "NOT_FOUND"
    NO_SOURCES = "NO_SOURCES"

    # 操作相關
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    OPERATION_FAILED = "OPERATION_FAILED"

    # 系統相關
    BROWSER_LAUNCH_FAILED = "BROWSER_LAUNCH_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"


# 可重試的錯誤碼
RETRYABLE_ERRORS = {
    ErrorCode.TIMEOUT,
    ErrorCode.RATE_LIMITED,
    ErrorCode.ELEMENT_NOT_FOUND,
    ErrorCode.NETWORK_ERROR,
}

# 需要重新認證的錯誤碼
AUTH_ERRORS = {
    ErrorCode.AUTH_REQUIRED,
    ErrorCode.SESSION_EXPIRED,
}


@dataclass
class McpError:
    """MCP 錯誤物件。"""

    code: ErrorCode | str
    message: str
    details: dict[str, Any] | None = None
    recoverable: bool | None = None

    def __post_init__(self):
        # 自動判斷是否可恢復
        if self.recoverable is None:
            if isinstance(self.code, ErrorCode):
                self.recoverable = self.code in RETRYABLE_ERRORS
            else:
                self.recoverable = False

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        result = {
            "code": self.code.value if isinstance(self.code, ErrorCode) else self.code,
            "message": self.message,
            "recoverable": self.recoverable,
        }
        if self.details:
            result["details"] = self.details
        return result

    def to_response(self) -> dict[str, Any]:
        """轉換為 MCP 回應格式。"""
        return {"error": self.to_dict()}


class NotebookLMError(Exception):
    """NotebookLM MCP 伺服器錯誤基礎類別。"""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool | None = None,
    ):
        self.error = McpError(code, message, details, recoverable)
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        return self.error.to_dict()

    def to_response(self) -> dict[str, Any]:
        """轉換為 MCP 回應格式。"""
        return self.error.to_response()


class AuthenticationError(NotebookLMError):
    """認證錯誤。"""

    def __init__(self, message: str = "需要重新認證，請執行 kof-notebooklm-init"):
        super().__init__(ErrorCode.AUTH_REQUIRED, message, recoverable=False)


class NotFoundError(NotebookLMError):
    """資源不存在錯誤。"""

    def __init__(self, resource_type: str, resource_id: str):
        message = f"找不到 {resource_type}: {resource_id}"
        super().__init__(
            ErrorCode.NOT_FOUND,
            message,
            details={"resource_type": resource_type, "resource_id": resource_id},
            recoverable=False,
        )


class ValidationError(NotebookLMError):
    """輸入驗證錯誤。"""

    def __init__(self, field: str, message: str):
        super().__init__(
            ErrorCode.INVALID_INPUT,
            message,
            details={"field": field},
            recoverable=False,
        )


class TimeoutError(NotebookLMError):
    """逾時錯誤。"""

    def __init__(self, operation: str, timeout_ms: int):
        message = f"操作 '{operation}' 逾時（{timeout_ms}ms）"
        super().__init__(
            ErrorCode.TIMEOUT,
            message,
            details={"operation": operation, "timeout_ms": timeout_ms},
            recoverable=True,
        )


class RateLimitError(NotebookLMError):
    """速率限制錯誤。"""

    def __init__(self, retry_after: float):
        message = f"速率限制超過，請在 {retry_after:.1f} 秒後重試"
        super().__init__(
            ErrorCode.RATE_LIMITED,
            message,
            details={"retry_after_seconds": round(retry_after, 1)},
            recoverable=True,
        )


def classify_error(exception: Exception) -> McpError:
    """
    將例外分類為標準 MCP 錯誤。

    Args:
        exception: 例外物件

    Returns:
        McpError 物件
    """
    # 如果已經是 NotebookLMError，直接使用
    if isinstance(exception, NotebookLMError):
        return exception.error

    exc_msg = str(exception).lower()
    exc_type = type(exception).__name__

    # 根據例外訊息分類
    if any(keyword in exc_msg for keyword in ["timeout", "timed out", "逾時"]):
        return McpError(ErrorCode.TIMEOUT, str(exception), recoverable=True)

    if any(keyword in exc_msg for keyword in ["auth", "login", "認證", "登入"]):
        return McpError(ErrorCode.AUTH_REQUIRED, str(exception), recoverable=False)

    if any(keyword in exc_msg for keyword in ["not found", "404", "找不到"]):
        return McpError(ErrorCode.NOT_FOUND, str(exception), recoverable=False)

    if any(keyword in exc_msg for keyword in ["rate", "limit", "too many", "速率"]):
        return McpError(ErrorCode.RATE_LIMITED, str(exception), recoverable=True)

    if any(keyword in exc_msg for keyword in ["connection", "network", "網路"]):
        return McpError(ErrorCode.NETWORK_ERROR, str(exception), recoverable=True)

    if any(keyword in exc_msg for keyword in ["browser", "playwright", "chromium"]):
        return McpError(ErrorCode.BROWSER_LAUNCH_FAILED, str(exception), recoverable=False)

    # 預設為內部錯誤
    return McpError(
        ErrorCode.INTERNAL_ERROR,
        str(exception),
        details={"exception_type": exc_type},
        recoverable=False,
    )


def error_response(
    code: ErrorCode | str,
    message: str,
    details: dict[str, Any] | None = None,
    recoverable: bool | None = None,
) -> dict[str, Any]:
    """
    建立錯誤回應的便捷函式。

    Args:
        code: 錯誤碼
        message: 錯誤訊息
        details: 額外詳細資訊
        recoverable: 是否可恢復

    Returns:
        錯誤回應字典
    """
    return McpError(code, message, details, recoverable).to_response()


def handle_exception(exception: Exception, operation: str = "unknown") -> dict[str, Any]:
    """
    處理例外並回傳標準錯誤回應。

    Args:
        exception: 例外物件
        operation: 操作名稱

    Returns:
        錯誤回應字典
    """
    logger.exception(f"操作 '{operation}' 發生錯誤")
    error = classify_error(exception)

    if error.details is None:
        error.details = {}
    error.details["operation"] = operation

    return error.to_response()
