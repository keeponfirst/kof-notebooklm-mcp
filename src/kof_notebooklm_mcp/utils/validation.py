"""
輸入驗證工具模組。

提供 URL、文字內容等輸入的驗證和清理功能。
"""

import re
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Literal


# 驗證限制
MAX_QUESTION_LENGTH = 10000  # 問題最大長度
MAX_TEXT_SOURCE_LENGTH = 500000  # 文字來源最大長度（約 500KB）
MAX_NOTEBOOK_NAME_LENGTH = 200  # 筆記本名稱最大長度
MAX_TITLE_LENGTH = 200  # 標題最大長度
ALLOWED_URL_SCHEMES = ["https", "http"]  # 允許的 URL 協議


@dataclass
class ValidationResult:
    """驗證結果。"""

    valid: bool
    error: str | None = None
    sanitized_value: str | None = None


def validate_url(url: str) -> ValidationResult:
    """
    驗證 URL 格式和安全性。

    Args:
        url: 要驗證的 URL

    Returns:
        ValidationResult 包含驗證結果
    """
    if not url or not url.strip():
        return ValidationResult(valid=False, error="URL 不能為空")

    url = url.strip()

    # 解析 URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return ValidationResult(valid=False, error=f"URL 格式無效: {e}")

    # 檢查協議
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return ValidationResult(
            valid=False,
            error=f"不支援的 URL 協議: {parsed.scheme}。只允許 {', '.join(ALLOWED_URL_SCHEMES)}",
        )

    # 檢查主機名稱
    if not parsed.netloc:
        return ValidationResult(valid=False, error="URL 缺少主機名稱")

    # 檢查危險模式
    dangerous_patterns = [
        r"javascript:",
        r"data:",
        r"vbscript:",
        r"file:",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return ValidationResult(valid=False, error="URL 包含不安全的內容")

    return ValidationResult(valid=True, sanitized_value=url)


def validate_text_content(text: str, max_length: int = MAX_TEXT_SOURCE_LENGTH) -> ValidationResult:
    """
    驗證文字內容。

    Args:
        text: 要驗證的文字
        max_length: 最大允許長度

    Returns:
        ValidationResult 包含驗證結果
    """
    if not text:
        return ValidationResult(valid=False, error="文字內容不能為空")

    if len(text) > max_length:
        return ValidationResult(
            valid=False,
            error=f"文字內容超過最大長度限制（{max_length:,} 字元）。目前長度: {len(text):,}",
        )

    # 移除可能有問題的控制字元（保留換行和 tab）
    sanitized = "".join(
        char for char in text if char.isprintable() or char in "\n\r\t"
    )

    return ValidationResult(valid=True, sanitized_value=sanitized)


def validate_title(title: str | None) -> ValidationResult:
    """
    驗證標題。

    Args:
        title: 要驗證的標題（可為空）

    Returns:
        ValidationResult 包含驗證結果
    """
    if not title:
        return ValidationResult(valid=True, sanitized_value=None)

    title = title.strip()

    if len(title) > MAX_TITLE_LENGTH:
        return ValidationResult(
            valid=False,
            error=f"標題超過最大長度限制（{MAX_TITLE_LENGTH} 字元）",
        )

    # 移除換行符號
    sanitized = title.replace("\n", " ").replace("\r", " ")

    return ValidationResult(valid=True, sanitized_value=sanitized)


def validate_notebook_id(notebook_id: str) -> ValidationResult:
    """
    驗證筆記本 ID。

    Args:
        notebook_id: 要驗證的筆記本 ID

    Returns:
        ValidationResult 包含驗證結果
    """
    if not notebook_id or not notebook_id.strip():
        return ValidationResult(valid=False, error="筆記本 ID 不能為空")

    notebook_id = notebook_id.strip()

    # NotebookLM ID 通常是英數字和連字號的組合
    if not re.match(r"^[a-zA-Z0-9_-]+$", notebook_id):
        return ValidationResult(
            valid=False,
            error="筆記本 ID 格式無效。只允許英數字、底線和連字號",
        )

    return ValidationResult(valid=True, sanitized_value=notebook_id)


def validate_source_type(source_type: str) -> ValidationResult:
    """
    驗證來源類型。

    Args:
        source_type: 來源類型

    Returns:
        ValidationResult 包含驗證結果
    """
    valid_types = ["url", "text"]

    if not source_type:
        return ValidationResult(valid=False, error="來源類型不能為空")

    source_type = source_type.lower().strip()

    if source_type not in valid_types:
        return ValidationResult(
            valid=False,
            error=f"無效的來源類型: {source_type}。只允許 {', '.join(valid_types)}",
        )

    return ValidationResult(valid=True, sanitized_value=source_type)
