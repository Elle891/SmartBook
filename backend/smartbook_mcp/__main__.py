"""CLI entry: python -m smartbook_mcp

Runs the SmartBook MCP server over stdio.

Environment:
  SMARTBOOK_MCP_TOKEN   Required JWT from /auth login (or switch account-set).
  SMARTBOOK_MCP_SKIP_SESSION / SMARTBOOK_MCP_REQUIRE_SESSION
  PYTHONPATH=backend (or run from backend with path set).
"""

from __future__ import annotations

from smartbook_mcp.server import run_stdio


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()
