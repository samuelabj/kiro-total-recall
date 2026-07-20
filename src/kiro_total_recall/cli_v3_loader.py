"""Load conversations from Kiro CLI v3 file-based sessions.

V3 sessions are stored in ~/.kiro/sessions/cli/ as file triplets:
  - {session_id}.json  — session metadata (cwd, title, timestamps, state)
  - {session_id}.jsonl — message log (one JSON object per line)
  - {session_id}.lock  — process lock file (ignored)

Each .jsonl line has the structure:
  {"version": "v1", "kind": "<Kind>", "data": {...}}

Supported kinds:
  - Prompt: user messages (content[].kind == "text")
  - AssistantMessage: assistant responses (content[].kind in ["text", "toolUse"])
  - ToolResults: tool execution results (skipped for search indexing)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import get_config
from .models import IndexedMessage, SessionInfo, Source

logger = logging.getLogger(__name__)


def get_v3_sessions_dir() -> Path | None:
    """Get the v3 CLI sessions directory."""
    return get_config().cli.v3_sessions_dir


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _parse_unix_timestamp(ts: int | None) -> datetime | None:
    """Parse unix timestamp (seconds)."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts)
    except (ValueError, OSError):
        return None


def _extract_text_from_content(content: list) -> str:
    """Extract searchable text from v3 content array.

    Content items have structure: {"kind": "text"|"toolUse"|"toolResult", "data": ...}
    We only extract text content for search indexing.
    """
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        data = item.get("data")
        if kind == "text" and isinstance(data, str):
            parts.append(data)
    return "\n".join(parts)


def list_cli_v3_sessions() -> list[SessionInfo]:
    """List all v3 CLI sessions."""
    sessions_dir = get_v3_sessions_dir()
    if not sessions_dir or not sessions_dir.exists():
        return []

    sessions = []
    try:
        for json_file in sessions_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    meta = json.load(f)

                session_id = meta.get("session_id", json_file.stem)
                cwd = meta.get("cwd", "")
                created = _parse_iso_timestamp(meta.get("created_at"))
                updated = _parse_iso_timestamp(meta.get("updated_at"))

                sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        workspace=cwd,
                        created=created,
                        modified=updated,
                        source=Source.CLI,
                    )
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"Skipping v3 session {json_file.name}: {e}")

    except OSError as e:
        logger.warning(f"Error reading v3 CLI sessions directory: {e}")

    return sessions


def load_cli_v3_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages for a v3 CLI session."""
    sessions_dir = get_v3_sessions_dir()
    if not sessions_dir or not sessions_dir.exists():
        return []

    jsonl_path = sessions_dir / f"{session.session_id}.jsonl"
    if not jsonl_path.exists():
        return []

    messages = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                kind = entry.get("kind")
                data = entry.get("data", {})

                if not isinstance(data, dict):
                    continue

                # Map kind to role
                if kind == "Prompt":
                    role = "user"
                elif kind == "AssistantMessage":
                    role = "assistant"
                else:
                    # Skip ToolResults and other kinds
                    continue

                content = data.get("content", [])
                if not isinstance(content, list):
                    continue

                text = _extract_text_from_content(content)
                if not text.strip():
                    continue

                # Extract timestamp from meta if available
                meta = data.get("meta", {})
                timestamp = _parse_unix_timestamp(meta.get("timestamp"))
                if not timestamp:
                    timestamp = session.created or datetime.now()

                message_id = data.get("message_id", f"{session.session_id}-{line_num}")

                messages.append(
                    IndexedMessage(
                        uuid=f"v3-{session.session_id}-{message_id}",
                        session_id=session.session_id,
                        workspace=session.workspace,
                        timestamp=timestamp,
                        role=role,
                        searchable_text=text,
                        message_index=len(messages),
                        source=Source.CLI,
                    )
                )

    except OSError as e:
        logger.warning(f"Error loading v3 CLI session {session.session_id}: {e}")

    return messages
