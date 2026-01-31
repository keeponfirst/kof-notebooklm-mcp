"""Unit tests for health_check tool."""

import pytest

from kof_notebooklm_mcp.tools.health_check import HealthCheckResult


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_to_dict_healthy(self):
        """Test serialization of healthy result."""
        result = HealthCheckResult(
            status="healthy",
            authenticated=True,
            latency_ms=1500,
            browser_ok=True,
            error=None,
        )
        d = result.to_dict()
        assert d["status"] == "healthy"
        assert d["authenticated"] is True
        assert d["latency_ms"] == 1500
        assert d["browser_ok"] is True
        assert d["error"] is None

    def test_to_dict_unhealthy(self):
        """Test serialization of unhealthy result."""
        result = HealthCheckResult(
            status="unhealthy",
            authenticated=False,
            latency_ms=500,
            browser_ok=False,
            error="Browser failed to launch",
        )
        d = result.to_dict()
        assert d["status"] == "unhealthy"
        assert d["authenticated"] is False
        assert d["browser_ok"] is False
        assert d["error"] == "Browser failed to launch"

    def test_to_dict_degraded(self):
        """Test serialization of degraded result."""
        result = HealthCheckResult(
            status="degraded",
            authenticated=False,
            latency_ms=2000,
            browser_ok=True,
            error="Session expired",
        )
        d = result.to_dict()
        assert d["status"] == "degraded"
        assert d["authenticated"] is False
        assert d["browser_ok"] is True
