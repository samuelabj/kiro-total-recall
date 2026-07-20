"""Unified loader combining CLI (v2 + v3) and IDE sources."""

from .cli_loader import list_cli_sessions, load_cli_session_messages
from .cli_v3_loader import list_cli_v3_sessions, load_cli_v3_session_messages
from .config import get_config
from .ide_loader import list_ide_sessions, load_ide_session_messages
from .ide_v3_loader import list_ide_v3_sessions, load_ide_v3_session_messages
from .models import IndexedMessage, SessionInfo, Source

# V3 CLI sessions use a 'v3-' prefix in their message UUIDs to distinguish them.
_V3_SESSION_IDS: set[str] = set()

# IDE v3 sessions use an 'idev3-' prefix in their message UUIDs.
_IDE_V3_SESSION_IDS: set[str] = set()


def list_all_sessions() -> list[SessionInfo]:
    """List all sessions from enabled sources, sorted by modified time."""
    global _V3_SESSION_IDS, _IDE_V3_SESSION_IDS
    config = get_config()
    sessions = []

    if config.cli.enabled:
        sessions.extend(list_cli_sessions())

        v3_sessions = list_cli_v3_sessions()
        _V3_SESSION_IDS = {s.session_id for s in v3_sessions}
        sessions.extend(v3_sessions)

    if config.ide.enabled:
        sessions.extend(list_ide_sessions())

        ide_v3_sessions = list_ide_v3_sessions()
        _IDE_V3_SESSION_IDS = {s.session_id for s in ide_v3_sessions}
        sessions.extend(ide_v3_sessions)

    return sorted(sessions, key=lambda s: s.timestamp_fallback, reverse=True)


def load_session_messages(session: SessionInfo) -> list[IndexedMessage]:
    """Load messages for a session based on its source."""
    if session.source == Source.CLI:
        if session.session_id in _V3_SESSION_IDS:
            return load_cli_v3_session_messages(session)
        return load_cli_session_messages(session)
    if session.session_id in _IDE_V3_SESSION_IDS:
        return load_ide_v3_session_messages(session)
    return load_ide_session_messages(session)


def load_messages_for_sessions(
    sessions: list[SessionInfo],
) -> list[IndexedMessage]:
    """Load messages for multiple sessions."""
    messages = []
    for session in sessions:
        messages.extend(load_session_messages(session))
    return messages
