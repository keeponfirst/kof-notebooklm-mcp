"""
CLI commands for kof-notebooklm-mcp.

Provides commands for authentication and management.
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv


def init_auth() -> None:
    """
    Initialize authentication by opening a browser for manual Google login.

    This command opens a visible browser window where the user can log in
    to their Google account. The session cookies are saved to a persistent
    browser profile that the MCP server uses for subsequent operations.
    """
    # Load environment variables
    load_dotenv()

    from .client.session import run_interactive_login

    success = run_interactive_login()
    sys.exit(0 if success else 1)


def check_health() -> None:
    """
    Check the health of the NotebookLM connection.

    Verifies browser can launch and user is authenticated.
    """
    import json

    load_dotenv()

    from .tools.health_check import health_check

    async def run_check():
        result = await health_check()
        print(json.dumps(result.to_dict(), indent=2))
        return result.status == "healthy"

    success = asyncio.run(run_check())
    sys.exit(0 if success else 1)


def main_cli() -> None:
    """Main CLI entrypoint with subcommands."""
    parser = argparse.ArgumentParser(
        description="KOF NotebookLM MCP Server CLI",
        prog="kof-notebooklm",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init subcommand
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize authentication (opens browser for Google login)",
    )

    # health subcommand
    health_parser = subparsers.add_parser(
        "health",
        help="Check connection health",
    )

    # serve subcommand (for MCP server)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the MCP server",
    )

    args = parser.parse_args()

    if args.command == "init":
        init_auth()
    elif args.command == "health":
        check_health()
    elif args.command == "serve":
        from .server import main

        main()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
