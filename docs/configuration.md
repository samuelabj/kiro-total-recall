# Configuration

Kiro Total Recall is configured via a TOML file. The system looks for configuration in this order:

1. `~/.config/kiro-total-recall/config.toml` (user config)
2. `config.default.toml` in the project root (fallback defaults)
3. Hardcoded defaults in `config.py`

To customize, copy `config.default.toml` to `~/.config/kiro-total-recall/config.toml` and edit.

## Full Reference

### `[sources.cli]` — CLI Session Sources

```toml
[sources.cli]
enabled = true

# SQLite database paths for v2 format — first existing path wins
paths = [
    "~/Library/Application Support/kiro-cli/data.sqlite3",
    "~/.local/share/kiro-cli/data.sqlite3",
    "~/AppData/Local/Kiro-Cli/data.sqlite3",
    "~/AppData/Roaming/kiro-cli/data.sqlite3",
]

# v3 file-based sessions directory (kiro-cli --v3)
v3_paths = [
    "~/.kiro/sessions/cli",
]
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable CLI session indexing |
| `paths` | list[str] | (platform paths) | SQLite database locations for v2 format. First existing path is used. |
| `v3_paths` | list[str] | `["~/.kiro/sessions/cli"]` | Directories containing v3 `.json`/`.jsonl` session files. First existing path is used. |

### `[sources.ide]` — IDE Session Sources

```toml
[sources.ide]
enabled = true

# Glob patterns for session files — checks both .chat and workspace-sessions formats
patterns = [
    "~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
    "~/.config/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
    "~/AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
    "~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
    "~/.config/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
    "~/AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
]
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable IDE session indexing |
| `patterns` | list[str] | (platform globs) | Glob patterns to locate IDE session files. Uses `**` for recursive matching. |

### `[embedding]` — Embedding Model

```toml
[embedding]
model = "all-MiniLM-L6-v2"
cache_dir = "~/.cache/kiro-total-recall"
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model` | str | `"all-MiniLM-L6-v2"` | Sentence-transformer model name. Must produce 384-dim vectors. |
| `cache_dir` | str | `"~/.cache/kiro-total-recall"` | Directory for embedding cache and lock files. |

The cache stores pre-computed embeddings in `embeddings.pkl` so messages don't need re-embedding on restart. A `embeddings.lock` file provides safe concurrent access.

### `[search]` — Search Defaults

```toml
[search]
default_threshold = 0.2
default_max_results = 10
default_context_window = 3
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_threshold` | float | `0.2` | Minimum cosine similarity (0–1) for a result to be returned. Lower values return more results. |
| `default_max_results` | int | `10` | Maximum results per search call (before pagination). |
| `default_context_window` | int | `3` | Number of messages before AND after each match to include as context. |

These are defaults — each search tool call can override them via parameters.

### `[memory]` — Memory Management

```toml
[memory]
fraction = 0.33
# limit_mb = 512
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `fraction` | float | `0.33` | Fraction of physical RAM to allow for the index. Oldest sessions are excluded if the limit is exceeded. |
| `limit_mb` | int \| null | `null` | Explicit memory limit in MB. Takes precedence over `fraction` when set. |

## Environment Variables

These override config file settings:

| Variable | Effect |
|----------|--------|
| `KIRO_RECALL_MEMORY_LIMIT_MB` | Override memory limit (in MB). Takes precedence over config. |
| `KIRO_RECALL_NO_MEMORY_LIMIT` | Set to any value to disable memory limiting entirely. |
| `KIRO_PROJECT_DIR` | Override workspace detection for `search_project_history`. |
| `KIRO_WORKSPACE` | Alternative to `KIRO_PROJECT_DIR` for workspace detection. |

## MCP Server Configuration

To use Total Recall as an MCP server in Kiro, add it to your `mcp.json`:

```json
{
  "mcpServers": {
    "kiro-total-recall": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/kiro-total-recall", "kiro-total-recall"],
      "env": {
        "KIRO_RECALL_NO_MEMORY_LIMIT": "1"
      },
      "disabled": false
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "kiro-total-recall": {
      "command": "kiro-total-recall",
      "disabled": false
    }
  }
}
```

## Path Resolution

All paths in configuration support `~` expansion (resolved to the user's home directory). On Windows, this expands to `%USERPROFILE%` (e.g., `C:\Users\username`).

For list-based paths (`paths`, `v3_paths`), the first existing path is used. For glob patterns, the first pattern that produces matches is used.
