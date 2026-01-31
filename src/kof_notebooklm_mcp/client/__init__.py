"""
NotebookLM client layer.

Provides browser automation for interacting with NotebookLM:
- browser.py: Playwright browser management
- session.py: Profile and session handling
- pages/: Page Object Models for NotebookLM UI
"""

from .browser import BrowserManager, get_browser_manager, shutdown_browser
from .session import SessionManager, run_interactive_login

__all__ = [
    "BrowserManager",
    "get_browser_manager",
    "shutdown_browser",
    "SessionManager",
    "run_interactive_login",
]
