"""錯誤處理的單元測試。"""

import pytest

from kof_notebooklm_mcp.utils.errors import (
    ErrorCode,
    McpError,
    NotebookLMError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    TimeoutError as McpTimeoutError,
    RateLimitError,
    RETRYABLE_ERRORS,
    classify_error,
    error_response,
    handle_exception,
)


class TestErrorCode:
    """ErrorCode 測試。"""

    def test_retryable_errors(self):
        """測試可重試錯誤集合。"""
        assert ErrorCode.TIMEOUT in RETRYABLE_ERRORS
        assert ErrorCode.RATE_LIMITED in RETRYABLE_ERRORS
        assert ErrorCode.NETWORK_ERROR in RETRYABLE_ERRORS
        assert ErrorCode.AUTH_REQUIRED not in RETRYABLE_ERRORS
        assert ErrorCode.INVALID_INPUT not in RETRYABLE_ERRORS


class TestMcpError:
    """McpError 測試。"""

    def test_to_dict(self):
        """測試轉換為字典。"""
        error = McpError(
            code=ErrorCode.TIMEOUT,
            message="操作逾時",
            details={"timeout_ms": 30000},
        )
        d = error.to_dict()

        assert d["code"] == "TIMEOUT"
        assert d["message"] == "操作逾時"
        assert d["recoverable"] is True
        assert d["details"]["timeout_ms"] == 30000

    def test_auto_recoverable_true(self):
        """測試自動判斷可恢復（是）。"""
        error = McpError(ErrorCode.TIMEOUT, "逾時")
        assert error.recoverable is True

    def test_auto_recoverable_false(self):
        """測試自動判斷可恢復（否）。"""
        error = McpError(ErrorCode.AUTH_REQUIRED, "需要認證")
        assert error.recoverable is False

    def test_explicit_recoverable(self):
        """測試明確指定可恢復性。"""
        error = McpError(ErrorCode.AUTH_REQUIRED, "需要認證", recoverable=True)
        assert error.recoverable is True

    def test_to_response(self):
        """測試轉換為回應格式。"""
        error = McpError(ErrorCode.NOT_FOUND, "找不到資源")
        response = error.to_response()

        assert "error" in response
        assert response["error"]["code"] == "NOT_FOUND"


class TestNotebookLMError:
    """NotebookLMError 測試。"""

    def test_authentication_error(self):
        """測試認證錯誤。"""
        error = AuthenticationError()
        assert error.error.code == ErrorCode.AUTH_REQUIRED
        assert error.error.recoverable is False

    def test_not_found_error(self):
        """測試找不到錯誤。"""
        error = NotFoundError("notebook", "abc123")
        d = error.to_dict()

        assert d["code"] == "NOT_FOUND"
        assert "abc123" in d["message"]
        assert d["details"]["resource_type"] == "notebook"

    def test_validation_error(self):
        """測試驗證錯誤。"""
        error = ValidationError("url", "URL 格式無效")
        d = error.to_dict()

        assert d["code"] == "INVALID_INPUT"
        assert d["details"]["field"] == "url"

    def test_timeout_error(self):
        """測試逾時錯誤。"""
        error = McpTimeoutError("ask", 90000)
        d = error.to_dict()

        assert d["code"] == "TIMEOUT"
        assert d["recoverable"] is True
        assert d["details"]["timeout_ms"] == 90000

    def test_rate_limit_error(self):
        """測試速率限制錯誤。"""
        error = RateLimitError(30.5)
        d = error.to_dict()

        assert d["code"] == "RATE_LIMITED"
        assert d["recoverable"] is True
        assert d["details"]["retry_after_seconds"] == 30.5


class TestClassifyError:
    """classify_error 測試。"""

    def test_timeout_exception(self):
        """測試分類 timeout 例外。"""
        exc = Exception("Connection timed out")
        error = classify_error(exc)
        assert error.code == ErrorCode.TIMEOUT

    def test_auth_exception(self):
        """測試分類認證例外。"""
        exc = Exception("Authentication required")
        error = classify_error(exc)
        assert error.code == ErrorCode.AUTH_REQUIRED

    def test_not_found_exception(self):
        """測試分類找不到例外。"""
        exc = Exception("Resource not found (404)")
        error = classify_error(exc)
        assert error.code == ErrorCode.NOT_FOUND

    def test_rate_limit_exception(self):
        """測試分類速率限制例外。"""
        exc = Exception("Rate limit exceeded")
        error = classify_error(exc)
        assert error.code == ErrorCode.RATE_LIMITED

    def test_network_exception(self):
        """測試分類網路例外。"""
        exc = Exception("Connection refused")
        error = classify_error(exc)
        assert error.code == ErrorCode.NETWORK_ERROR

    def test_browser_exception(self):
        """測試分類瀏覽器例外。"""
        exc = Exception("Playwright browser failed to launch")
        error = classify_error(exc)
        assert error.code == ErrorCode.BROWSER_LAUNCH_FAILED

    def test_unknown_exception(self):
        """測試分類未知例外。"""
        exc = Exception("Some random error")
        error = classify_error(exc)
        assert error.code == ErrorCode.INTERNAL_ERROR

    def test_notebook_lm_error_passthrough(self):
        """測試 NotebookLMError 直接傳遞。"""
        original = AuthenticationError()
        error = classify_error(original)
        assert error.code == ErrorCode.AUTH_REQUIRED


class TestErrorResponse:
    """error_response 測試。"""

    def test_basic_response(self):
        """測試基本回應。"""
        response = error_response(ErrorCode.TIMEOUT, "操作逾時")
        assert "error" in response
        assert response["error"]["code"] == "TIMEOUT"

    def test_response_with_details(self):
        """測試帶詳細資訊的回應。"""
        response = error_response(
            ErrorCode.RATE_LIMITED,
            "速率限制",
            details={"retry_after": 30},
        )
        assert response["error"]["details"]["retry_after"] == 30


class TestHandleException:
    """handle_exception 測試。"""

    def test_handle_exception(self):
        """測試處理例外。"""
        exc = Exception("Test error")
        response = handle_exception(exc, "test_operation")

        assert "error" in response
        assert response["error"]["details"]["operation"] == "test_operation"
