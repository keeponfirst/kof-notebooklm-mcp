"""速率限制的單元測試。"""

import asyncio
import pytest

from kof_notebooklm_mcp.utils.rate_limit import (
    RateLimitConfig,
    RateLimitExceeded,
    TokenBucket,
    RateLimiter,
)


class TestTokenBucket:
    """Token Bucket 測試。"""

    @pytest.mark.asyncio
    async def test_initial_tokens(self):
        """測試初始 token 數量。"""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket(config)
        assert bucket.available_tokens() == 10.0

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """測試成功取得 token。"""
        config = RateLimitConfig(requests_per_minute=60, burst_size=5)
        bucket = TokenBucket(config)

        # 應該可以連續取得 5 個 token
        for _ in range(5):
            result = await bucket.acquire(blocking=False)
            assert result is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self):
        """測試超過限制時拋出例外。"""
        config = RateLimitConfig(requests_per_minute=60, burst_size=2)
        bucket = TokenBucket(config)

        # 消耗所有 token
        await bucket.acquire(blocking=False)
        await bucket.acquire(blocking=False)

        # 第三次應該失敗
        with pytest.raises(RateLimitExceeded) as exc_info:
            await bucket.acquire(blocking=False)

        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_token_refill(self):
        """測試 token 補充。"""
        # 每秒補充 10 個 token
        config = RateLimitConfig(requests_per_minute=600, burst_size=1)
        bucket = TokenBucket(config)

        # 消耗 token
        await bucket.acquire(blocking=False)

        # 等待補充
        await asyncio.sleep(0.15)  # 應該補充約 1.5 個 token

        # 應該可以再次取得
        result = await bucket.acquire(blocking=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocking_acquire(self):
        """測試阻塞等待模式。"""
        config = RateLimitConfig(requests_per_minute=600, burst_size=1)
        bucket = TokenBucket(config)

        # 消耗 token
        await bucket.acquire(blocking=False)

        # 阻塞等待應該成功
        start_time = asyncio.get_event_loop().time()
        result = await bucket.acquire(blocking=True, timeout=1.0)
        elapsed = asyncio.get_event_loop().time() - start_time

        assert result is True
        assert elapsed < 0.5  # 應該在 0.1 秒左右完成


class TestRateLimiter:
    """RateLimiter 測試。"""

    @pytest.mark.asyncio
    async def test_default_operation(self):
        """測試預設操作。"""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=60, burst_size=5))

        # 應該可以取得
        result = await limiter.acquire("default", blocking=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_configure_operation(self):
        """測試為特定操作設定限制。"""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=60, burst_size=10))

        # 為 add_source 設定更嚴格的限制
        limiter.configure("add_source", RateLimitConfig(requests_per_minute=30, burst_size=2))

        # add_source 應該只能連續執行 2 次
        await limiter.acquire("add_source", blocking=False)
        await limiter.acquire("add_source", blocking=False)

        with pytest.raises(RateLimitExceeded):
            await limiter.acquire("add_source", blocking=False)

    @pytest.mark.asyncio
    async def test_status(self):
        """測試狀態查詢。"""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=60, burst_size=5))
        await limiter.acquire("test_op", blocking=False)

        status = limiter.status("test_op")
        assert status["operation"] == "test_op"
        assert "available_tokens" in status
        assert "max_tokens" in status


class TestRateLimitExceeded:
    """RateLimitExceeded 例外測試。"""

    def test_error_dict(self):
        """測試轉換為錯誤字典。"""
        exc = RateLimitExceeded(retry_after=30.5)
        error_dict = exc.to_error_dict()

        assert error_dict["code"] == "RATE_LIMITED"
        assert error_dict["recoverable"] is True
        assert error_dict["details"]["retry_after_seconds"] == 30.5
