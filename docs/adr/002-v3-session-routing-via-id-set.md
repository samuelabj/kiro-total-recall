# ADR-002: V3 Session Routing via ID Set

**Date:** 2026-07-20
**Status:** Accepted

## Context

Both CLI v2 and CLI v3 sessions produce `SessionInfo` objects with `source=Source.CLI`. When `load_session_messages()` is called, the unified loader needs to route to the correct loader implementation.

Options considered:
1. Add a new `Source.CLI_V3` enum value
2. Add a `format_version` field to `SessionInfo`
3. Track v3 session IDs in a module-level set populated during session listing

## Decision

Use a module-level `_V3_SESSION_IDS: set[str]` in `loader.py`, populated during `list_all_sessions()`, to route CLI sessions to the v3 loader.

## Rationale

- Adding `Source.CLI_V3` would break the existing MCP tool contract — `search_cli_history` filters on `Source.CLI` and users expect CLI results from both formats unified.
- A `format_version` field on `SessionInfo` adds a model concern that only matters for routing, not for search or display.
- The ID set is simple, fast (O(1) lookup), and self-contained within the loader module. It requires no changes to the public data models or MCP tool interfaces.

## Consequences

- `list_all_sessions()` must be called before `load_session_messages()` for v3 routing to work. This is already the natural order of operations (index build lists first, then loads).
- If sessions are loaded without a prior listing call (direct usage), v3 sessions would fall through to the v2 loader and return empty results. This is acceptable since the indexer always calls `list_all_sessions()` first.
- The set is rebuilt on every `list_all_sessions()` call, so it's always current.
