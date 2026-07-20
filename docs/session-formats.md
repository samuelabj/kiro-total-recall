# Session Storage Formats

Kiro stores conversation history in different formats depending on the client (CLI vs IDE) and the version. This document describes each format in detail.

## CLI v2 — SQLite Database

The original CLI storage format uses a single SQLite database.

### Location

First existing path wins:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/kiro-cli/data.sqlite3` |
| Linux | `~/.local/share/kiro-cli/data.sqlite3` |
| Windows | `%LOCALAPPDATA%\Kiro-Cli\data.sqlite3` |
| Windows (alt) | `%APPDATA%\kiro-cli\data.sqlite3` |

### Schema

```sql
CREATE TABLE conversations_v2 (
    key TEXT NOT NULL,              -- workspace identifier (e.g. directory path)
    conversation_id TEXT NOT NULL,  -- UUID session identifier
    value TEXT NOT NULL,            -- JSON blob containing the conversation
    created_at INTEGER NOT NULL,    -- Unix timestamp in milliseconds
    updated_at INTEGER NOT NULL,    -- Unix timestamp in milliseconds
    PRIMARY KEY (key, conversation_id)
);
```

### Conversation JSON Structure (`value` column)

```json
{
  "history": [
    {
      "user": {
        "content": {"Prompt": {"prompt": "user message text"}},
        "timestamp": 1782098513
      },
      "assistant": {
        "content": [{"type": "text", "text": "assistant response"}],
        "timestamp": 1782098520
      }
    }
  ]
}
```

Each entry in `history` is a turn containing optional `user` and/or `assistant` keys.

### Content Extraction

User content may appear as:
- `{"Prompt": {"prompt": "..."}}`  — wrapped prompt
- `{"text": "..."}` — direct text
- `[{"type": "text", "text": "..."}]` — content array

### Notes

- The `--v3` flag was introduced in later versions and this table is now empty for users exclusively using v3 mode.
- The older `conversations` table (single `key`/`value` schema) is also present but typically unused.

---

## CLI v3 — File-Based Sessions

The v3 format (activated via `kiro-cli --v3`) uses a directory of file triplets. This is the "next generation" agent format.

### Location

```
~/.kiro/sessions/cli/
```

### File Structure

Each session produces three files:

```
~/.kiro/sessions/cli/
├── {session_id}.json     # Session metadata
├── {session_id}.jsonl    # Message log (append-only)
└── {session_id}.lock     # Process lock (runtime only)
```

### Metadata File (`.json`)

```json
{
  "session_id": "074ca7d2-f45c-42e8-82b1-d2b84e7a6d5b",
  "cwd": "C:\\Users\\work\\source\\repos\\talent_api",
  "created_at": "2026-06-22T03:21:47.344053500Z",
  "updated_at": "2026-06-22T03:22:03.220083300Z",
  "title": "list all references to liam@careerhub.com.au",
  "session_created_reason": "subagent",
  "session_state": {
    "version": "v1",
    "conversation_metadata": {
      "user_turn_metadatas": [
        {
          "loop_id": { "agent_id": { "name": "kiro_default", ... }, "rand": 1896664760 },
          "result": { "Ok": { "id": "...", "role": "assistant", "content": [...] } },
          "message_ids": ["...", "..."],
          "total_request_count": 2,
          "number_of_cycles": 1,
          "builtin_tool_uses": 1,
          "turn_duration": { "secs": 9, "nanos": 428188600 },
          "end_reason": "UserTurnEnd",
          "end_timestamp": "2026-06-22T03:22:03.217822300Z",
          "input_token_count": 0,
          "output_token_count": 0,
          "context_usage_percentage": 5.8244
        }
      ]
    }
  }
}
```

Key fields:
- `session_id` — UUID identifier
- `cwd` — working directory where the session was started (used as workspace)
- `created_at` / `updated_at` — ISO 8601 timestamps with nanosecond precision
- `title` — auto-generated from the first user prompt
- `session_created_reason` — `"subagent"` or `"user"` indicating how the session was initiated

### Message Log (`.jsonl`)

Each line is a JSON object with the structure:

```json
{"version": "v1", "kind": "<Kind>", "data": {...}}
```

#### Kind: `Prompt` (user message)

```json
{
  "version": "v1",
  "kind": "Prompt",
  "data": {
    "message_id": "a4bbb5c8-9728-48b7-b527-72b784dd93d1",
    "content": [
      {"kind": "text", "data": "list all references to liam@careerhub.com.au"}
    ],
    "meta": {
      "timestamp": 1782098513
    }
  }
}
```

#### Kind: `AssistantMessage` (assistant response)

```json
{
  "version": "v1",
  "kind": "AssistantMessage",
  "data": {
    "message_id": "3bf4342b-9f05-4e9d-a23c-edb6f762b2a6",
    "content": [
      {"kind": "text", "data": "No matches found for `liam@careerhub.com.au`..."},
      {"kind": "toolUse", "data": {"toolUseId": "tooluse_...", "name": "grep", "input": {...}}}
    ]
  }
}
```

Content items have a `kind` field:
- `"text"` — human-readable text (indexed for search)
- `"toolUse"` — tool invocation (not indexed)

#### Kind: `ToolResults` (tool execution output)

```json
{
  "version": "v1",
  "kind": "ToolResults",
  "data": {
    "message_id": "18dc2b9b-f2b0-4730-b5c6-9cf59e71a17e",
    "content": [
      {"kind": "toolResult", "data": {"toolUseId": "tooluse_...", "content": [...], "status": "success"}}
    ],
    "results": [...]
  }
}
```

Tool results are skipped during indexing — they contain raw tool output that isn't useful for semantic search.

### Lock File (`.lock`)

```json
{"pid": 70548, "started_at": "2026-06-22T03:21:47.342887900Z"}
```

Runtime lock indicating a process is actively writing to this session. Ignored by the loader.

### Notes

- Sessions with empty `.jsonl` files (0 bytes) are listed but produce no indexed messages. These are typically subagent sessions that were created as placeholders.
- The `meta.timestamp` field in Prompt messages is a Unix timestamp in seconds.
- AssistantMessage entries may lack a `meta` field; the loader falls back to the session `created_at` timestamp.

---

## IDE — Workspace Sessions

The Kiro IDE stores sessions under its globalStorage path in two formats.

### Location

```
{globalStorage}/kiro.kiroagent/workspace-sessions/{base64_workspace_path}/
```

Where `{globalStorage}` is:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Kiro/User/globalStorage` |
| Linux | `~/.config/Kiro/User/globalStorage` |
| Windows | `%APPDATA%\Kiro\User\globalStorage` |

