"""Load conversations from Kiro IDE v3 session directories.

IDE v3 sessions are stored in ~/.kiro/sessions/{workspaceHash}/{sessionId}/
as directory structures:
  - session.json    — session metadata (id, title, workspacePaths, timestamps)
  - messages.jsonl  — message log (one JSON object per line)
  - publish.cursor  — byte offset cursor (ignored)
  - snapshots/      — optional snapshot directory (ignored)

Each .jsonl line has the structure:
  {"id": "...", "timestamp": "ISO8601", "payload": {"type": "<type>", ...}}

Supported payload types for indexing:
  - user: user messages (payload.content is the text)
  - assistant: assistant responses (payload.content is the text,
               payload.operationType == "Say")

Skipped payload types:
  - tool_call, tool_result: tool invocations and outputs
  - turn_start, turn_end: turn boundaries
  - session_metadata: context usage metrics
  - steering_inclusion: steering document references
  - session_start: session initialization (contains system prompt)
  - session_event: session lifecycle events
  - usage_summary: token usage summaries
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import get_config
from .models import IndexedMessage, SessionInfo, Source

logger = logging.getLogger(__name__)

# Directories to skip when scanning ~/.kiro/sessions/
_SKIP_DIRS = {"cli", "_global"}


def _get_ide_v3_sessions_base() -> Path | None:
    """Get the base IDE v3 sessions directory (~/.kiro/sessions)."""
    config = get_config()
    for path_str in config.ide.v3_session_dirs:
        expanded = Path(path_str).expanduser()
        if expanded.exists() and expanded.is_dir():
            return expanded
    return None


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def list_ide_v3_sessions() -> list[SessionInfo]:
    """List all IDE v3 sessions from ~/.kiro/sessions/{workspaceHash}/."""
    base_dir = _get_ide_v3_sessions_base()
    if not base_dir:
        return []

    sessions = []

    try:
        for ws_dir in base_dir.iterdir():
            if not ws_dir.is_dir() or ws_dir.name in _SKIP_DIRS:
                continue

            try:
                for session_dir in ws_dir.iterdir():
                    if not session_dir.is_dir():
                        continue

                    session_json = session_dir / "session.json"
                    if not session_json.exists():
                        continue

                    try:
                        with open(session_json, encoding="utf-8") as f:
                            meta = json.load(f)

                        session_id = meta.get("id", session_dir.name)
                        workspace_paths = meta.get("workspacePaths", [])
                        workspace = workspace_paths[0] if workspace_paths else ""
                        created = _parse_iso_timestamp(meta.get("createdAt"))
                        modified = _parse_iso_timestamp(meta.get("lastModifiedAt"))

                        sessions.append(
                            SessionInfo(
                                session_id=session_id,
                                workspace=workspace,
                                created=created,
                                modified=modified,
                                source=Source.IDE,
                            )
                        )
                    except (json.JSONDecodeError, OSError) as e:
                        logger.debug(
                            f"Skipping IDE v3 session {session_dir.name}: {e}"
                        )

            except OSError as e:
                logger.debug(f"Error reading workspace dir {ws_dir.name}: {e}")

    except OSError as e:
        logger.warning(f"Error reading IDE v3 sessions directory: {e}")

    return sessions


def load_ide_v3_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages for an IDE v3 session."""
    base_dir = _get_ide_v3_sessions_base()
    if not base_dir:
        return []

    # Find the session directory by scanning workspace hash dirs
    session_dir = _find_session_dir(base_dir, session.session_id)
    if not session_dir:
        return []

    jsonl_path = session_dir / "messages.jsonl"
    if not jsonl_path.exists():
        return []

    messages = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = entry.get("payload")
                if not isinstance(payload, dict):
                    continue

                msg_type = payload.get("type")

                # Only index user and assistant messages
                if msg_type == "user":
                    role = "user"
                    text = payload.get("content", "")
                elif msg_type == "assistant":
                    role = "assistant"
                    text = payload.get("content", "")
                else:
                    continue

                # Skip empty messages
                if not isinstance(text, str) or not text.strip():
                    continue

                # Parse timestamp
                timestamp = _parse_iso_timestamp(entry.get("timestamp"))
                if not timestamp:
                    timestamp = session.created or datetime.now()

                message_id = entry.get("id", f"{session.session_id}-{len(messages)}")

                messages.append(
                    IndexedMessage(
                        uuid=f"idev3-{session.session_id}-{message_id}",
                        session_id=session.session_id,
                        workspace=session.workspace,
                        timestamp=timestamp,
                        role=role,
                        searchable_text=text,
                        message_index=len(messages),
                        source=Source.IDE,
                    )
                )

    except PermissionError:
        logger.debug(
            f"Permission denied reading IDE v3 session {session.session_id} "
            f"(Kiro IDE may be running)"
        )
    except OSError as e:
        logger.warning(f"Error loading IDE v3 session {session.session_id}: {e}")

    return messages


def _find_session_dir(base_dir: Path, session_id: str) -> Path | None:
    """Find the session directory by scanning workspace hash directories."""
    try:
        for ws_dir in base_dir.iterdir():
            if not ws_dir.is_dir() or ws_dir.name in _SKIP_DIRS:
                continue

            session_dir = ws_dir / session_id
            if session_dir.is_dir():
                return session_dir

    except OSError:
        pass

    return None
