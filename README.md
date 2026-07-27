# Kiro Total Recall

Ever told Kiro "like we discussed yesterday" only to realize... it has no idea?

**Total Recall** gives Kiro the memory it's missing.

## The Problem

1. **Sessions Are Isolated**: Each Kiro session starts fresh. Yesterday's architecture discussion? Gone.
2. **Projects Don't Share Knowledge**: Your preferences (testing style, package managers, patterns) aren't remembered across projects.
3. **CLI and IDE Are Separate**: Conversations in Kiro CLI don't connect to Kiro IDE.

**Total Recall indexes every Kiro conversation and provides semantic search.** Find discussions by *meaning*, not just keywords.

## Quickstart

### As a Kiro Power (Recommended, IDE only)

1. In Kiro IDE: Powers panel → **Add power from GitHub**
2. Enter: `https://github.com/samuelabj/kiro-total-recall`
3. The power activates automatically when you mention "recall", "remember", or "past conversation"

### Manual MCP Setup (CLI and IDE)

Add to `~/.kiro/settings/mcp.json` (this config is shared by both CLI and IDE):

```json
{
  "mcpServers": {
    "total-recall": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/samuelabj/kiro-total-recall", "kiro-total-recall"]
    }
  }
}
```

**Restart Kiro CLI/IDE** after adding. MCP servers are only loaded at startup.

### Verify Installation

In Kiro CLI: `/mcp` should list `total-recall`

