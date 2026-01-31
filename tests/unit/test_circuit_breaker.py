"""斷路器的單元測試。"""

import asyncio
import pytest

from kof_notebooklm_mcp.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
)


class TestCircuitBreaker:
    """CircuitBreaker 測試。"""

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """測試初始狀態。"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False

    @pytest.mark.asyncio
    async def test_allow_request_when_closed(self):
        """測試關閉狀態允許請求。"""
        cb = CircuitBreaker("test")
        result = await cb.allow_request()
        assert result is True

    @pytest.mark.asyncio
    async def test_open_after_failures(self):
        """測試連續失敗後開啟。"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        # 記錄連續失敗
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_reject_when_open(self):
        """測試開啟狀態拒絕請求。"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config)

        # 開啟斷路器
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # 應該拒絕請求
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            await cb.allow_request()

        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """測試逾時後進入半開狀態。"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker("test", config)

        # 開啟斷路器
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # 等待恢復時間
        await asyncio.sleep(0.15)

        # 應該允許請求（進入半開狀態）
        result = await cb.allow_request()
        assert result is True
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_close_after_success_in_half_open(self):
        """測試半開狀態成功後關閉。"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        cb = CircuitBreaker("test", config)

        # 開啟斷路器
        await cb.record_failure()
        await cb.record_failure()

        # 等待並進入半開狀態
        await asyncio.sleep(0.15)
        await cb.allow_request()

        # 記錄成功
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopen_after_failure_in_half_open(self):
        """測試半開狀態失敗後重新開啟。"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker("test", config)

        # 開啟斷路器
        await cb.record_failure()
        await cb.record_failure()

        # 等待並進入半開狀態
        await asyncio.sleep(0.15)
        await cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN

        # 記錄失敗
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """測試成功重置失敗計數。"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        # 兩次失敗
        await cb.record_failure()
        await cb.record_failure()

        # 一次成功
        await cb.record_success()

        # 再兩次失敗不應該開啟（因為計數已重置）
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        # 第三次失敗才開啟
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_method(self):
        """測試透過 call 方法執行函式。"""
        cb = CircuitBreaker("test")

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_method_with_failure(self):
        """測試 call 方法記錄失敗。"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("測試失敗")

        # 連續失敗
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)

        # 斷路器應該開啟
        assert cb.is_open is True

    @pytest.mark.asyncio
    async def test_status(self):
        """測試狀態查詢。"""
        cb = CircuitBreaker("test_cb")
        await cb.record_failure()

        status = cb.status()
        assert status["name"] == "test_cb"
        assert status["state"] == "closed"
        assert status["failure_count"] == 1
