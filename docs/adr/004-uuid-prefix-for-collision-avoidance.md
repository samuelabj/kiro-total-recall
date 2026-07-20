# ADR-004: UUID Prefix for Cross-Loader Collision Avoidance

**Date:** 2026-07-20
**Status:** Accepted

## Context

Each `IndexedMessage` requires a globally unique `uuid` field. The indexer uses this to identify messages for deduplication, context window retrieval, and cache keying.

The v2 loader generates UUIDs as `{session_id}-{index}-{role}`. The v3 format provides its own `message_id` field per entry. In theory these shouldn't collide, but both are UUID-shaped strings and the indexer makes no guarantees about cross-source uniqueness.

## Decision

Prefix v3 message UUIDs with `v3-`: `f"v3-{session.session_id}-{message_id}"`.

## Rationale

- Provides a simple visual marker when debugging which loader produced a message.
- Eliminates any theoretical collision risk between v2 synthesized UUIDs and v3 native message IDs.
- Zero cost — it's a string prefix, no structural changes needed.
- Follows defensive programming principles without over-engineering.

## Consequences

- V3 message UUIDs are slightly longer but this has no practical impact.
- If additional loaders are added, they should follow the same pattern (e.g., `ide-{...}`). The IDE loader currently uses session-file-based UUIDs which are already distinct.
