"""
MCP Server entrypoint for kof-notebooklm-mcp.

This module implements the MCP server that exposes NotebookLM tools.
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client.browser import shutdown_browser
from .tools.health_check import health_check
from .tools.list_notebooks import list_notebooks
from .tools.get_notebook import get_notebook
from .tools.list_sources import list_sources
from .tools.add_source import add_source
from .tools.ask import ask
from .tools.create_notebook import create_notebook
from .utils.rate_limit import get_rate_limiter, RateLimitExceeded
from .utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
from .utils.errors import handle_exception, error_response, ErrorCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Create the MCP server
server = Server("kof-notebooklm-mcp")


# Tool definitions
TOOL_DEFINITIONS = [
    Tool(
        name="health_check",
        description="Verify NotebookLM connection and authentication status. "
        "Returns status (healthy/degraded/unhealthy), authentication state, and latency.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="list_notebooks",
        description="List all notebooks in the user's NotebookLM account.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of notebooks to return (default: 50)",
                    "default": 50,
                }
            },
            "required": [],
        },
    ),
    Tool(
        name="get_notebook",
        description="Get detailed information about a specific notebook.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_id": {
                    "type": "string",
                    "description": "The notebook ID (from list_notebooks)",
                }
            },
            "required": ["notebook_id"],
        },
    ),
    Tool(
        name="list_sources",
        description="List all sources in a notebook.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_id": {
                    "type": "string",
                    "description": "The notebook ID",
                }
            },
            "required": ["notebook_id"],
        },
    ),
    Tool(
        name="add_source",
        description="Add a URL or text source to a notebook. "
        "For URLs, NotebookLM will fetch and process the content. "
        "For text, provide markdown or plain text content directly.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_id": {
                    "type": "string",
                    "description": "The notebook ID to add source to",
                },
                "source_type": {
                    "type": "string",
                    "enum": ["url", "text"],
                    "description": "Type of source to add",
                },
                "url": {
                    "type": "string",
                    "description": "URL to add (required if source_type is 'url')",
                },
                "text": {
                    "type": "string",
                    "description": "Text/markdown content (required if source_type is 'text')",
                },
                "title": {
                    "type": "string",
                    "description": "Title for text sources (optional)",
                },
            },
            "required": ["notebook_id", "source_type"],
        },
    ),
    Tool(
        name="ask",
        description="Query a notebook and get an AI-generated answer with source citations. "
        "The answer is based on the sources in the notebook.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_id": {
                    "type": "string",
                    "description": "The notebook ID to query",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask",
                },
                "include_citations": {
                    "type": "boolean",
                    "description": "Whether to extract source citations (default: true)",
                    "default": True,
                },
            },
            "required": ["notebook_id", "question"],
        },
    ),
    Tool(
        name="create_notebook",
        description="Create a new notebook and optionally rename it.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the new notebook (optional)",
                }
            },
            "required": [],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with rate limiting and circuit breaker protection."""
    logger.info("Tool called: %s with args: %s", name, arguments)

    # 取得速率限制器和斷路器
    rate_limiter = get_rate_limiter()
    circuit_breaker = get_circuit_breaker("notebooklm")

    try:
        # 檢查斷路器狀態（health_check 跳過）
        if name != "health_check":
            try:
                await circuit_breaker.allow_request()
            except CircuitBreakerOpen as e:
                logger.warning(f"斷路器已開啟: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            error_response(
                                ErrorCode.RATE_LIMITED,
                                f"服務暫時不可用，請在 {e.retry_after:.1f} 秒後重試",
                                {"retry_after_seconds": round(e.retry_after, 1)},
                            )
                        ),
                    )
                ]

        # 套用速率限制（health_check 跳過）
        if name != "health_check":
            try:
                # 寫入操作使用獨立的速率限制
                operation = name if name in ("add_source", "ask", "create_notebook") else "default"
                await rate_limiter.acquire(operation, blocking=True, timeout=30.0)
            except RateLimitExceeded as e:
                logger.warning(f"速率限制超過: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(e.to_error_dict()),
                    )
                ]

        # 執行工具
        result_dict: dict[str, Any] | None = None

        if name == "health_check":
            result = await health_check()
            result_dict = result.to_dict()

        elif name == "list_notebooks":
            limit = arguments.get("limit", 50)
            result = await list_notebooks(limit=limit)
            result_dict = result.to_dict()

        elif name == "get_notebook":
            notebook_id = arguments.get("notebook_id", "")
            result = await get_notebook(notebook_id=notebook_id)
            result_dict = result.to_dict()

        elif name == "list_sources":
            notebook_id = arguments.get("notebook_id", "")
            result = await list_sources(notebook_id=notebook_id)
            result_dict = result.to_dict()

        elif name == "add_source":
            notebook_id = arguments.get("notebook_id", "")
            source_type = arguments.get("source_type", "")
            url = arguments.get("url")
            text = arguments.get("text")
            title = arguments.get("title")
            result = await add_source(
                notebook_id=notebook_id,
                source_type=source_type,
                url=url,
                text=text,
                title=title,
            )
            result_dict = result.to_dict()

        elif name == "ask":
            notebook_id = arguments.get("notebook_id", "")
            question = arguments.get("question", "")
            include_citations = arguments.get("include_citations", True)
            result = await ask(
                notebook_id=notebook_id,
                question=question,
                include_citations=include_citations,
            )
            result_dict = result.to_dict()

        elif name == "create_notebook":
            title = arguments.get("title")
            result = await create_notebook(title=title)
            result_dict = result.to_dict()

        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        error_response(
                            ErrorCode.UNKNOWN_TOOL,
                            f"未知的工具: {name}",
                        )
                    ),
                )
            ]

        # 檢查結果是否有錯誤
        if result_dict and "error" in result_dict:
            # 記錄失敗（但不是所有錯誤都應觸發斷路器）
            error_code = result_dict["error"].get("code", "")
            if error_code in ("TIMEOUT", "NETWORK_ERROR", "INTERNAL_ERROR"):
                await circuit_breaker.record_failure()
        else:
            # 記錄成功
            await circuit_breaker.record_success()

        return [TextContent(type="text", text=json.dumps(result_dict))]

    except Exception as e:
        # 記錄失敗
        await circuit_breaker.record_failure()
        # 使用標準化錯誤處理
        error_dict = handle_exception(e, name)
        return [TextContent(type="text", text=json.dumps(error_dict))]


async def run_server() -> None:
    """Run the MCP server."""
    logger.info("Starting kof-notebooklm-mcp server")

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    async def shutdown(sig: signal.Signals) -> None:
        logger.info("Received %s, shutting down...", sig.name)
        await shutdown_browser()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await shutdown_browser()


def main() -> None:
    """Main entrypoint for the MCP server."""
    load_dotenv()
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
