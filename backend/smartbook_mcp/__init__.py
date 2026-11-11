"""Partial MCP support for SmartBook — read-only accounting tools for agents."""

from __future__ import annotations

__all__ = ["create_mcp", "create_http_app", "mcp_enabled"]

from smartbook_mcp.server import create_http_app, create_mcp, mcp_enabled
