# Documentation Requirements

Before committing changes to this project, ensure relevant documentation is updated:

## What to update

- **`docs/session-formats.md`** — When adding or modifying a session loader, document the storage format (location, file structure, schema, payload types, and notes).
- **`docs/architecture.md`** — When adding new modules or changing data flow, update the system diagram and module table.
- **`docs/configuration.md`** — When adding config options, environment variables, or changing defaults.
- **`docs/development.md`** — When adding new source files, dependencies, or changing project structure.
- **`docs/adr/`** — When making architectural decisions (new modules, routing strategies, format handling, deliberate exclusions). Use sequential numbering: `NNN-short-description.md`.

## ADR format

```markdown
# ADR-NNN: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Superseded | Deprecated

## Context
## Decision
## Rationale
## Consequences
```

## When to skip

- Trivial fixes (typos, formatting) don't need doc updates.
- If the change only affects internal implementation without changing behavior, architecture, or configuration, docs can be skipped.
