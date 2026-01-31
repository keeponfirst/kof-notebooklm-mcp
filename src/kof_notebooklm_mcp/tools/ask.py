"""
ask 工具實作。

向筆記本提問並取得 AI 生成的回答與來源引用。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from ..client.browser import get_browser_manager
from ..client.pages.notebook_detail import NotebookDetailPage
from ..utils.validation import validate_notebook_id, validate_text_content, MAX_QUESTION_LENGTH

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """引用資訊。"""

    source_id: str
    source_title: str
    excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        return {
            "source_id": self.source_id,
            "source_title": self.source_title,
            "excerpt": self.excerpt,
        }


@dataclass
class AskResult:
    """ask 操作結果。"""

    answer: str | None = None
    citations: list[Citation] = field(default_factory=list)
    confidence: Literal["high", "medium", "low"] | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式。"""
        if self.error:
            return {"error": self.error}

        result: dict[str, Any] = {
            "answer": self.answer,
        }

        if self.citations:
            result["citations"] = [c.to_dict() for c in self.citations]

        if self.confidence:
            result["confidence"] = self.confidence

        if self.follow_up_questions:
            result["follow_up_questions"] = self.follow_up_questions

        return result


def _estimate_confidence(answer: str, citations: list[Citation]) -> Literal["high", "medium", "low"] | None:
    """
    根據回答內容和引用數量估計信心程度。

    Args:
        answer: AI 回答
        citations: 引用列表

    Returns:
        信心程度
    """
    if not answer:
        return None

    # 簡單的啟發式估計
    citation_count = len(citations)
    answer_length = len(answer)

    # 有多個引用且回答詳細 -> 高信心
    if citation_count >= 2 and answer_length > 200:
        return "high"

    # 有引用或回答較長 -> 中等信心
    if citation_count >= 1 or answer_length > 100:
        return "medium"

    # 其他情況 -> 低信心
    return "low"


async def ask(
    notebook_id: str,
    question: str,
    include_citations: bool = True,
) -> AskResult:
    """
    向筆記本提問並取得 AI 回答。

    Args:
        notebook_id: 筆記本 ID
        question: 要提問的問題
        include_citations: 是否提取來源引用（預設 True）

    Returns:
        AskResult 包含回答、引用和建議問題
    """
    logger.info(f"執行 ask (notebook_id={notebook_id}, question={question[:50]}...)")

    # 驗證筆記本 ID
    id_validation = validate_notebook_id(notebook_id)
    if not id_validation.valid:
        return AskResult(
            error={
                "code": "INVALID_INPUT",
                "message": id_validation.error,
                "recoverable": False,
            }
        )
    notebook_id = id_validation.sanitized_value  # type: ignore

    # 驗證問題
    if not question or not question.strip():
        return AskResult(
            error={
                "code": "INVALID_INPUT",
                "message": "問題不能為空",
                "recoverable": False,
            }
        )

    question = question.strip()

    # 檢查問題長度
    question_validation = validate_text_content(question, max_length=MAX_QUESTION_LENGTH)
    if not question_validation.valid:
        return AskResult(
            error={
                "code": "QUESTION_TOO_LONG",
                "message": question_validation.error,
                "recoverable": False,
            }
        )
    question = question_validation.sanitized_value  # type: ignore

    try:
        # 取得瀏覽器管理器
        browser = get_browser_manager()
        page = await browser.get_page()

        # 建立頁面物件
        detail_page = NotebookDetailPage(page)

        # 執行提問
        result = await detail_page.ask(
            notebook_id=notebook_id,
            question=question,
            include_citations=include_citations,
            timeout_ms=90000,  # 90 秒逾時
        )

        # 檢查結果
        if not result.get("success", False):
            error_msg = result.get("error", "提問失敗")

            # 判斷錯誤類型
            error_code = "ASK_FAILED"
            if "來源" in error_msg or "source" in error_msg.lower():
                error_code = "NO_SOURCES"
            elif "逾時" in error_msg or "timeout" in error_msg.lower():
                error_code = "TIMEOUT"
            elif "輸入框" in error_msg or "input" in error_msg.lower():
                error_code = "CHAT_UNAVAILABLE"

            return AskResult(
                error={
                    "code": error_code,
                    "message": error_msg,
                    "recoverable": error_code == "TIMEOUT",
                }
            )

        # 提取回答
        answer = result.get("answer", "")

        # 提取引用
        citations: list[Citation] = []
        if include_citations:
            raw_citations = result.get("citations", [])
            for c in raw_citations:
                if isinstance(c, dict):
                    citations.append(
                        Citation(
                            source_id=c.get("source_id", ""),
                            source_title=c.get("source_title", ""),
                            excerpt=c.get("excerpt"),
                        )
                    )

        # 提取建議問題
        follow_up_questions = result.get("follow_up_questions", [])

        # 估計信心程度
        confidence = _estimate_confidence(answer, citations)

        logger.info(
            f"成功取得回答: {len(answer)} 字元, {len(citations)} 個引用, "
            f"{len(follow_up_questions)} 個建議問題"
        )

        return AskResult(
            answer=answer,
            citations=citations,
            confidence=confidence,
            follow_up_questions=follow_up_questions,
        )

    except Exception as e:
        logger.exception("ask 執行失敗")

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

        return AskResult(
            error={
                "code": error_code,
                "message": f"提問失敗: {str(e)}",
                "recoverable": error_code not in ["NOT_FOUND", "AUTH_REQUIRED"],
            }
        )
