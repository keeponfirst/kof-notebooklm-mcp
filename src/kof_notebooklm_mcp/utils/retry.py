"""
重試邏輯模組。

提供帶有指數退避的重試機制。
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class RetryConfig:
    """重試設定。"""

    max_retries: int = 3
    base_delay: float = 1.0  # 秒
    max_delay: float = 30.0  # 秒
    exponential_base: float = 2.0
    jitter: float = 0.1  # ±10% 隨機化

    # 可重試的錯誤類型
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            TimeoutError,
            ConnectionError,
            OSError,
        )
    )

    # 可重試的錯誤碼
    retryable_error_codes: set[str] = field(
        default_factory=lambda: {
            "TIMEOUT",
            "NETWORK_ERROR",
            "ELEMENT_NOT_FOUND",
            "RATE_LIMITED",
        }
    )


# 預設重試設定
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    計算重試延遲時間。

    Args:
        attempt: 目前重試次數（從 0 開始）
        config: 重試設定

    Returns:
        延遲秒數
    """
    # 指數退避
    delay = config.base_delay * (config.exponential_base ** attempt)

    # 套用上限
    delay = min(delay, config.max_delay)

    # 加入隨機抖動
    jitter_range = delay * config.jitter
    delay += random.uniform(-jitter_range, jitter_range)

    return max(0.1, delay)  # 至少 0.1 秒


def is_retryable_exception(exc: Exception, config: RetryConfig) -> bool:
    """
    判斷例外是否可重試。

    Args:
        exc: 例外物件
        config: 重試設定

    Returns:
        是否可重試
    """
    # 檢查例外類型
    if isinstance(exc, config.retryable_exceptions):
        return True

    # 檢查例外訊息中的關鍵字
    exc_msg = str(exc).lower()
    retryable_keywords = ["timeout", "connection", "network", "temporary", "retry"]

    for keyword in retryable_keywords:
        if keyword in exc_msg:
            return True

    return False


def is_retryable_error_code(error_code: str, config: RetryConfig) -> bool:
    """
    判斷錯誤碼是否可重試。

    Args:
        error_code: 錯誤碼
        config: 重試設定

    Returns:
        是否可重試
    """
    return error_code in config.retryable_error_codes


async def retry_async(
    func: Callable[P, T],
    *args: P.args,
    config: RetryConfig | None = None,
    **kwargs: P.kwargs,
) -> T:
    """
    執行異步函式並在失敗時重試。

    Args:
        func: 要執行的異步函式
        *args: 函式參數
        config: 重試設定
        **kwargs: 函式關鍵字參數

    Returns:
        函式回傳值

    Raises:
        最後一次嘗試的例外
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # 檢查是否可重試
            if not is_retryable_exception(e, config):
                logger.warning(f"不可重試的錯誤: {e}")
                raise

            # 檢查是否還有重試機會
            if attempt >= config.max_retries:
                logger.warning(f"已達最大重試次數 ({config.max_retries})，放棄重試")
                raise

            # 計算延遲
            delay = calculate_delay(attempt, config)
            logger.info(
                f"第 {attempt + 1} 次嘗試失敗: {e}。"
                f"將在 {delay:.2f} 秒後重試 (剩餘 {config.max_retries - attempt} 次)"
            )

            await asyncio.sleep(delay)

    # 不應該到達這裡，但為了型別安全
    if last_exception:
        raise last_exception
    raise RuntimeError("重試邏輯錯誤")


def with_retry(config: RetryConfig | None = None):
    """
    重試裝飾器。

    用法:
        @with_retry(RetryConfig(max_retries=5))
        async def my_function():
            ...

    Args:
        config: 重試設定

    Returns:
        裝飾器函式
    """
    config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_async(func, *args, config=config, **kwargs)

        return wrapper  # type: ignore

    return decorator


class RetryContext:
    """
    重試上下文管理器。

    用法:
        async with RetryContext(config) as ctx:
            while ctx.should_retry():
                try:
                    result = await some_operation()
                    break
                except Exception as e:
                    await ctx.handle_error(e)
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or DEFAULT_RETRY_CONFIG
        self.attempt = 0
        self.last_exception: Exception | None = None

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # 不吞掉例外

    def should_retry(self) -> bool:
        """檢查是否應該繼續重試。"""
        return self.attempt <= self.config.max_retries

    async def handle_error(self, error: Exception) -> None:
        """
        處理錯誤並等待重試。

        Args:
            error: 發生的錯誤

        Raises:
            如果不可重試或已達上限，重新拋出錯誤
        """
        self.last_exception = error
        self.attempt += 1

        if not is_retryable_exception(error, self.config):
            raise error

        if self.attempt > self.config.max_retries:
            raise error

        delay = calculate_delay(self.attempt - 1, self.config)
        logger.info(
            f"重試 {self.attempt}/{self.config.max_retries}: "
            f"等待 {delay:.2f} 秒後重試"
        )
        await asyncio.sleep(delay)
