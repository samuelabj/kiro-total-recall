"""Load conversations from Kiro IDE session files.

Supports two storage formats:
1. New format (workspace-sessions/): Base64-encoded workspace paths with .json session files
   containing a 'history' array of {message: {role, content}} entries.
2. Legacy format (hash dirs): Execution files with input.data.messages and actions[type=say].
"""

import base64
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
        # Millisecond epoch timestamps
        if ts > 1_000_000_000_000:
            return datetime.fromtimestamp(ts / 1000)
        return datetime.fromtimestamp(ts)
    if isinstance(ts, str):
        # Try parsing as int string first (Kiro stores "1772073534762" as string)
        try:
            int_val = int(ts)
            return _parse_timestamp(int_val)
        except ValueError:
            pass
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


def _decode_workspace_dir_name(name: str) -> str | None:
    """Decode a base64url-encoded workspace directory name."""
    try:
        # Kiro uses URL-safe base64 with _ as padding (instead of =)
        padded = name.replace("_", "=")
        return base64.urlsafe_b64decode(padded).decode("utf-8")
    except Exception:
        return None


def _get_workspace_sessions_dir() -> Path | None:
    """Get the workspace-sessions directory if it exists."""
    config = get_config()
    for pattern in config.ide.patterns:
        # Extract the kiro.kiroagent base path from the pattern
        expanded = Path(pattern).expanduser()
        parts = expanded.parts
        # Find the kiro.kiroagent part
        for i, part in enumerate(parts):
            if part == "kiro.kiroagent":
                base = Path(*parts[: i + 1])
                ws_sessions = base / "workspace-sessions"
                if ws_sessions.exists():
                    return ws_sessions
                break
    return None


def _get_legacy_session_dirs() -> list[tuple[Path, str]]:
    """Get legacy hash-named session directories.

    Returns list of (session_dir, workspace_hash) tuples.
    """
    config = get_config()
    for pattern in config.ide.patterns:
        expanded = Path(pattern).expanduser()
        parts = expanded.parts
        for i, part in enumerate(parts):
            if part == "kiro.kiroagent":
                base = Path(*parts[: i + 1])
                if base.exists():
                    results = []
                    for ws_dir in base.iterdir():
                        if not ws_dir.is_dir():
                            continue
                        if ws_dir.name.startswith(".") or ws_dir.name == "workspace-sessions":
                            continue
                        for session_dir in ws_dir.iterdir():
                            if session_dir.is_dir():
                                results.append((session_dir, ws_dir.name))
                    return results
                break
    return []


# ============================================================
# New format: workspace-sessions/<base64-path>/<sessionId>.json
# ============================================================


def _list_workspace_sessions() -> list[SessionInfo]:
    """List sessions from the new workspace-sessions format."""
    ws_dir = _get_workspace_sessions_dir()
    if not ws_dir:
        return []

    sessions = []
    for workspace_dir in ws_dir.iterdir():
        if not workspace_dir.is_dir():
            continue

        workspace_path = _decode_workspace_dir_name(workspace_dir.name)
        if not workspace_path:
            continue

        # Read sessions.json for metadata
        sessions_file = workspace_dir / "sessions.json"
        session_metadata: dict[str, dict] = {}
        if sessions_file.exists():
            try:
                with open(sessions_file, encoding="utf-8") as f:
                    meta_list = json.load(f)
                if isinstance(meta_list, list):
                    for m in meta_list:
                        sid = m.get("sessionId", "")
                        if sid:
                            session_metadata[sid] = m
            except (json.JSONDecodeError, OSError):
                pass

        # Each .json file (except sessions.json) is a session
        for session_file in workspace_dir.iterdir():
            if not session_file.is_file() or session_file.suffix != ".json":
                continue
            if session_file.name == "sessions.json":
                continue

            session_id = session_file.stem
            try:
                stat = session_file.stat()
                meta = session_metadata.get(session_id, {})
                created = _parse_timestamp(meta.get("dateCreated"))
                if not created:
                    created = datetime.fromtimestamp(stat.st_ctime)

                sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        workspace=workspace_path,
                        created=created,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        source=Source.IDE,
                    )
                )
            except OSError as e:
                logger.debug(f"Could not stat {session_file}: {e}")

    return sessions


