"""FastMCP server factory for SmartBook partial MCP support."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def mcp_enabled() -> bool:
    return os.environ.get("SMARTBOOK_MCP_ENABLED", "").lower() in ("1", "true", "yes")


def create_mcp() -> Any:
    """Create a FastMCP instance with SmartBook read-only tools registered."""
    from mcp.server.fastmcp import FastMCP

    from smartbook_mcp.tools import register_tools

    mcp = FastMCP(
        "smartbook",
        instructions=(
            "SmartBook accounting MCP — partial read-only access. "
            "Authenticate with SMARTBOOK_MCP_TOKEN (JWT). "
            "Tools require an active account_set_id matching the JWT claim."
        ),
    )
    register_tools(mcp)
    return mcp


def create_http_app() -> Any:
    """Return a Starlette app for Streamable HTTP transport (mount at /mcp).

    When mounted under ``/mcp`` on svc-accounting, the internal streamable
    path must be ``/`` so the public URL is ``/mcp`` (not ``/mcp/mcp``).
    """
    from mcp.server.fastmcp import FastMCP

    from smartbook_mcp.tools import register_tools

    mcp = FastMCP(
        "smartbook",
        instructions=(
            "SmartBook accounting MCP — partial read-only access. "
            "Authenticate with SMARTBOOK_MCP_TOKEN (JWT). "
            "Tools require an active account_set_id matching the JWT claim."
        ),
        streamable_http_path="/",
    )
    register_tools(mcp)
    return mcp.streamable_http_app()


def run_stdio() -> None:
    """Run the MCP server over stdio (Cursor / Claude Desktop local)."""
    mcp = create_mcp()
    logger.info("Starting SmartBook MCP (stdio transport)")
    mcp.run(transport="stdio")
