"""
Configuration management for kof-notebooklm-mcp.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Configuration settings for the NotebookLM MCP server."""

    # Browser profile location
    profile_path: Path = field(default_factory=lambda: Path.home() / ".kof-notebooklm" / "profile")

    # Browser settings
    headless: bool = True
    timeout_ms: int = 30000
    slow_mo_ms: int = 0

    # Rate limiting
    rate_limit_per_minute: int = 10

    # NotebookLM URLs
    base_url: str = "https://notebooklm.google.com"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        profile_path_str = os.getenv("NOTEBOOKLM_PROFILE_PATH")
        profile_path = (
            Path(profile_path_str).expanduser()
            if profile_path_str
            else Path.home() / ".kof-notebooklm" / "profile"
        )

        headless_str = os.getenv("NOTEBOOKLM_HEADLESS", "true").lower()
        headless = headless_str not in ("false", "0", "no")

        timeout_ms = int(os.getenv("NOTEBOOKLM_TIMEOUT", "30000"))
        slow_mo_ms = int(os.getenv("NOTEBOOKLM_SLOW_MO", "0"))
        rate_limit = int(os.getenv("NOTEBOOKLM_RATE_LIMIT", "10"))

        return cls(
            profile_path=profile_path,
            headless=headless,
            timeout_ms=timeout_ms,
            slow_mo_ms=slow_mo_ms,
            rate_limit_per_minute=rate_limit,
        )

    def ensure_profile_dir(self) -> None:
        """Create profile directory with secure permissions if it doesn't exist."""
        self.profile_path.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner only) on Unix systems
        try:
            self.profile_path.chmod(0o700)
        except OSError:
            # Windows doesn't support chmod the same way
            pass


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
