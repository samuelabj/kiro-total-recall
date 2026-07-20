"""Configuration management for Kiro Total Recall."""

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Default paths
CONFIG_DIR = Path.home() / ".config" / "kiro-total-recall"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config.default.toml"

# Embedding constants
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Memory constants
BYTES_PER_MESSAGE = 2600
DEFAULT_MEMORY_FRACTION = 1 / 3
MEMORY_LIMIT_ENV = "KIRO_RECALL_MEMORY_LIMIT_MB"
MEMORY_LIMIT_DISABLED_ENV = "KIRO_RECALL_NO_MEMORY_LIMIT"


def expand_path(path: str) -> Path:
    """Expand ~ and return Path."""
    return Path(path).expanduser()


def find_first_existing(paths: list[str]) -> Path | None:
    """Return first existing path from list."""
    for p in paths:
        expanded = expand_path(p)
        if expanded.exists():
            return expanded
    return None


def find_first_matching_glob(patterns: list[str]) -> tuple[Path | None, str | None]:
    """Return (parent_dir, pattern) for first pattern with matches."""
    for pattern in patterns:
        expanded = expand_path(pattern)
        # Get the non-glob prefix as parent
        parts = expanded.parts
        parent_parts = []
        for part in parts:
            if "*" in part:
                break
            parent_parts.append(part)
        parent = Path(*parent_parts) if parent_parts else Path(".")
        if parent.exists() and list(parent.glob(str(expanded.relative_to(parent)))):
            return parent, pattern
    return None, None


@dataclass
class CLISourceConfig:
    """CLI source configuration."""

    enabled: bool = True
    paths: list[str] = field(default_factory=lambda: [
        "~/Library/Application Support/kiro-cli/data.sqlite3",
        "~/.local/share/kiro-cli/data.sqlite3",
        "~/AppData/Local/Kiro-Cli/data.sqlite3",
        "~/AppData/Roaming/kiro-cli/data.sqlite3",
    ])
    v3_paths: list[str] = field(default_factory=lambda: [
        "~/.kiro/sessions/cli",
    ])

    @property
    def database_path(self) -> Path | None:
        """Get first existing database path."""
        return find_first_existing(self.paths)

    @property
    def v3_sessions_dir(self) -> Path | None:
        """Get first existing v3 CLI sessions directory."""
        return find_first_existing(self.v3_paths)


@dataclass
class IDESourceConfig:
    """IDE source configuration."""

    enabled: bool = True
    patterns: list[str] = field(default_factory=lambda: [
        "~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
        "~/.config/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
        "~/AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/*/*.chat",
        # Also match .json session files in workspace-sessions
        "~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
        "~/.config/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
        "~/AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/*.json",
    ])
    v3_session_dirs: list[str] = field(default_factory=lambda: [
        "~/.kiro/sessions",
    ])

    def get_chat_files(self) -> list[Path]:
        """Get all .chat/.json session files matching patterns."""
        for pattern in self.patterns:
            expanded = expand_path(pattern)
            parts = expanded.parts
            parent_parts = []
            glob_pattern_parts = []
            in_glob = False
            for part in parts:
                if "*" in part or in_glob:
                    in_glob = True
                    glob_pattern_parts.append(part)
                else:
                    parent_parts.append(part)
            parent = Path(*parent_parts) if parent_parts else Path(".")
            glob_pattern = str(Path(*glob_pattern_parts)) if glob_pattern_parts else "*"
            if parent.exists():
                files = list(parent.glob(glob_pattern))
                if files:
                    return sorted(files)
        return []


@dataclass
class EmbeddingConfig:
    """Embedding configuration."""

    model: str = EMBEDDING_MODEL
    cache_dir: str = "~/.cache/kiro-total-recall"

    @property
    def cache_path(self) -> Path:
        return expand_path(self.cache_dir)

    @property
    def cache_file(self) -> Path:
        return self.cache_path / "embeddings.pkl"

    @property
    def lock_file(self) -> Path:
        return self.cache_path / "embeddings.lock"


@dataclass
class SearchConfig:
    """Search configuration."""

    default_threshold: float = 0.2
    default_max_results: int = 10
    default_context_window: int = 3


@dataclass
class MemoryConfig:
    """Memory configuration."""

    fraction: float = DEFAULT_MEMORY_FRACTION
    limit_mb: int | None = None


@dataclass
class Config:
    """Main configuration."""

    cli: CLISourceConfig = field(default_factory=CLISourceConfig)
    ide: IDESourceConfig = field(default_factory=IDESourceConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        cli_data = data.get("sources", {}).get("cli", {})
        ide_data = data.get("sources", {}).get("ide", {})
        emb_data = data.get("embedding", {})
        search_data = data.get("search", {})
        mem_data = data.get("memory", {})

        return cls(
            cli=CLISourceConfig(**cli_data) if cli_data else CLISourceConfig(),
            ide=IDESourceConfig(**ide_data) if ide_data else IDESourceConfig(),
            embedding=EmbeddingConfig(**emb_data) if emb_data else EmbeddingConfig(),
            search=SearchConfig(**search_data) if search_data else SearchConfig(),
            memory=MemoryConfig(**mem_data) if mem_data else MemoryConfig(),
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load configuration (cached)."""
    # Try user config first
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return Config.from_dict(tomllib.load(f))

    # Fall back to default config
    if DEFAULT_CONFIG.exists():
        with open(DEFAULT_CONFIG, "rb") as f:
            return Config.from_dict(tomllib.load(f))

    # Use hardcoded defaults
    return Config()
