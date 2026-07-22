"""Tests for MCP server result handling."""

import json
from unittest.mock import AsyncMock

import pytest

from kof_notebooklm_mcp import server as server_module
from kof_notebooklm_mcp.tools.health_check import HealthCheckResult


def test_tool_arguments_are_redacted_before_logging():
    """來源內容、問題與 URL 不應以明文寫進 INFO 日誌。"""
    summary = server_module._summarize_tool_arguments(
        {
            "notebook_id": "notebook-1",
            "title": "研究來源",
            "text": "sensitive source",
            "question": "sensitive question",
            "url": "https://example.com/private-path",
        }
    )

    assert summary == {
        "notebook_id": "notebook-1",
        "title": "研究來源",
        "text": "<redacted: 16 chars>",
        "question": "<redacted: 18 chars>",
        "url": "<redacted: URL>",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "authenticated", "browser_ok", "error"),
    [
        ("healthy", True, True, None),
        ("degraded", False, True, "Session expired"),
        ("unhealthy", False, False, "Browser failed to launch"),
    ],
)
async def test_health_check_status_error_is_not_treated_as_error_object(
    monkeypatch,
    status,
    authenticated,
    browser_ok,
    error,
):
    """Health status messages must serialize without dict-only error handling."""
    result = HealthCheckResult(
        status=status,
        authenticated=authenticated,
        latency_ms=25,
        browser_ok=browser_ok,
        error=error,
    )
    circuit_breaker = AsyncMock()

    monkeypatch.setattr(server_module, "health_check", AsyncMock(return_value=result))
    monkeypatch.setattr(
        server_module,
        "get_circuit_breaker",
        lambda _name: circuit_breaker,
    )

    response = await server_module.call_tool("health_check", {})
    payload = json.loads(response[0].text)

    assert payload == result.to_dict()
    circuit_breaker.record_failure.assert_not_awaited()
    circuit_breaker.record_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_check_accepts_missing_arguments(monkeypatch):
    """無參數工具被 MCP runtime 以 None 呼叫時也不應觸發 NoneType 錯誤。"""
    result = HealthCheckResult(
        status="healthy",
        authenticated=True,
        latency_ms=25,
        browser_ok=True,
        error=None,
    )
    circuit_breaker = AsyncMock()

    monkeypatch.setattr(server_module, "health_check", AsyncMock(return_value=result))
    monkeypatch.setattr(
        server_module,
        "get_circuit_breaker",
        lambda _name: circuit_breaker,
    )

    response = await server_module.call_tool("health_check", None)

    assert json.loads(response[0].text) == result.to_dict()
