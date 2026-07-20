# Development

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
# Clone the repository
git clone https://github.com/danilop/kiro-total-recall.git
cd kiro-total-recall

# Create virtual environment and install dependencies
uv sync

# Or with pip
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e .
```

## Running Locally

```bash
# Run the MCP server directly
uv run kiro-total-recall

# Or via the venv
.venv/Scripts/python -m kiro_total_recall.server
```

The server communicates over stdio using the MCP protocol. It's designed to be launched by a Kiro IDE or CLI instance, not run standalone in a terminal.

## Adding a New Session Source

To support a new conversation storage format:

1. Create a new loader module (e.g., `new_source_loader.py`) with:
   - `list_new_source_sessions() -> list[SessionInfo]`
   - `load_new_source_session_messages(session: SessionInfo) -> list[IndexedMessage]`

2. Add any new config paths to `config.py` (follow the pattern of `CLISourceConfig`).

3. Integrate into `loader.py`:
   - Import the new functions
   - Call the listing function in `list_all_sessions()`
   - Route message loading in `load_session_messages()`

4. If the new source shares `Source.CLI` or `Source.IDE`, use a disambiguation mechanism (like the `_V3_SESSION_IDS` set). Otherwise, add a new `Source` enum value in `models.py`.

### Data Model Requirements

Each message must produce an `IndexedMessage` with:
- `uuid` — globally unique identifier (use a prefix like `v3-` to avoid collisions)
- `session_id` — groups messages into a conversation
- `workspace` — the project directory (used for `search_project_history` filtering)
- `timestamp` — when the message was created
- `role` — `"user"` or `"assistant"`
- `searchable_text` — the text content to embed and search
- `message_index` — position within the session (for context window retrieval)
- `source` — `Source.CLI` or `Source.IDE`

## Embedding Cache

Embeddings are cached at `~/.cache/kiro-total-recall/embeddings.pkl`. During development you may want to clear this to force re-embedding:

```bash
# Clear the cache
rm ~/.cache/kiro-total-recall/embeddings.pkl
```

On Windows:
```powershell
Remove-Item "$env:USERPROFILE\.cache\kiro-total-recall\embeddings.pkl"
```

## Linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check
uv run ruff check src/

# Fix auto-fixable issues
uv run ruff check --fix src/

# Format
uv run ruff format src/
```

Configuration is in `pyproject.toml` under `[tool.ruff]`.

## Debugging

### Check what sessions are discovered

```python
from kiro_total_recall.loader import list_all_sessions
sessions = list_all_sessions()
for s in sessions[:10]:
    print(f"{s.source.value:4} | {s.session_id[:12]}... | {s.workspace}")
```

### Check v3 CLI sessions specifically

```python
from kiro_total_recall.cli_v3_loader import list_cli_v3_sessions, load_cli_v3_session_messages
sessions = list_cli_v3_sessions()
for s in sessions:
    msgs = load_cli_v3_session_messages(s)
    print(f"{s.session_id[:12]}... -> {len(msgs)} messages")
```

### Inspect the index state

```python
from kiro_total_recall.indexer import get_index
index = get_index()
index.ensure_index()
print(f"Total messages indexed: {index.message_count}")
print(f"Excluded sessions (memory limit): {index.excluded_session_count}")
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp` | Model Context Protocol server framework (FastMCP) |
| `sentence-transformers` | Embedding model loading and inference |
| `numpy` | Vector operations for cosine similarity |
| `pydantic` | Data validation and serialization |
| `filelock` | Safe concurrent access to the embedding cache |

## Notes

- The server preloads the embedding model in a background thread at startup. First search may take a moment if the model hasn't loaded yet.
- The `all-MiniLM-L6-v2` model is ~80MB and downloaded on first run to `~/.cache/torch/sentence_transformers/`.
- Memory usage scales with the number of indexed messages. Each message uses approximately 2.6KB (embedding + metadata).