def _load_workspace_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages from a workspace-sessions .json file."""
    ws_dir = _get_workspace_sessions_dir()
    if not ws_dir:
        return []

    # Find the session file by searching workspace dirs
    session_file = None
    for workspace_dir in ws_dir.iterdir():
        if not workspace_dir.is_dir():
            continue
        candidate = workspace_dir / f"{session.session_id}.json"
        if candidate.exists():
            session_file = candidate
            break

    if not session_file:
        return []

    messages = []
    try:
        with open(session_file, encoding="utf-8") as f:
            data = json.load(f)

        workspace = data.get("workspaceDirectory", session.workspace)
        history = data.get("history", [])

        for idx, entry in enumerate(history):
            if not isinstance(entry, dict):
                continue

            msg = entry.get("message", entry)
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            if role not in ("user", "assistant", "human", "ai"):
                continue
            role = "user" if role in ("user", "human") else "assistant"

            content = msg.get("content", "")
            text = _extract_text_from_content(content)

            # Skip system prompts and steering content
            if role == "user" and (
                text.startswith("<identity>")
                or text.startswith("<") 
                or "## Included Rules" in text[:200]
            ):
                continue

            if not text.strip():
                continue

            # Skip very short assistant responses like "On it." or "understood"
            # These are acknowledgments, not searchable content
            if role == "assistant" and len(text.strip()) < 10:
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
        logger.warning(f"Error loading workspace session {session.session_id}: {e}")

    return messages


# ============================================================
# Legacy format: <workspace-hash>/<session-hash>/<execution-files>
# ============================================================


def _list_legacy_sessions() -> list[SessionInfo]:
    """List sessions from legacy hash-named execution files.

    In the legacy format, each execution file belongs to a chat session
    (identified by chatSessionId). We group executions by chatSessionId.
    """
    session_dirs = _get_legacy_session_dirs()
    if not session_dirs:
        return []

    # Map chatSessionId -> SessionInfo
    seen_sessions: dict[str, SessionInfo] = {}

    for session_dir, workspace_hash in session_dirs:
        for exec_file in session_dir.iterdir():
            if not exec_file.is_file() or exec_file.stat().st_size < 100:
                continue

            try:
                with open(exec_file, encoding="utf-8", errors="ignore") as f:
                    # Only read enough to get the chatSessionId and startTime
                    raw = f.read(2000)

                # Quick extraction without full JSON parse
                import re
                chat_id_match = re.search(r'"chatSessionId"\s*:\s*"([^"]+)"', raw)
                start_match = re.search(r'"startTime"\s*:\s*(\d+)', raw)

                if not chat_id_match:
                    continue

                chat_session_id = chat_id_match.group(1)
                start_time = int(start_match.group(1)) if start_match else None

                if chat_session_id not in seen_sessions:
                    created = _parse_timestamp(start_time) if start_time else None
                    stat = exec_file.stat()
                    seen_sessions[chat_session_id] = SessionInfo(
                        session_id=chat_session_id,
                        workspace=workspace_hash,
                        created=created or datetime.fromtimestamp(stat.st_ctime),
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        source=Source.IDE,
                    )
                else:
                    # Update modified time if this file is newer
                    stat = exec_file.stat()
                    existing = seen_sessions[chat_session_id]
                    file_mtime = datetime.fromtimestamp(stat.st_mtime)
                    if existing.modified and file_mtime > existing.modified:
                        seen_sessions[chat_session_id] = SessionInfo(
                            session_id=existing.session_id,
                            workspace=existing.workspace,
                            created=existing.created,
                            modified=file_mtime,
                            source=Source.IDE,
                        )

            except (OSError, ValueError):
                continue

    return list(seen_sessions.values())


def _load_legacy_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages from legacy execution files for a given chatSessionId.

    Each execution file contains:
    - input.data.messages: user messages sent to the agent (the latest user message
      is the last one; earlier entries are history context)
    - actions[actionType=say].output.message: assistant responses
    """
    session_dirs = _get_legacy_session_dirs()
    if not session_dirs:
        return []

    # Find all execution files belonging to this chatSessionId
    exec_files: list[tuple[Path, int]] = []  # (path, startTime)
    for session_dir, workspace_hash in session_dirs:
        for exec_file in session_dir.iterdir():
            if not exec_file.is_file() or exec_file.stat().st_size < 100:
                continue
            try:
                with open(exec_file, encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                if data.get("chatSessionId") == session.session_id:
                    start_time = data.get("startTime", 0)
                    exec_files.append((exec_file, start_time))
            except (json.JSONDecodeError, OSError):
                continue

    if not exec_files:
        return []

    # Sort executions by startTime
    exec_files.sort(key=lambda x: x[1])

    messages = []
    msg_idx = 0

    for exec_path, start_time in exec_files:
        try:
            with open(exec_path, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            execution_timestamp = _parse_timestamp(start_time) or session.modified or datetime.now()

            # Extract the user message (last entry in input.data.messages)
            input_msgs = data.get("input", {}).get("data", {}).get("messages", [])
            if input_msgs:
                # The last user message is the actual prompt for this execution
                last_user = None
                for m in reversed(input_msgs):
                    if m.get("role") == "user":
                        last_user = m
                        break

                if last_user:
                    content = last_user.get("content", "")
                    text = _extract_text_from_content(content)

                    # Skip system prompts
                    if text and not text.startswith("<identity>") and not text.startswith("<"):
                        if "## Included Rules" not in text[:200] and text.strip():
                            messages.append(
                                IndexedMessage(
                                    uuid=f"{session.session_id}-user-{msg_idx}",
                                    session_id=session.session_id,
                                    workspace=session.workspace,
                                    timestamp=execution_timestamp,
                                    role="user",
                                    searchable_text=text,
                                    message_index=msg_idx,
                                    source=Source.IDE,
                                )
                            )
                            msg_idx += 1

            # Extract assistant responses from actions[type=say]
            actions = data.get("actions", [])
            for action in actions:
                if action.get("actionType", action.get("type")) != "say":
                    continue

                output = action.get("output", {})
                text = output.get("message", "") if isinstance(output, dict) else ""
                if not text or not text.strip():
                    continue

                # Skip very short acknowledgments
                if len(text.strip()) < 10:
                    continue

                action_time = _parse_timestamp(action.get("emittedAt"))

                messages.append(
                    IndexedMessage(
                        uuid=action.get("actionId", f"{session.session_id}-say-{msg_idx}"),
                        session_id=session.session_id,
                        workspace=session.workspace,
                        timestamp=action_time or execution_timestamp,
                        role="assistant",
                        searchable_text=text,
                        message_index=msg_idx,
                        source=Source.IDE,
                    )
                )
                msg_idx += 1

        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Error reading execution file {exec_path}: {e}")
            continue

    return messages


# ============================================================
# Public API (used by the rest of the system)
# ============================================================


def get_chat_files() -> list[Path]:
    """Get all IDE chat/session files.

    Returns files from both new and legacy formats.
    For the new format, returns the .json session files.
    For the legacy format, this returns an empty list (legacy uses
    a different loading path).
    """
    ws_dir = _get_workspace_sessions_dir()
    if ws_dir:
        files = []
        for workspace_dir in ws_dir.iterdir():
            if not workspace_dir.is_dir():
                continue
            for f in workspace_dir.iterdir():
                if f.is_file() and f.suffix == ".json" and f.name != "sessions.json":
                    files.append(f)
        return sorted(files)

    # Fallback to original glob-based discovery
    return get_config().ide.get_chat_files()


def list_ide_sessions() -> list[SessionInfo]:
    """List all IDE sessions from both new and legacy formats."""
    sessions = []

    # New format: workspace-sessions/
    new_sessions = _list_workspace_sessions()
    sessions.extend(new_sessions)
    if new_sessions:
        logger.info(f"Found {len(new_sessions)} sessions in workspace-sessions format")

    # Legacy format: hash-named dirs
    legacy_sessions = _list_legacy_sessions()
    sessions.extend(legacy_sessions)
    if legacy_sessions:
        logger.info(f"Found {len(legacy_sessions)} sessions in legacy format")

    # If neither found anything, try original .chat file discovery
    if not sessions:
        for chat_file in get_config().ide.get_chat_files():
            try:
                if chat_file.name == "sessions.json":
                    continue
                stat = chat_file.stat()
                session_id = chat_file.stem
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
    """Load messages from an IDE session (dispatches to correct format)."""
    # Try workspace-sessions format first
    ws_dir = _get_workspace_sessions_dir()
    if ws_dir:
        # Check if this session exists in workspace-sessions
        for workspace_dir in ws_dir.iterdir():
            if not workspace_dir.is_dir():
                continue
            candidate = workspace_dir / f"{session.session_id}.json"
            if candidate.exists():
                return _load_workspace_session_messages(session)

    # Check if this looks like a legacy session (workspace is a hash)
    if len(session.workspace) == 32 and all(c in "0123456789abcdef" for c in session.workspace):
        return _load_legacy_session_messages(session)

    # Fallback: try workspace-sessions anyway, then legacy
    messages = _load_workspace_session_messages(session)
    if messages:
        return messages

    messages = _load_legacy_session_messages(session)
    if messages:
        return messages

    # Final fallback: try original .chat file format
    return _load_chat_file_messages(session)


def _load_chat_file_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages from an original .chat file (fallback)."""
    chat_files = get_config().ide.get_chat_files()
    chat_file = next((f for f in chat_files if f.stem == session.session_id), None)

    if not chat_file or not chat_file.exists():
        return []

    messages = []
    try:
        with open(chat_file, encoding="utf-8") as f:
            data = json.load(f)

        msg_list = data.get("chat", [])
        if not msg_list:
            msg_list = data.get("messages", data.get("history", []))
        if not msg_list and "conversation" in data:
            msg_list = data["conversation"].get("messages", [])
        if not msg_list and isinstance(data, list):
            msg_list = data

        workspace = data.get("workspaceDirectory", session.workspace) if isinstance(data, dict) else session.workspace

        for idx, msg in enumerate(msg_list):
            if not isinstance(msg, dict):
                continue

            if "message" in msg and isinstance(msg["message"], dict):
                msg = msg["message"]

            role = msg.get("role", msg.get("type", ""))
            if role not in ("user", "assistant", "human", "ai"):
                continue

            role = "user" if role in ("user", "human") else "assistant"
            content = msg.get("content", msg.get("text", msg.get("message", "")))
            text = _extract_text_from_content(content)

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
        logger.warning(f"Error loading chat file session {session.session_id}: {e}")

    return messages