In Kiro IDE: Check the MCP Servers panel

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Kiro CLI & IDE                                  │
│  ┌──────────────────────────┐    ┌──────────────────────────────────┐   │
│  │  CLI: SQLite DB          │    │  IDE: .chat JSON files           │   │
│  │  ~/Library/App Support/  │    │  ~/Library/App Support/Kiro/     │   │
│  │  kiro-cli/data.sqlite3   │    │  User/globalStorage/.../*.chat   │   │
│  └────────────┬─────────────┘    └─────────────┬────────────────────┘   │
│               └────────────────┬───────────────┘                        │
│                                ▼                                        │
│                    ┌───────────────────────┐                            │
│                    │   Unified Loader      │                            │
│                    └───────────┬───────────┘                            │
└────────────────────────────────┼────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Kiro Total Recall                                  │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────────────────┐   │
│  │ loader  │───▶│ indexer  │───▶│  query  │───▶│  MCP server        │   │
│  │ CLI+IDE │    │ 384-dim  │    │ cosine  │    │  4 search tools    │   │
│  └─────────┘    └────┬─────┘    └─────────┘    └────────────────────┘   │
│                      ▼                                                  │
│         ~/.cache/kiro-total-recall/embeddings.pkl                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Index: Making Search Fast

On first search, Total Recall:

1. **Loads** all messages from CLI (SQLite) and IDE (.chat files)
2. **Embeds** each message using [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (384-dimensional vectors)
3. **Caches** embeddings to `~/.cache/kiro-total-recall/embeddings.pkl`

Subsequent searches are fast because:

- **Fingerprinting**: Only rebuilds when conversations change
- **Incremental updates**: New messages get embedded; existing embeddings loaded from cache
- **Hash-based deduplication**: Same text = same embedding (no recomputation)

## Features

- **Semantic Search**: Find by meaning, not just keywords
- **Dual Source**: Searches both CLI and IDE conversations
- **Context Windows**: See surrounding messages for each match
- **Date Filtering**: Filter by time range (ISO 8601)
- **Incremental Indexing**: Only processes new conversations
- **Memory Limits**: Configurable RAM usage (default: 1/3 of RAM)

## MCP Tools

| Tool | Scope | Use Case |
|------|-------|----------|
| `search_project_history` | Current workspace | Bugs, decisions in *this* codebase |
| `search_global_history` | All workspaces | Preferences, patterns across *all* work |
| `search_cli_history` | CLI only | Kiro CLI conversations |
| `search_ide_history` | IDE only | Kiro IDE conversations |

### Parameters

All tools accept:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Keywords or sentence to search |
| `after` | none | Filter to messages on/after this date (inclusive). ISO 8601 format. |
| `before` | none | Filter to messages before this date (exclusive). ISO 8601 format. |
| `context_size` | 3 | Messages before AND after each match |
| `threshold` | 0.2 | Minimum similarity (0-1, higher = stricter) |
| `max_results` | 10 | Maximum results to return |
| `offset` | 0 | Skip results (for pagination) |

### Date Filtering Examples

```python
# Messages from a specific day
search_project_history(query="auth bug", after="2025-01-15", before="2025-01-16")

# Messages from the past week
search_project_history(query="refactoring", after="2025-01-25")

# Messages in January
search_project_history(query="database", after="2025-01-01", before="2025-02-01")
```

### Response Structure

```json
{
  "results": [
    {
      "matched_message": {
        "role": "assistant",
        "content": "To fix the authentication bug...",
        "timestamp": "2025-01-15T10:30:00",
        "workspace": "/Users/dev/myproject",
        "session_id": "abc123",
        "uuid": "msg-456",
        "source": "cli"
      },
      "score": 0.8542,
      "context": [
        {"role": "user", "content": "How do I fix this auth bug?", "timestamp": "...", "is_match": false},
        {"role": "assistant", "content": "To fix the authentication bug...", "timestamp": "...", "is_match": true}
      ]
    }
  ],
  "query": "authentication bug fix",
  "total_matches": 25,
  "offset": 0,
  "has_more": true,
  "hint": "Showing 1-10 of 25 matches. Use offset: 10 for more."
}
```

## Usage Examples

Just ask naturally:

```
"How did we fix that auth bug?"
"What did we discuss about the database schema?"
"What's my usual approach to error handling?"
"Find our React component discussions from last week"
```

Or use tools directly:

```python
search_project_history(query="authentication bug fix")
search_global_history(query="React component patterns")
search_cli_history(query="deployment", after="2025-01-01")
```

## Configuration

Create `~/.config/kiro-total-recall/config.toml` to customize:

```toml
[sources.cli]
enabled = true
paths = [
    "~/Library/Application Support/kiro-cli/data.sqlite3",
    "~/.local/share/kiro-cli/data.sqlite3",
    "~/AppData/Roaming/kiro-cli/data.sqlite3",
]

[sources.ide]
enabled = true
patterns = [
    "~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
    "~/.config/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
    "~/AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
]

[embedding]
model = "all-MiniLM-L6-v2"
cache_dir = "~/.cache/kiro-total-recall"

[search]
default_threshold = 0.2
default_max_results = 10
default_context_window = 3

[memory]
fraction = 0.33  # Use 1/3 of RAM
# limit_mb = 512  # Or set explicit limit
```

## Memory Management

Total Recall limits in-memory index size to prevent excessive memory usage. By default, it uses 1/3 of physical RAM. When the limit is reached, the oldest sessions are excluded from the index (newest sessions are kept).

| Variable | Description | Default |
|----------|-------------|---------|
| `KIRO_RECALL_MEMORY_LIMIT_MB` | Override memory limit in MB | 1/3 of RAM |
| `KIRO_RECALL_NO_MEMORY_LIMIT` | Set to any value to disable limit | - |

## Testing

```bash
# Test server starts
uvx kiro-total-recall
# Ctrl+C to exit

# Test search directly
uv run python -c "
from kiro_total_recall.query import search_conversations
result = search_conversations(query='bug fix', max_results=3)
print(f'Found {result.total_matches} matches')
"
```

## Project Structure

```
kiro-total-recall/
├── POWER.md                      # Kiro Power manifest + steering
├── mcp.json                      # MCP server config for Power
├── config.default.toml           # Default configuration
├── src/kiro_total_recall/
│   ├── server.py                 # FastMCP server, tool definitions
│   ├── query.py                  # Search engine, deduplication
│   ├── indexer.py                # Embedding, caching, fingerprinting
│   ├── loader.py                 # Unified loader (CLI + IDE)
│   ├── cli_loader.py             # SQLite parsing for CLI
│   ├── ide_loader.py             # JSON parsing for IDE .chat files
│   ├── config.py                 # Configuration management
│   └── models.py                 # Pydantic data models
├── pyproject.toml
└── LICENSE
```

## Technical Details

| Component | Technology |
|-----------|------------|
| Embedding model | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (384 dimensions) |
| Vector search | Cosine similarity via NumPy dot product |
| Cache format | Python pickle with file locking |
| MCP framework | [FastMCP](https://github.com/jlowin/fastmcp) |
| Package manager | [uv](https://docs.astral.sh/uv/) |

## License

[MIT License](LICENSE)
