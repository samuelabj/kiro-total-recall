"""FastMCP server for Kiro Total Recall."""

import os
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .indexer import get_index
from .models import Source
from .query import search_conversations

mcp = FastMCP("kiro-total-recall")


def _preload_index():
    """Preload embedding model and index in background (non-blocking)."""
    try:
        index = get_index()
        _ = index.model  # Trigger model load
        index.ensure_index()  # Build index
    except Exception:
        pass  # Errors will surface on actual search


# Start preloading in daemon thread - doesn't block server startup
threading.Thread(target=_preload_index, daemon=True).start()


def _get_current_workspace() -> str | None:
    """Get current workspace from environment or cwd.

    Kiro MCP servers don't receive the IDE workspace path directly,
    so we check environment variables that can be set in the MCP config,
    then fall back to cwd.
    """
    # Try Kiro-specific env vars (set manually in mcp.json config)
    for var in ("KIRO_PROJECT_DIR", "KIRO_WORKSPACE"):
        if val := os.environ.get(var):
            return val
    # Fall back to PWD/cwd (usually the --directory of the MCP server)
    return os.environ.get("PWD") or str(Path.cwd())


def _search(
    query: str,
    workspace: str | None,
    source: Source | None,
    after: str | None,
    before: str | None,
    context_size: int,
    threshold: float,
    max_results: int,
    offset: int,
) -> dict:
    """Common search implementation."""
    return search_conversations(
        query=query,
        workspace=workspace,
        source=source,
        after=after,
        before=before,
        context_size=context_size,
        threshold=threshold,
        max_results=max_results,
        offset=offset,
    ).model_dump(mode="json")


@mcp.tool()
def search_project_history(
    query: str,
    after: str | None = None,
    before: str | None = None,
    context_size: int = 3,
    threshold: float = 0.2,
    max_results: int = 10,
    offset: int = 0,
) -> dict:
    """
    Search conversation history for the CURRENT WORKSPACE only.

    Use this to find workspace-specific context: past decisions, implementation
    details, bugs discussed, architecture choices in this codebase.

    Args:
        query: Keywords or sentence describing what to find
        after: Filter to messages on/after this date (ISO 8601: "2025-01-15")
        before: Filter to messages before this date (ISO 8601)
        context_size: Messages to include before AND after each match (default: 3)
        threshold: Minimum similarity 0-1 (default: 0.2)
        max_results: Maximum results to return (default: 10)
        offset: Skip results for pagination (default: 0)

    Returns:
        Search results with matched messages, scores, context, and pagination info
    """
    return _search(
        query=query,
        workspace=_get_current_workspace(),
        source=None,
        after=after,
        before=before,
        context_size=context_size,
        threshold=threshold,
        max_results=max_results,
        offset=offset,
    )


@mcp.tool()
def search_global_history(
    query: str,
    after: str | None = None,
    before: str | None = None,
    context_size: int = 3,
    threshold: float = 0.2,
    max_results: int = 10,
    offset: int = 0,
) -> dict:
    """
    Search conversation history across ALL WORKSPACES.

    Use this to find cross-project knowledge: user preferences, coding patterns,
    common solutions, and insights from all previous work.

    Args:
        query: Keywords or sentence describing what to find
        after: Filter to messages on/after this date (ISO 8601: "2025-01-15")
        before: Filter to messages before this date (ISO 8601)
        context_size: Messages to include before AND after each match (default: 3)
        threshold: Minimum similarity 0-1 (default: 0.2)
        max_results: Maximum results to return (default: 10)
        offset: Skip results for pagination (default: 0)

    Returns:
        Search results with matched messages, scores, workspace, context, pagination
    """
    return _search(
        query=query,
        workspace=None,
        source=None,
        after=after,
        before=before,
        context_size=context_size,
        threshold=threshold,
        max_results=max_results,
        offset=offset,
    )


@mcp.tool()
def search_cli_history(
    query: str,
    after: str | None = None,
    before: str | None = None,
    context_size: int = 3,
    threshold: float = 0.2,
    max_results: int = 10,
    offset: int = 0,
) -> dict:
    """
    Search Kiro CLI conversation history only.

    Use this to find conversations from Kiro CLI sessions specifically.

    Args:
        query: Keywords or sentence describing what to find
        after: Filter to messages on/after this date (ISO 8601)
        before: Filter to messages before this date (ISO 8601)
        context_size: Messages before AND after each match (default: 3)
        threshold: Minimum similarity 0-1 (default: 0.2)
        max_results: Maximum results (default: 10)
        offset: Skip results for pagination (default: 0)

    Returns:
        Search results from CLI conversations only
    """
    return _search(
        query=query,
        workspace=None,
        source=Source.CLI,
        after=after,
        before=before,
        context_size=context_size,
        threshold=threshold,
        max_results=max_results,
        offset=offset,
    )


@mcp.tool()
def search_ide_history(
    query: str,
    after: str | None = None,
    before: str | None = None,
    context_size: int = 3,
    threshold: float = 0.2,
    max_results: int = 10,
    offset: int = 0,
) -> dict:
    """
    Search Kiro IDE conversation history only.

    Use this to find conversations from Kiro IDE sessions specifically.

    Args:
        query: Keywords or sentence describing what to find
        after: Filter to messages on/after this date (ISO 8601)
        before: Filter to messages before this date (ISO 8601)
        context_size: Messages before AND after each match (default: 3)
        threshold: Minimum similarity 0-1 (default: 0.2)
        max_results: Maximum results (default: 10)
        offset: Skip results for pagination (default: 0)

    Returns:
        Search results from IDE conversations only
    """
    return _search(
        query=query,
        workspace=None,
        source=Source.IDE,
        after=after,
        before=before,
        context_size=context_size,
        threshold=threshold,
        max_results=max_results,
        offset=offset,
    )


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
