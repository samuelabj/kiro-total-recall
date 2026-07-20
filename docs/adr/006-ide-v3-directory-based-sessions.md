# ADR-006: IDE v3 Directory-Based Session Loader

**Date:** 2026-07-20
**Status:** Accepted

## Context

Kiro IDE 1.0 migrated session storage from the `workspace-sessions/` JSON format to a new directory-based format at `~/.kiro/sessions/{workspaceHash}/{sessionId}/`. Each session is a directory containing `session.json` (metadata) and `messages.jsonl` (conversation log).

Initially we believed these files were exclusively locked by the Kiro process (all appeared as 4096-byte entries that threw `PermissionError`). Investigation revealed that the 4096-byte entries were actually directory entries reported by Windows, and the `PermissionError` was caused by attempting to `open()` a directory as a file. The actual files inside the directories are readable while Kiro is running.

## Decision

Create a separate `ide_v3_loader.py` module that scans `~/.kiro/sessions/` workspace hash directories, reads `session.json` for metadata, and parses `messages.jsonl` for conversation content. Use the same routing pattern as the CLI v3 loader (module-level `_IDE_V3_SESSION_IDS` set).

## Rationale

- The format is structurally different from the pre-1.0 workspace-sessions JSON (directory per session vs single JSON file per session, JSONL vs embedded history array).
- Keeping it separate follows the established pattern (one loader per format) and avoids complicating the existing `ide_loader.py`.
- The `messages.jsonl` payload schema (`{type, content}`) is simpler than the CLI v3 format (`{kind, data.content[].kind}`) so it warranted its own parser rather than forcing a shared abstraction.

## Consequences

- Both IDE loaders run in parallel — pre-1.0 sessions from workspace-sessions and 1.0+ sessions from the new directories are all indexed.
- The `_global/` and `cli/` subdirectories are explicitly skipped (CLI is handled by `cli_v3_loader.py`).
- `PermissionError` is caught gracefully in case Kiro does hold locks on specific session files during active writes.
- The workspace hash cannot currently be reversed to a directory path without reading `session.json`'s `workspacePaths` field.
