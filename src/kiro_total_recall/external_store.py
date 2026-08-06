"""Persistent storage for externally-ingested messages."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .config import get_config
from .models import IndexedMessage, SessionInfo, Source

logger = logging.getLogger(__name__)


def _get_store_path() -> Path:
    """Get the external messages store file path."""
    config = get_config()
    return config.embedding.cache_path / "external_messages.json"


def _get_lock_path() -> Path:
    """Get the lock file path for external store."""
    config = get_config()
    return config.embedding.cache_path / "external_messages.lock"


def _load_store() -> list[dict[str, Any]]:
    """Load the external messages store."""
    store_path = _get_store_path()
    if not store_path.exists():
        return []
    try:
        with open(store_path) as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load external store: {e}")
        return []


def _save_store(messages: list[dict[str, Any]]) -> None:
    """Save the external messages store atomically."""
    store_path = _get_store_path()
    lock_path = _get_lock_path()
    store_path.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(lock_path):
        temp_file = store_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as f:
                json.dump(messages, f, default=str)
            temp_file.replace(store_path)
        except OSError:
            temp_file.unlink(missing_ok=True)
            raise


def save_messages(new_messages: list[IndexedMessage]) -> int:
    """Persist new external messages to the store. Returns count saved."""
    if not new_messages:
        return 0

    existing = _load_store()
    existing_uuids = {m["uuid"] for m in existing}

    added = 0
    for msg in new_messages:
        if msg.uuid in existing_uuids:
            continue
        existing.append({
            "uuid": msg.uuid,
            "session_id": msg.session_id,
            "workspace": msg.workspace,
            "timestamp": msg.timestamp.isoformat(),
            "role": msg.role,
            "searchable_text": msg.searchable_text,
            "message_index": msg.message_index,
            "source": msg.source.value,
        })
        added += 1

    if added > 0:
        _save_store(existing)

    return added


def load_external_messages() -> list[IndexedMessage]:
    """Load all externally-ingested messages from the store."""
    raw = _load_store()
    messages = []
    for entry in raw:
        try:
            messages.append(IndexedMessage(
                uuid=entry["uuid"],
                session_id=entry["session_id"],
                workspace=entry["workspace"],
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                role=entry["role"],
                searchable_text=entry["searchable_text"],
                message_index=entry.get("message_index", 0),
                source=Source.EXTERNAL,
            ))
        except (KeyError, ValueError) as e:
            logger.warning(f"Skipping malformed external message: {e}")
    return messages


def list_external_sessions() -> list[SessionInfo]:
    """List sessions from externally-ingested messages."""
    messages = load_external_messages()
    if not messages:
        return []

    # Group by session_id
    sessions: dict[str, list[IndexedMessage]] = {}
    for msg in messages:
        sessions.setdefault(msg.session_id, []).append(msg)

    result = []
    for session_id, msgs in sessions.items():
        timestamps = [m.timestamp for m in msgs]
        result.append(SessionInfo(
            session_id=session_id,
            workspace=msgs[0].workspace,
            message_count=len(msgs),
            created=min(timestamps),
            modified=max(timestamps),
            source=Source.EXTERNAL,
        ))

    return result


def get_external_message_count() -> int:
    """Get count of externally-stored messages without loading all."""
    store_path = _get_store_path()
    if not store_path.exists():
        return 0
    try:
        with open(store_path) as f:
            data = json.load(f)
            return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError):
        return 0
