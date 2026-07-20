# Architecture

Kiro Total Recall is an MCP (Model Context Protocol) server that provides semantic search across Kiro CLI and IDE conversation history. It runs as a background process alongside Kiro, indexing past conversations so they can be recalled contextually during new sessions.

## System Overview

```
┌─────────────────────────────────────────────────────┐
│  Kiro IDE / CLI (MCP Client)                        │
│    calls: search_project_history                    │
│           search_global_history                     │
│           search_cli_history                        │
│           search_ide_history                        │
└──────────────────────┬──────────────────────────────┘
                       │ MCP (stdio)
┌──────────────────────▼──────────────────────────────┐
│  server.py (FastMCP)                                │
│    - Exposes 4 search tools                         │
│    - Preloads index in daemon thread at startup     │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  query.py                                           │
│    - Applies filters (workspace, source, dates)     │
│    - Deduplicates overlapping context windows       │
│    - Paginates results                              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  indexer.py (ConversationIndex)                     │
│    - Loads all sessions via loader.py               │
│    - Computes sentence-transformer embeddings       │
│    - Caches embeddings to disk (pickle)             │
│    - Performs cosine similarity search              │
│    - Memory-limited session selection               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  loader.py (Unified Loader)                         │
│    - Merges sessions from all sources               │
│    - Routes message loading to correct loader       │
│    - Sorts sessions by recency                      │
├─────────────┬─────────────────┬─────────────────────┤
│ cli_loader  │ cli_v3_loader   │ ide_loader          │
│ (SQLite v2) │ (file-based v3) │ (JSON sessions)     │
└─────────────┴─────────────────┴─────────────────────┘
```

## Module Responsibilities

| Module | Role |
|--------|------|
| `server.py` | MCP server entry point. Defines tools, handles preloading. |
| `query.py` | Search orchestration: filtering, deduplication, pagination. |
| `indexer.py` | Embedding computation, caching, similarity search. Memory management. |
| `loader.py` | Unified session listing and message loading across all sources. |
| `cli_loader.py` | Reads v2 CLI sessions from SQLite (`conversations_v2` table). |
| `cli_v3_loader.py` | Reads v3 CLI sessions from `.json` + `.jsonl` file pairs. |
| `ide_loader.py` | Reads IDE sessions from workspace-sessions JSON and legacy hash-dir formats. |
| `config.py` | Configuration loading from TOML files with sensible defaults. |
| `models.py` | Pydantic data models shared across all modules. |

## Data Flow

1. **Startup**: Server starts, spawns a daemon thread that preloads the embedding model and builds the index.
2. **Index Build**: `list_all_sessions()` discovers sessions from all enabled sources. Sessions are sorted by recency and trimmed to fit memory limits. Messages are loaded and embedded.
3. **Search**: When a tool is called, the query is embedded using the same model, then cosine similarity is computed against all indexed messages. Results are filtered, deduplicated, and returned with surrounding context.
4. **Caching**: Embeddings are cached to `~/.cache/kiro-total-recall/embeddings.pkl` with file-level locking. Only new/changed messages are re-embedded on subsequent runs.

## Key Design Decisions

- **Embedding model**: `all-MiniLM-L6-v2` (384 dimensions). Small, fast, good quality for conversational text.
- **Memory management**: Configurable fraction of physical RAM. Oldest sessions are excluded when the limit is reached.
- **Session fingerprinting**: A hash of session IDs and timestamps detects when the index needs rebuilding.
- **Source routing**: CLI sessions are distinguished between v2 (SQLite) and v3 (file-based) using a tracked set of v3 session IDs populated during session listing.
- **Deduplication**: Overlapping context windows within the same session are merged, keeping the highest-scoring match.
