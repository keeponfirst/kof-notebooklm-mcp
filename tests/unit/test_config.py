"""Unit tests for configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kof_notebooklm_mcp.config import Config


class TestConfig:
    """Tests for Config class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()
        assert config.headless is True
        assert config.timeout_ms == 30000
        assert config.slow_mo_ms == 0
        assert config.rate_limit_per_minute == 10
        assert config.base_url == "https://notebooklm.google.com"

    def test_from_env_defaults(self):
        """Test loading config with no environment variables set."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            assert config.headless is True
            assert config.timeout_ms == 30000

    def test_from_env_custom_values(self):
        """Test loading config with custom environment variables."""
        env = {
            "NOTEBOOKLM_PROFILE_PATH": "/custom/path",
            "NOTEBOOKLM_HEADLESS": "false",
            "NOTEBOOKLM_TIMEOUT": "60000",
            "NOTEBOOKLM_SLOW_MO": "100",
            "NOTEBOOKLM_RATE_LIMIT": "5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()
            assert config.profile_path == Path("/custom/path")
            assert config.headless is False
            assert config.timeout_ms == 60000
            assert config.slow_mo_ms == 100
            assert config.rate_limit_per_minute == 5

    def test_headless_env_variations(self):
        """Test various values for NOTEBOOKLM_HEADLESS."""
        # True values
        for val in ["true", "True", "TRUE", "1", "yes", "anything"]:
            with patch.dict(os.environ, {"NOTEBOOKLM_HEADLESS": val}, clear=True):
                config = Config.from_env()
                assert config.headless is True, f"Expected True for '{val}'"

        # False values
        for val in ["false", "False", "FALSE", "0", "no"]:
            with patch.dict(os.environ, {"NOTEBOOKLM_HEADLESS": val}, clear=True):
                config = Config.from_env()
                assert config.headless is False, f"Expected False for '{val}'"

    def test_profile_path_expansion(self):
        """Test that ~ in profile path is expanded."""
        with patch.dict(os.environ, {"NOTEBOOKLM_PROFILE_PATH": "~/test"}, clear=True):
            config = Config.from_env()
            assert str(config.profile_path).startswith(str(Path.home()))

    def test_ensure_profile_dir(self, tmp_path):
        """Test profile directory creation."""
        profile_path = tmp_path / "new_profile"
        config = Config(profile_path=profile_path)

        assert not profile_path.exists()
        config.ensure_profile_dir()
        assert profile_path.exists()
        assert profile_path.is_dir()
