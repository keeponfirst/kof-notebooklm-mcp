"""
Browser management for NotebookLM automation.

Uses Playwright to manage a Chromium browser instance with persistent profile.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from ..config import Config, get_config

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manages a Playwright browser instance with persistent profile.

    The browser uses a persistent context to maintain session cookies
    across restarts, avoiding the need for repeated authentication.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the browser with persistent profile."""
        async with self._lock:
            if self._playwright is not None:
                return  # Already started

            logger.info("Starting browser with profile at %s", self.config.profile_path)
            self.config.ensure_profile_dir()

            self._playwright = await async_playwright().start()

            # Use persistent context to maintain session
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_path),
                headless=self.config.headless,
                slow_mo=self.config.slow_mo_ms,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
                viewport={"width": 1280, "height": 800},
            )

            # Get or create the main page
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()

            logger.info("Browser started successfully")

    async def stop(self) -> None:
        """Stop the browser and cleanup resources."""
        async with self._lock:
            if self._context is not None:
                await self._context.close()
                self._context = None
                self._page = None

            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

            logger.info("Browser stopped")

    async def get_page(self) -> Page:
        """Get the main browser page, starting browser if needed."""
        if self._page is None:
            await self.start()
        assert self._page is not None
        return self._page

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL and wait for page load."""
        page = await self.get_page()
        logger.debug("Navigating to %s", url)
        await page.goto(url, wait_until=wait_until, timeout=self.config.timeout_ms)

    async def is_authenticated(self) -> bool:
        """
        Check if the user is authenticated with Google.

        Navigates to NotebookLM and checks if we land on the main page
        or get redirected to login.
        """
        page = await self.get_page()

        try:
            await page.goto(
                self.config.base_url,
                wait_until="domcontentloaded",
                timeout=self.config.timeout_ms,
            )

            # Wait a bit for any redirects
            await page.wait_for_timeout(2000)

            current_url = page.url

            # Check if we're on the NotebookLM page (not Google login)
            if "accounts.google.com" in current_url:
                logger.info("User needs to authenticate (redirected to Google login)")
                return False

            # Check for presence of notebook-related elements
            # These selectors may need adjustment based on actual NotebookLM UI
            try:
                await page.wait_for_selector(
                    '[aria-label*="notebook"], [data-notebook], .notebook-list, main',
                    timeout=5000,
                )
                logger.info("User is authenticated")
                return True
            except Exception:
                # If no notebook elements found, might still be loading or not logged in
                if "notebooklm.google.com" in current_url:
                    # We're on the site but can't find elements - might be loading
                    return True
                return False

        except Exception as e:
            logger.warning("Error checking authentication: %s", e)
            return False

    @asynccontextmanager
    async def managed_session(self) -> AsyncGenerator["BrowserManager", None]:
        """Context manager for browser session lifecycle."""
        try:
            await self.start()
            yield self
        finally:
            await self.stop()


# Global browser instance (lazy loaded)
_browser_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


async def shutdown_browser() -> None:
    """Shutdown the global browser instance."""
    global _browser_manager
    if _browser_manager is not None:
        await _browser_manager.stop()
        _browser_manager = None
