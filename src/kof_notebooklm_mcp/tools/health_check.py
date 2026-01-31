"""
health_check tool implementation.

Verifies NotebookLM connection and authentication status.
"""

import logging
import time
from dataclasses import dataclass
from typing import Literal

from ..client.browser import BrowserManager, get_browser_manager
from ..config import get_config

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    status: Literal["healthy", "degraded", "unhealthy"]
    authenticated: bool
    latency_ms: int
    browser_ok: bool
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "authenticated": self.authenticated,
            "latency_ms": self.latency_ms,
            "browser_ok": self.browser_ok,
            "error": self.error,
        }


async def health_check() -> HealthCheckResult:
    """
    Perform a health check of the NotebookLM MCP server.

    Verifies:
    1. Browser can launch
    2. Can navigate to notebooklm.google.com
    3. User is authenticated (not redirected to login)

    Returns:
        HealthCheckResult with status information.
    """
    start_time = time.time()
    config = get_config()

    # Check if profile exists
    if not config.profile_path.exists():
        return HealthCheckResult(
            status="unhealthy",
            authenticated=False,
            latency_ms=int((time.time() - start_time) * 1000),
            browser_ok=False,
            error="No browser profile found. Run 'kof-notebooklm-init' to authenticate.",
        )

    browser: BrowserManager | None = None
    browser_ok = False
    authenticated = False
    error: str | None = None

    try:
        # Try to start browser
        browser = get_browser_manager()
        await browser.start()
        browser_ok = True

        # Check authentication
        authenticated = await browser.is_authenticated()

        if not authenticated:
            error = "Session expired. Run 'kof-notebooklm-init' to re-authenticate."

    except Exception as e:
        logger.exception("Health check failed")
        error = str(e)
        if "Executable doesn't exist" in str(e) or "browserType.launch" in str(e):
            error = "Playwright browser not installed. Run 'playwright install chromium'."

    latency_ms = int((time.time() - start_time) * 1000)

    # Determine overall status
    if browser_ok and authenticated:
        status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    elif browser_ok and not authenticated:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthCheckResult(
        status=status,
        authenticated=authenticated,
        latency_ms=latency_ms,
        browser_ok=browser_ok,
        error=error,
    )
