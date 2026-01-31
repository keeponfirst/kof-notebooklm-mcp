"""
速率限制模組。

使用 Token Bucket 演算法實現速率限制。
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制設定。"""

    requests_per_minute: int = 10  # 每分鐘請求數
    burst_size: int | None = None  # 突發容量（預設等於每分鐘請求數）

    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = self.requests_per_minute


class RateLimitExceeded(Exception):
    """速率限制超過時拋出的例外。"""

    def __init__(self, retry_after: float, message: str | None = None):
        self.retry_after = retry_after
        self.message = message or f"速率限制超過，請在 {retry_after:.1f} 秒後重試"
        super().__init__(self.message)

    def to_error_dict(self) -> dict[str, Any]:
        """轉換為錯誤字典格式。"""
        return {
            "code": "RATE_LIMITED",
            "message": self.message,
            "details": {
                "retry_after_seconds": round(self.retry_after, 1),
            },
            "recoverable": True,
        }


class TokenBucket:
    """
    Token Bucket 速率限制器。

    每個請求消耗一個 token，token 以固定速率補充。
    當沒有可用 token 時，請求會被阻塞或拒絕。
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = float(config.burst_size or config.requests_per_minute)
        self.max_tokens = float(config.burst_size or config.requests_per_minute)
        self.refill_rate = config.requests_per_minute / 60.0  # tokens per second
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """補充 tokens。"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """
        嘗試取得一個 token。

        Args:
            blocking: 是否阻塞等待
            timeout: 最大等待時間（秒）

        Returns:
            是否成功取得 token

        Raises:
            RateLimitExceeded: 如果 blocking=False 且沒有可用 token
        """
        start_time = time.monotonic()

        async with self._lock:
            while True:
                self._refill()

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

                if not blocking:
                    # 計算需要等待的時間
                    wait_time = (1 - self.tokens) / self.refill_rate
                    raise RateLimitExceeded(wait_time)

                # 檢查逾時
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= timeout:
                        wait_time = (1 - self.tokens) / self.refill_rate
                        raise RateLimitExceeded(wait_time)

                # 等待足夠的時間以補充一個 token
                wait_time = (1 - self.tokens) / self.refill_rate
                if timeout is not None:
                    remaining = timeout - (time.monotonic() - start_time)
                    wait_time = min(wait_time, remaining)

                await asyncio.sleep(min(wait_time, 1.0))  # 最多等待 1 秒後再檢查

    async def wait(self) -> None:
        """等待直到有可用 token。"""
        await self.acquire(blocking=True)

    def available_tokens(self) -> float:
        """取得目前可用的 token 數量。"""
        self._refill()
        return self.tokens

    def time_until_available(self) -> float:
        """取得直到有可用 token 的時間（秒）。"""
        self._refill()
        if self.tokens >= 1:
            return 0.0
        return (1 - self.tokens) / self.refill_rate


class RateLimiter:
    """
    多層級速率限制器。

    支援不同操作類型的獨立限制。
    """

    def __init__(self, default_config: RateLimitConfig | None = None):
        self.default_config = default_config or RateLimitConfig()
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _get_bucket(self, operation: str) -> TokenBucket:
        """取得或建立指定操作的 bucket。"""
        if operation not in self._buckets:
            self._buckets[operation] = TokenBucket(self.default_config)
        return self._buckets[operation]

    def configure(self, operation: str, config: RateLimitConfig) -> None:
        """
        為特定操作設定速率限制。

        Args:
            operation: 操作名稱
            config: 速率限制設定
        """
        self._buckets[operation] = TokenBucket(config)

    async def acquire(
        self,
        operation: str = "default",
        blocking: bool = True,
        timeout: float | None = None,
    ) -> bool:
        """
        取得執行操作的許可。

        Args:
            operation: 操作名稱
            blocking: 是否阻塞等待
            timeout: 最大等待時間

        Returns:
            是否成功取得許可
        """
        async with self._lock:
            bucket = self._get_bucket(operation)

        return await bucket.acquire(blocking=blocking, timeout=timeout)

    async def wait(self, operation: str = "default") -> None:
        """等待直到可以執行操作。"""
        await self.acquire(operation, blocking=True)

    def status(self, operation: str = "default") -> dict[str, Any]:
        """
        取得速率限制狀態。

        Args:
            operation: 操作名稱

        Returns:
            狀態字典
        """
        bucket = self._get_bucket(operation)
        return {
            "operation": operation,
            "available_tokens": round(bucket.available_tokens(), 2),
            "max_tokens": bucket.max_tokens,
            "refill_rate_per_second": round(bucket.refill_rate, 3),
            "time_until_available": round(bucket.time_until_available(), 2),
        }


# 全域速率限制器實例
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """取得全域速率限制器實例。"""
    global _rate_limiter
    if _rate_limiter is None:
        from ..config import get_config

        config = get_config()
        default_config = RateLimitConfig(
            requests_per_minute=config.rate_limit_per_minute,
        )
        _rate_limiter = RateLimiter(default_config)

        # 為寫入操作設定更嚴格的限制
        write_config = RateLimitConfig(
            requests_per_minute=max(5, config.rate_limit_per_minute // 2),
        )
        _rate_limiter.configure("add_source", write_config)
        _rate_limiter.configure("ask", write_config)

    return _rate_limiter


async def rate_limit(operation: str = "default") -> None:
    """
    便捷函式：等待速率限制。

    Args:
        operation: 操作名稱
    """
    limiter = get_rate_limiter()
    await limiter.wait(operation)
