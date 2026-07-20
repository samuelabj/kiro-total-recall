# ADR-003: Skip Tool Results in Search Indexing

**Date:** 2026-07-20
**Status:** Accepted

## Context

The v3 `.jsonl` message log contains three kinds of entries:
- `Prompt` — user messages
- `AssistantMessage` — assistant responses (text + tool use invocations)
- `ToolResults` — raw output from tool executions (grep results, file contents, API responses)

We needed to decide which kinds to index for semantic search.

## Decision

Index only `Prompt` (as role "user") and text content from `AssistantMessage` (as role "assistant"). Skip `ToolResults` entirely. Within `AssistantMessage`, only extract `content[].kind == "text"` items — skip `toolUse` entries.

## Rationale

- Tool results are verbose, noisy, and typically contain raw data (file listings, grep output, JSON API responses) that doesn't benefit from semantic search.
- Indexing tool results would dramatically increase embedding count and memory usage without proportional search quality improvement.
- The assistant's text responses already summarize tool results in natural language, which embeds and searches much better.
- Tool use invocations (function names + parameters) are structural, not semantic — they don't help a user searching for "how did we fix the auth bug."

## Consequences

- Users cannot search for specific tool output (e.g., finding a session where a particular file path appeared in grep results). They can search for the assistant's summary instead.
- This reduces index size significantly — in practice, `ToolResults` lines can be 10-100x larger than text messages.
- If a use case emerges for searching tool results, a separate specialized index could be added without changing the core search.
