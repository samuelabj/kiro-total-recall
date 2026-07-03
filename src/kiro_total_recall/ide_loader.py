"""Load conversations from Kiro IDE .chat files."""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import get_config
from .models import IndexedMessage, SessionInfo, Source

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: int | str | None) -> datetime | None:
    """Parse timestamp from various formats."""
    if ts is None:
        return None
    if isinstance(ts, int):
        return datetime.fromtimestamp(ts / 1000)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _extract_text_from_content(content: str | list | dict | None) -> str:
    """Extract searchable text from message content."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content:
            return content["text"]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" or "text" in item:
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def get_chat_files() -> list[Path]:
    """Get all IDE .chat files."""
    return get_config().ide.get_chat_files()


def list_ide_sessions() -> list[SessionInfo]:
    """List all IDE sessions from .chat/.json files."""
    sessions = []
    for chat_file in get_chat_files():
        try:
            # Skip the sessions index file
            if chat_file.name == "sessions.json":
                continue

            stat = chat_file.stat()
            # Use filename (without extension) as session ID
            session_id = chat_file.stem
            # Parent directory name as workspace hint
            workspace = chat_file.parent.name

            sessions.append(
                SessionInfo(
                    session_id=session_id,
                    workspace=workspace,
                    created=datetime.fromtimestamp(stat.st_ctime),
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    source=Source.IDE,
                )
            )
        except OSError as e:
            logger.debug(f"Could not stat {chat_file}: {e}")

    return sessions


def load_ide_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages from an IDE .chat file."""
    chat_files = get_chat_files()
    chat_file = next((f for f in chat_files if f.stem == session.session_id), None)

    if not chat_file or not chat_file.exists():
        return []

    messages = []
    try:
        with open(chat_file) as f:
            data = json.load(f)

        # IDE .chat files: {"chat": [...], "metadata": {...}, ...}
        msg_list = data.get("chat", [])

        # Fallback patterns
        if not msg_list:
            msg_list = data.get("messages", data.get("history", []))
        if not msg_list and "conversation" in data:
            msg_list = data["conversation"].get("messages", [])
        if not msg_list and isinstance(data, list):
            msg_list = data

        # Kiro server format includes workspaceDirectory at top level
        workspace = data.get("workspaceDirectory", session.workspace) if isinstance(data, dict) else session.workspace

        for idx, msg in enumerate(msg_list):
            if not isinstance(msg, dict):
                continue

            # Kiro server format: history entries wrap message in {"message": {...}}
            if "message" in msg and isinstance(msg["message"], dict):
                msg = msg["message"]

            role = msg.get("role", msg.get("type", ""))
            if role not in ("user", "assistant", "human", "ai"):
                continue

            role = "user" if role in ("user", "human") else "assistant"
            content = msg.get("content", msg.get("text", msg.get("message", "")))
            text = _extract_text_from_content(content)

            # Skip system prompts (identity, capabilities, etc.)
            if role == "user" and text.startswith("<identity>"):
                continue

            if not text.strip():
                continue

            timestamp = _parse_timestamp(msg.get("timestamp", msg.get("created_at")))
            if not timestamp:
                timestamp = session.modified or datetime.now()

            messages.append(
                IndexedMessage(
                    uuid=msg.get("id", msg.get("uuid", f"{session.session_id}-{idx}")),
                    session_id=session.session_id,
                    workspace=workspace,
                    timestamp=timestamp,
                    role=role,
                    searchable_text=text,
                    message_index=idx,
                    source=Source.IDE,
                )
            )

    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Error loading IDE session {session.session_id}: {e}")

    return messages
