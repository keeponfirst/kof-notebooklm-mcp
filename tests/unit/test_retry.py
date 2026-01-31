"""重試邏輯的單元測試。"""

import asyncio
import pytest

from kof_notebooklm_mcp.utils.retry import (
    RetryConfig,
    RetryContext,
    calculate_delay,
    is_retryable_exception,
    retry_async,
)


class TestCalculateDelay:
    """延遲計算測試。"""

    def test_first_attempt(self):
        """測試第一次嘗試的延遲。"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        delay = calculate_delay(0, config)
        assert delay == 1.0

    def test_exponential_backoff(self):
        """測試指數退避。"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0

    def test_max_delay(self):
        """測試最大延遲上限。"""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=0.0)
        delay = calculate_delay(10, config)  # 2^10 = 1024，超過上限
        assert delay == 5.0

    def test_jitter(self):
        """測試隨機抖動。"""
        config = RetryConfig(base_delay=10.0, jitter=0.1)  # ±10%
        delays = [calculate_delay(0, config) for _ in range(100)]
        # 延遲應該在 9.0 到 11.0 之間
        assert all(9.0 <= d <= 11.0 for d in delays)
        # 不應該全部相同
        assert len(set(delays)) > 1


class TestIsRetryableException:
    """可重試例外判斷測試。"""

    def test_timeout_exception(self):
        """測試 TimeoutError。"""
        config = RetryConfig()
        assert is_retryable_exception(TimeoutError("連線逾時"), config) is True

    def test_connection_exception(self):
        """測試 ConnectionError。"""
        config = RetryConfig()
        assert is_retryable_exception(ConnectionError("連線失敗"), config) is True

    def test_value_exception_not_retryable(self):
        """測試 ValueError（不可重試）。"""
        config = RetryConfig()
        assert is_retryable_exception(ValueError("無效的值"), config) is False

    def test_exception_with_timeout_keyword(self):
        """測試訊息包含 timeout 關鍵字。"""
        config = RetryConfig()
        assert is_retryable_exception(Exception("Operation timeout"), config) is True

    def test_exception_with_retry_keyword(self):
        """測試訊息包含 retry 關鍵字。"""
        config = RetryConfig()
        assert is_retryable_exception(Exception("Please retry later"), config) is True


class TestRetryAsync:
    """異步重試測試。"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """測試第一次就成功。"""
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(succeed, config=RetryConfig())
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """測試重試後成功。"""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("暫時失敗")
            return "success"

        config = RetryConfig(max_retries=5, base_delay=0.01)
        result = await retry_async(fail_then_succeed, config=config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """測試超過最大重試次數。"""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("永遠失敗")

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(TimeoutError):
            await retry_async(always_fail, config=config)

        assert call_count == 3  # 1 次嘗試 + 2 次重試

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """測試不可重試的例外。"""
        call_count = 0

        async def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("不可重試")

        config = RetryConfig(max_retries=3, base_delay=0.01)

        with pytest.raises(ValueError):
            await retry_async(raise_value_error, config=config)

        assert call_count == 1  # 不應重試


class TestRetryContext:
    """重試上下文測試。"""

    @pytest.mark.asyncio
    async def test_context_success(self):
        """測試上下文管理器成功情況。"""
        async with RetryContext(RetryConfig(max_retries=3)) as ctx:
            assert ctx.should_retry() is True
            # 模擬成功操作
            ctx.attempt = 1

    @pytest.mark.asyncio
    async def test_context_handle_error(self):
        """測試上下文管理器錯誤處理。"""
        config = RetryConfig(max_retries=2, base_delay=0.01)

        async with RetryContext(config) as ctx:
            errors_handled = 0
            while ctx.should_retry():
                try:
                    if errors_handled < 2:
                        raise TimeoutError("測試錯誤")
                    break
                except TimeoutError as e:
                    errors_handled += 1
                    try:
                        await ctx.handle_error(e)
                    except TimeoutError:
                        break  # 超過重試次數

            assert errors_handled == 2
