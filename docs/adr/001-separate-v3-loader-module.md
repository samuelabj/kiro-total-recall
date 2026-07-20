# ADR-001: Separate V3 Loader Module

**Date:** 2026-07-20
**Status:** Accepted

## Context

The `kiro-cli --v3` flag introduces a completely different storage format for conversations. The original CLI loader (`cli_loader.py`) reads from a SQLite database with the `conversations_v2` table. The v3 format uses a directory of `.json` metadata files and `.jsonl` message logs.

We needed to decide whether to extend the existing `cli_loader.py` to handle both formats or create a separate module.

## Decision

Create a new `cli_v3_loader.py` module with its own `list_cli_v3_sessions()` and `load_cli_v3_session_messages()` functions.

## Rationale

- The two formats share no structural similarity — SQLite vs file-system, single JSON blob vs append-only JSONL, different content schemas.
- Mixing both in one module would increase complexity and make each format harder to maintain independently.
- A separate module follows the existing pattern (cli_loader, ide_loader) and keeps each loader focused.
- The unified `loader.py` already acts as the integration point, making it trivial to add new sources.

## Consequences

- A small routing mechanism (`_V3_SESSION_IDS` set) is needed in `loader.py` to distinguish v3 sessions from v2 sessions since both use `Source.CLI`.
- If a future v4 format appears, the same pattern can be followed without touching existing loaders.