The workspace path is encoded as URL-safe base64 with `_` replacing `=` padding.

### New Format (workspace-sessions/)

Each session is a JSON file: `{session_id}.json`

```json
{
  "history": [
    {
      "message": {
        "role": "user",
        "content": [{"type": "text", "text": "..."}]
      }
    },
    {
      "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": "..."}]
      }
    }
  ],
  "contextItems": [...],
  "ttsActive": false,
  "active": true,
  "isGatheringContext": false,
  "hasPendingIntentClarification": false,
  "config": {...},
  "title": "...",
  "sessionId": "36d88e89-85dc-4c0c-a403-8e854f373a9e",
  "defaultModelTitle": "..."
}
```

### Legacy Format (hash directories)

Older IDE sessions are stored in hash-named directories at the kiroagent root:

```
{globalStorage}/kiro.kiroagent/{md5_hash}/
```

Each directory contains execution files with structures like `input.data.messages` arrays and `actions[type=say]` entries.

### Notes

- The IDE also stores `.chat` files in some configurations (matched by glob patterns).
- The workspace path decoding allows matching sessions to specific projects.
- Both formats produce `Source.IDE` messages in the unified index.

---

## Summary Table

| Format | Client | Storage | Location | Status |
|--------|--------|---------|----------|--------|
| CLI v2 | `kiro-cli` (legacy) | SQLite | `data.sqlite3` (platform-specific) | Deprecated for v3 users |
| CLI v3 | `kiro-cli --v3` | JSON + JSONL files | `~/.kiro/sessions/cli/` | Active |
| IDE (new) | Kiro IDE | JSON files | `workspace-sessions/{b64}/` | Active |
| IDE (legacy) | Kiro IDE | Execution files | `{md5_hash}/` | Legacy |
