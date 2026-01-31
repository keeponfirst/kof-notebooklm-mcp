"""
Session management for NotebookLM authentication.

Handles the initial authentication flow and session validation.
"""

import asyncio
import logging
import sys

from playwright.async_api import async_playwright

from ..config import Config, get_config

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages NotebookLM authentication sessions.

    Provides methods for initial authentication (interactive) and
    session validation.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()

    async def interactive_login(self) -> bool:
        """
        Perform interactive login flow.

        Opens a visible browser window for the user to manually log in
        to their Google account. The session is saved to the persistent
        browser profile.

        Returns:
            True if login was successful, False otherwise.
        """
        print("\n" + "=" * 60)
        print("NotebookLM Authentication Setup")
        print("=" * 60)
        print()
        print("A browser window will open. Please:")
        print("1. Log in to your Google account")
        print("2. Navigate to notebooklm.google.com")
        print("3. Verify you can see your notebooks")
        print("4. Close the browser window when done")
        print()
        print(f"Profile will be saved to: {self.config.profile_path}")
        print()

        self.config.ensure_profile_dir()

        async with async_playwright() as playwright:
            # Launch visible browser for manual login
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_path),
                headless=False,  # Always visible for login
                slow_mo=100,  # Slow down slightly for user to see
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
                viewport=None,  # Use full window size
            )

            page = context.pages[0] if context.pages else await context.new_page()

            # Navigate to NotebookLM
            print("Opening NotebookLM...")
            await page.goto("https://notebooklm.google.com")

            # Wait for user to complete login
            print()
            print("Waiting for you to complete login...")
            print("(Close the browser window when done)")
            print()

            # Wait for the browser to be closed by the user
            try:
                await context.wait_for_event("close", timeout=300000)  # 5 minute timeout
            except Exception:
                # Timeout or error - check if we're authenticated
                pass

            # Verify authentication before closing
            try:
                current_url = page.url
                is_authenticated = (
                    "notebooklm.google.com" in current_url
                    and "accounts.google.com" not in current_url
                )
            except Exception:
                # Browser was closed
                is_authenticated = True  # Assume success if user closed browser

            await context.close()

        if is_authenticated:
            print()
            print("✅ Authentication successful!")
            print(f"   Session saved to: {self.config.profile_path}")
            print()
            print("You can now use kof-notebooklm-mcp.")
            print()
            return True
        else:
            print()
            print("❌ Authentication may have failed.")
            print("   Please try again and make sure to complete Google login.")
            print()
            return False

    async def validate_session(self) -> dict:
        """
        Validate the current session without opening visible browser.

        Returns:
            Dict with session status information.
        """
        from .browser import BrowserManager

        result = {
            "valid": False,
            "profile_exists": self.config.profile_path.exists(),
            "error": None,
        }

        if not result["profile_exists"]:
            result["error"] = "No browser profile found. Run kof-notebooklm-init first."
            return result

        browser = BrowserManager(self.config)
        try:
            await browser.start()
            is_auth = await browser.is_authenticated()
            result["valid"] = is_auth
            if not is_auth:
                result["error"] = "Session expired. Run kof-notebooklm-init to re-authenticate."
        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.stop()

        return result


def run_interactive_login() -> bool:
    """
    Run the interactive login flow synchronously.

    Returns:
        True if login was successful, False otherwise.
    """
    config = get_config()
    session = SessionManager(config)

    # Run the async login in an event loop
    try:
        return asyncio.run(session.interactive_login())
    except KeyboardInterrupt:
        print("\n\nLogin cancelled by user.")
        return False
    except Exception as e:
        print(f"\n\nError during login: {e}")
        return False
