"""輸入驗證工具的單元測試。"""

import pytest

from kof_notebooklm_mcp.utils.validation import (
    validate_url,
    validate_text_content,
    validate_title,
    validate_notebook_id,
    validate_source_type,
    MAX_TEXT_SOURCE_LENGTH,
    MAX_TITLE_LENGTH,
)


class TestValidateUrl:
    """URL 驗證測試。"""

    def test_valid_https_url(self):
        """測試有效的 HTTPS URL。"""
        result = validate_url("https://example.com/page")
        assert result.valid is True
        assert result.sanitized_value == "https://example.com/page"

    def test_valid_http_url(self):
        """測試有效的 HTTP URL。"""
        result = validate_url("http://example.com")
        assert result.valid is True

    def test_empty_url(self):
        """測試空 URL。"""
        result = validate_url("")
        assert result.valid is False
        assert "不能為空" in result.error

    def test_whitespace_only_url(self):
        """測試只有空白的 URL。"""
        result = validate_url("   ")
        assert result.valid is False

    def test_invalid_scheme(self):
        """測試不允許的協議。"""
        result = validate_url("ftp://example.com")
        assert result.valid is False
        assert "不支援的 URL 協議" in result.error

    def test_javascript_url(self):
        """測試危險的 javascript URL。"""
        result = validate_url("javascript:alert(1)")
        assert result.valid is False
        assert "不安全" in result.error

    def test_data_url(self):
        """測試 data URL。"""
        result = validate_url("data:text/html,<script>")
        assert result.valid is False

    def test_missing_host(self):
        """測試缺少主機的 URL。"""
        result = validate_url("https://")
        assert result.valid is False
        assert "主機名稱" in result.error

    def test_url_with_whitespace(self):
        """測試帶空白的 URL 會被修剪。"""
        result = validate_url("  https://example.com  ")
        assert result.valid is True
        assert result.sanitized_value == "https://example.com"


class TestValidateTextContent:
    """文字內容驗證測試。"""

    def test_valid_text(self):
        """測試有效的文字。"""
        result = validate_text_content("這是一段測試文字")
        assert result.valid is True
        assert result.sanitized_value == "這是一段測試文字"

    def test_empty_text(self):
        """測試空文字。"""
        result = validate_text_content("")
        assert result.valid is False
        assert "不能為空" in result.error

    def test_text_with_newlines(self):
        """測試包含換行的文字。"""
        result = validate_text_content("第一行\n第二行\r\n第三行")
        assert result.valid is True
        assert "\n" in result.sanitized_value

    def test_text_exceeds_max_length(self):
        """測試超過最大長度的文字。"""
        long_text = "a" * (MAX_TEXT_SOURCE_LENGTH + 1)
        result = validate_text_content(long_text)
        assert result.valid is False
        assert "超過最大長度" in result.error

    def test_custom_max_length(self):
        """測試自訂最大長度。"""
        result = validate_text_content("12345", max_length=3)
        assert result.valid is False


class TestValidateTitle:
    """標題驗證測試。"""

    def test_valid_title(self):
        """測試有效的標題。"""
        result = validate_title("我的筆記")
        assert result.valid is True
        assert result.sanitized_value == "我的筆記"

    def test_none_title(self):
        """測試 None 標題（允許）。"""
        result = validate_title(None)
        assert result.valid is True
        assert result.sanitized_value is None

    def test_empty_title(self):
        """測試空標題（允許）。"""
        result = validate_title("")
        assert result.valid is True

    def test_title_with_newlines(self):
        """測試包含換行的標題會被清理。"""
        result = validate_title("第一行\n第二行")
        assert result.valid is True
        assert "\n" not in result.sanitized_value
        assert result.sanitized_value == "第一行 第二行"

    def test_title_exceeds_max_length(self):
        """測試超過最大長度的標題。"""
        long_title = "a" * (MAX_TITLE_LENGTH + 1)
        result = validate_title(long_title)
        assert result.valid is False
        assert "超過最大長度" in result.error


class TestValidateNotebookId:
    """筆記本 ID 驗證測試。"""

    def test_valid_id(self):
        """測試有效的 ID。"""
        result = validate_notebook_id("abc123")
        assert result.valid is True
        assert result.sanitized_value == "abc123"

    def test_valid_id_with_dash(self):
        """測試帶連字號的 ID。"""
        result = validate_notebook_id("abc-123-xyz")
        assert result.valid is True

    def test_valid_id_with_underscore(self):
        """測試帶底線的 ID。"""
        result = validate_notebook_id("abc_123_xyz")
        assert result.valid is True

    def test_empty_id(self):
        """測試空 ID。"""
        result = validate_notebook_id("")
        assert result.valid is False
        assert "不能為空" in result.error

    def test_id_with_special_chars(self):
        """測試包含特殊字元的 ID。"""
        result = validate_notebook_id("abc@123")
        assert result.valid is False
        assert "格式無效" in result.error

    def test_id_with_spaces(self):
        """測試包含空格的 ID。"""
        result = validate_notebook_id("abc 123")
        assert result.valid is False


class TestValidateSourceType:
    """來源類型驗證測試。"""

    def test_url_type(self):
        """測試 URL 類型。"""
        result = validate_source_type("url")
        assert result.valid is True
        assert result.sanitized_value == "url"

    def test_text_type(self):
        """測試 text 類型。"""
        result = validate_source_type("text")
        assert result.valid is True
        assert result.sanitized_value == "text"

    def test_uppercase_type(self):
        """測試大寫類型會被轉換。"""
        result = validate_source_type("URL")
        assert result.valid is True
        assert result.sanitized_value == "url"

    def test_invalid_type(self):
        """測試無效的類型。"""
        result = validate_source_type("pdf")
        assert result.valid is False
        assert "無效的來源類型" in result.error

    def test_empty_type(self):
        """測試空類型。"""
        result = validate_source_type("")
        assert result.valid is False
