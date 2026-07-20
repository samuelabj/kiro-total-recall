# ADR-005: Use CWD as Workspace Identifier for V3 Sessions

**Date:** 2026-07-20
**Status:** Accepted

## Context

The `search_project_history` tool filters results by workspace — it only returns messages from sessions related to the current project. Each `SessionInfo` and `IndexedMessage` has a `workspace` field used for this filtering (prefix match).

The v3 session metadata provides a `cwd` field — the working directory where `kiro-cli --v3` was launched. The v2 format uses a `key` column in the database which is also typically a directory path.

## Decision

Use the v3 session's `cwd` field directly as the `workspace` value.

## Rationale

- `cwd` accurately represents what project the user was working in when they started the session.
- It matches the v2 convention where workspace = directory path.
- The search uses prefix matching (`workspace.startswith(filter_value)`), so sessions started in subdirectories of a project root are still matched.
- No transformation or normalization needed — the path is stored as-is from the session metadata.

## Consequences

- Sessions started from a parent directory (e.g., `C:\Users\work`) will match any project-scoped search beneath that path. This is intentional — those are cross-project sessions.
- Path case sensitivity may differ between operating systems. On Windows (case-insensitive FS), `C:\Users\Work` and `C:\Users\work` should match but currently use exact string prefix comparison. This is a known limitation that could be addressed if it causes issues.
