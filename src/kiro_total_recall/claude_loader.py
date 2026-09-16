"""Load conversations from Claude Code session transcripts.

Claude Code stores each session as a JSONL transcript at:
  ~/.claude/projects/<workspace-slug>/<session-id>.jsonl

Each line is a JSON object. Relevant entries for indexing:
  - type == "user": human turns (message.content is a string or a list of
    content blocks; tool-result turns are also "user" but carry no "text"
    block and are skipped)
  - type == "assistant": model turns (message.content is a list of blocks;
    only "text" blocks are extracted, tool_use/thinking blocks are skipped)

Sidechain entries (isSidechain: true, i.e. subagent transcripts) are skipped
entirely so subagent chatter doesn't pollute top-level conversation search.

Each line also carries an "entrypoint" field ("cli", "claude-vscode",
"claude-desktop") that identifies how the session was started. We map that
onto the existing Source.CLI / Source.IDE split so Claude Code messages
integrate with the existing scoped search tools alongside legacy Kiro
history.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import get_config
from .models import IndexedMessage, SessionInfo, Source

logger = logging.getLogger(__name__)

# Entrypoints that identify a terminal/CLI session; everything else
# (claude-vscode, claude-desktop, or missing) is treated as an IDE session.
_CLI_ENTRYPOINTS = {"cli"}

# Populated by list_claude_sessions(); avoids re-globbing per session lookup.
_SESSION_PATHS: dict[str, Path] = {}


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _source_for_entrypoint(entrypoint: str | None) -> Source:
    """Map a transcript entry's entrypoint to a Source."""
    return Source.CLI if entrypoint in _CLI_ENTRYPOINTS else Source.IDE


def _extract_text(content) -> str:
    """Extract searchable text from a message's content field.

    Content is either a plain string (simple user turns) or a list of
    blocks (assistant turns, and user turns with attachments/tool results).
    Only "text" blocks are indexed.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in parts if part)


def list_claude_sessions() -> list[SessionInfo]:
    """List all Claude Code session transcripts.

    Workspace and precise source are resolved per-message during loading;
    listing only needs a cheap stat() so the fingerprint check that runs on
    every search stays fast even with a large transcript history.
    """
    global _SESSION_PATHS
    config = get_config()
    if not config.claude.enabled:
        return []

    _SESSION_PATHS = {}
    sessions = []
    for path in config.claude.get_transcript_files():
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError as e:
            logger.debug(f"Skipping Claude transcript {path.name}: {e}")
            continue

        session_id = path.stem
        _SESSION_PATHS[session_id] = path
        sessions.append(
            SessionInfo(
                session_id=session_id,
                workspace="",
                modified=modified,
                source=Source.IDE,
            )
        )

    return sessions


def load_claude_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages for a Claude Code session."""
    path = _SESSION_PATHS.get(session.session_id)
    if not path or not path.exists():
        return []

    messages = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("isSidechain") or entry.get("type") not in ("user", "assistant"):
                    continue

                message = entry.get("message")
                if not isinstance(message, dict):
                    continue

                role = message.get("role")
                if role not in ("user", "assistant"):
                    continue

                text = _extract_text(message.get("content"))
                if not text.strip():
                    continue

                timestamp = (
                    _parse_iso_timestamp(entry.get("timestamp"))
                    or session.modified
                    or datetime.now()
                )
                message_id = entry.get("uuid", len(messages))

                messages.append(
                    IndexedMessage(
                        uuid=f"claude-{session.session_id}-{message_id}",
                        session_id=session.session_id,
                        workspace=entry.get("cwd", ""),
                        timestamp=timestamp,
                        role=role,
                        searchable_text=text,
                        message_index=len(messages),
                        source=_source_for_entrypoint(entry.get("entrypoint")),
                    )
                )

    except PermissionError:
        logger.debug(
            f"Permission denied reading Claude session {session.session_id} "
            f"(Claude Code may have it open)"
        )
    except OSError as e:
        logger.warning(f"Error loading Claude session {session.session_id}: {e}")

    return messages
