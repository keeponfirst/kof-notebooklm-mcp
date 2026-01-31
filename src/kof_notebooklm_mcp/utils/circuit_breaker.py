"""
斷路器模組。

當連續失敗次數過多時，暫時停止請求以保護系統。
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """斷路器狀態。"""

    CLOSED = "closed"  # 正常運作
    OPEN = "open"  # 斷路（快速失敗）
    HALF_OPEN = "half_open"  # 測試恢復


@dataclass
class CircuitBreakerConfig:
    """斷路器設定。"""

    failure_threshold: int = 5  # 觸發斷路的連續失敗次數
    recovery_timeout: float = 60.0  # 斷路後等待恢復的時間（秒）
    half_open_max_calls: int = 1  # 半開狀態允許的測試請求數
    success_threshold: int = 1  # 恢復所需的連續成功次數


class CircuitBreakerOpen(Exception):
    """斷路器開啟時拋出的例外。"""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"斷路器已開啟，請在 {retry_after:.1f} 秒後重試")


class CircuitBreaker:
    """
    斷路器實現。

    狀態轉換:
    - CLOSED → OPEN: 連續失敗達到閾值
    - OPEN → HALF_OPEN: 等待恢復時間後
    - HALF_OPEN → CLOSED: 測試請求成功
    - HALF_OPEN → OPEN: 測試請求失敗
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """取得目前狀態。"""
        return self._state

    @property
    def is_closed(self) -> bool:
        """檢查是否為關閉狀態（正常運作）。"""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """檢查是否為開啟狀態（斷路）。"""
        return self._state == CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """檢查是否應該嘗試從 OPEN 轉換到 HALF_OPEN。"""
        if self._state != CircuitState.OPEN:
            return False

        if self._last_failure_time is None:
            return True

        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.config.recovery_timeout

    async def _transition_to_open(self) -> None:
        """轉換到開啟狀態。"""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()
        self._half_open_calls = 0
        logger.warning(f"斷路器 '{self.name}' 已開啟（連續失敗 {self._failure_count} 次）")

    async def _transition_to_half_open(self) -> None:
        """轉換到半開狀態。"""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0
        logger.info(f"斷路器 '{self.name}' 進入半開狀態，開始測試恢復")

    async def _transition_to_closed(self) -> None:
        """轉換到關閉狀態。"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(f"斷路器 '{self.name}' 已關閉（恢復正常）")

    async def record_success(self) -> None:
        """記錄成功。"""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    await self._transition_to_closed()

    async def record_failure(self) -> None:
        """記錄失敗。"""
        async with self._lock:
            self._failure_count += 1
            self._success_count = 0

            if self._state == CircuitState.HALF_OPEN:
                # 半開狀態下失敗，重新開啟
                await self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    await self._transition_to_open()

    async def allow_request(self) -> bool:
        """
        檢查是否允許請求。

        Returns:
            是否允許

        Raises:
            CircuitBreakerOpen: 如果斷路器開啟
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to_half_open()
                else:
                    # 計算剩餘等待時間
                    if self._last_failure_time:
                        elapsed = time.monotonic() - self._last_failure_time
                        retry_after = self.config.recovery_timeout - elapsed
                    else:
                        retry_after = self.config.recovery_timeout
                    raise CircuitBreakerOpen(max(0, retry_after))

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(self.config.recovery_timeout)
                self._half_open_calls += 1

            return True

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        透過斷路器執行函式。

        Args:
            func: 要執行的函式
            *args: 位置參數
            **kwargs: 關鍵字參數

        Returns:
            函式回傳值

        Raises:
            CircuitBreakerOpen: 如果斷路器開啟
            Exception: 函式執行時的例外
        """
        await self.allow_request()

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise

    def status(self) -> dict[str, Any]:
        """
        取得斷路器狀態。

        Returns:
            狀態字典
        """
        result = {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }

        if self._last_failure_time and self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            result["time_until_half_open"] = max(
                0, round(self.config.recovery_timeout - elapsed, 1)
            )

        return result


# 全域斷路器實例
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str = "default") -> CircuitBreaker:
    """
    取得或建立斷路器實例。

    Args:
        name: 斷路器名稱

    Returns:
        CircuitBreaker 實例
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name)
    return _circuit_breakers[name]


def circuit_breaker_status() -> dict[str, Any]:
    """
    取得所有斷路器狀態。

    Returns:
        狀態字典
    """
    return {name: cb.status() for name, cb in _circuit_breakers.items()}
