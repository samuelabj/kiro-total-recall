"""MCP server for Kiro Total Recall."""

import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .indexer import get_index
from .models import IndexedMessage, Source
from .query import search_conversations

mcp = MCPServer("kiro-total-recall")


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

    Both user prompts AND assistant responses are indexed and searchable.
    Results include a "role" field ("user" or "assistant") indicating who said it.

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

    Both user prompts AND assistant responses are indexed and searchable.
    Results include a "role" field ("user" or "assistant") indicating who said it.

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

    Both user prompts AND assistant responses are indexed and searchable.
    Results include a "role" field ("user" or "assistant") indicating who said it.

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

    Both user prompts AND assistant responses are indexed and searchable.
    Results include a "role" field ("user" or "assistant") indicating who said it.

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


@mcp.tool()
def ingest_content(
    messages: list[dict],
    session_id: str | None = None,
    workspace: str | None = None,
) -> dict:
    """
    Manually index external content into Total Recall for future search.

    Use this to ingest conversations or content from external sources (e.g.,
    other AI tools, exported chat logs, documentation) so they become
    searchable alongside Kiro IDE/CLI history.

    Messages are persisted to disk and survive server restarts.

    Args:
        messages: List of message objects, each with:
            - content (required): The text content to index
            - role (optional): "user" or "assistant" (default: "user")
            - timestamp (optional): ISO 8601 datetime (default: now)
        session_id: Group messages under this session ID (default: auto-generated)
        workspace: Workspace/project path to associate with (default: current workspace)

    Returns:
        Summary of ingestion: count of messages added, session_id used

    Example:
        ingest_content(
            messages=[
                {"content": "How do I use the Bond API?", "role": "user", "timestamp": "2026-05-06T10:15:00"},
                {"content": "The Bond API uses PUT requests to trigger actions...", "role": "assistant", "timestamp": "2026-05-06T10:15:30"}
            ],
            session_id="antigravity-52456d3d",
            workspace="/home/sam"
        )
    """
    if not messages:
        return {"success": False, "error": "No messages provided"}

    # Resolve defaults
    resolved_session_id = session_id or f"ext-{uuid.uuid4().hex[:12]}"
    resolved_workspace = workspace or _get_current_workspace() or ""

    # Build IndexedMessage objects
    indexed_messages = []
    for i, msg in enumerate(messages):
        content = msg.get("content")
        if not content or not content.strip():
            continue

        role = msg.get("role", "user")
        ts_str = msg.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
        except (ValueError, TypeError):
            timestamp = datetime.now()

        msg_uuid = f"ext-{resolved_session_id}-{uuid.uuid4().hex[:8]}"

        indexed_messages.append(IndexedMessage(
            uuid=msg_uuid,
            session_id=resolved_session_id,
            workspace=resolved_workspace,
            timestamp=timestamp,
            role=role,
            searchable_text=content.strip(),
            message_index=i,
            source=Source.EXTERNAL,
        ))

    if not indexed_messages:
        return {"success": False, "error": "No valid messages with content"}

    # Ingest into the live index
    index = get_index()
    added = index.ingest_messages(indexed_messages)

    return {
        "success": True,
        "messages_ingested": added,
        "messages_submitted": len(indexed_messages),
        "session_id": resolved_session_id,
        "workspace": resolved_workspace,
    }


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
