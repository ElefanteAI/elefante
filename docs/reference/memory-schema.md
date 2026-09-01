# Memory Schema

This reference describes the current development `Memory` and `MemoryMetadata`
models in `src/models/memory.py`. Published v2.13.0 does not yet include the
unreleased `recall_cues` extension described below.

## Memory

| Field | Type | Meaning |
|---|---|---|
| `id` | UUID | Generated memory identity |
| `content` | string, 1–10,000 characters | Durable memory text |
| `metadata` | `MemoryMetadata` | Classification, provenance, lifecycle, and scoring inputs |
| `embedding` | optional float list | Populated by the embedding service; stored explicitly |
| `related_entities` | UUID list | Graph entity references |
| `similarity_score` | optional float | Populated on retrieval |
| `relevance_score` | optional float | Populated on retrieval |

## Metadata groups

### Identity and classification

- `created_at`, `created_by`
- `domain`: `work`, `personal`, `learning`, `project`, `reference`, or `system`
- `category`
- `memory_type`: `fact`, `decision`, `preference`, `insight`, `note`,
  `conversation`, `specification`, or `directive`

### Retrieval inputs

| Field             | Type       | Purpose                                        | Auto-populated |
| ----------------- | ---------- | ---------------------------------------------- | -------------- |
| `concepts`        | `string[]` | 3-5 key terms used by concept-overlap retrieval | Yes            |
| `surfaces_when`   | `string[]` | Literal hints for explicitly triggered delivery; not a current ranking signal | Yes |
| `recall_cues`     | `string[]` | Up to five customer-supplied likely future questions used by exact project-scoped Recall | Verified customer writes only |
| `authority_score` | `float`    | Stored compatibility/dashboard field; the current retriever derives authority from vitality and access count | Yes |

- `score`: integer `0–100`; defaults to 100 and is system-managed
- `confidence`: float `0.0–1.0`; defaults to 0.7
- `tags`, `keywords`, `entities`

Recall cues are canonicalized, bounded to 1,000 characters each, deduplicated,
and never treated as a broad trigger or similarity override. A cue matches only
the complete normalized question, and only when both project and workspace are
resolved through the strict registry. The candidate must still pass lifecycle,
scope, reliability, current-source, conflict, and privacy gates. Home Remember
creates the first cue; verified Edit, Replace, and Restore maintain the cue on
the resulting current record.

`compute_authority_score()` returns `1.0` for specification/directive types.
Other types combine current score (0.35), access frequency (0.25), creation
freshness (0.20), and access freshness (0.20). Retrieval later combines
authority with four other signals; see [`scoring.md`](scoring.md).

### Relationships and lifecycle

- `status`, `relationship_type`, `parent_id`
- `related_memory_ids`, `conflict_ids`
- `supersedes_id`, `superseded_by_id`
- `version`, `deprecated`, `archived`, `summary`

Deprecated and archived memories are excluded from normal semantic results.

### Governance

- `retention_policy`: managed, permanent, or ephemeral
- `injection_policy`: ranked, triggered, or always
- `scope`: optional project, workspace, or task scope
- `trigger`: up to 20 phrases for triggered delivery
- `user_locked`: explicit user authority that protects the memory from
  automated refinery lifecycle changes

Defaults are managed, ranked, no scope, no triggers, and unlocked.
Always-inject is fail-closed unless user_locked is true. Governance is applied
before task-specific ranking; protected duplicates are not silently
archived. Ephemeral is currently declarative—automatic expiry is not
implemented. Invocation authority and causal task utility remain separate
operation/evaluation concerns.

The released proactive-surfacing path accepts an explicit query, file,
terminal-error, or conversation context and checks literal `trigger` plus
`surfaces_when` phrases only for `injection_policy="triggered"` memories. It
returns at most three read-only matches, skips inactive, conflicted, stale-source,
low-trust, or secret-bearing records, and never reinforces access or graph state.
When the caller supplies a workspace filter, stale-source means the shared
source-file digest check found a mismatch; without a workspace, an unavailable
source is not treated as proof of contradiction.
This is an opt-in delivery hint consumed by the bounded search/Recall selector.
Typed file, terminal-error, and conversation host adapters may submit explicit
surface context through the loopback event endpoint; the event is scrubbed and
not persisted, and no second semantic retriever is introduced.

Governed answer delivery separately reports a bounded warning when a candidate
has a stored conflict relationship or contradictory status. The conflicted
candidate is withheld, neither side is treated as authoritative, and the
warning omits internal memory IDs. The released runtime also has a
conservative explicit-proposition semantic detector and
`elefante-Memory(action="resolve")`. Resolve is dry-run-first, consolidates
equivalent assertions, requires a user-selected winner for ambiguous conflicts,
protects scope and user authority, preserves the losing record as superseded,
and rolls back a partial two-record write.

### Provenance

- `source`, `source_detail`, `source_reliability`, `verified`
- `session_id`, `author`
- `project`, `workspace`, `file_path`, `line_number`, `url`, `location`

Transport Source provenance also exists in the graph for installed multi-host
workflows. Provenance indicates origin; it does not by itself prove truth.

### Temporal fields

- `last_accessed`, `last_modified`, `access_count`. Ordinary retrieval does not
  update access; the default customer profile has no runtime reinforcement path.
- `decay_rate`, `reinforcement_factor`

Type decay is assigned when a Memory is constructed. Specifications and
directives have zero type decay, but freshness still affects vitality. The
exact formula is in [`scoring.md`](scoring.md).

### Extension fields

- `custom_metadata`: extension/application data
- `system_metadata`: Elefante-managed data such as token density

`custom_metadata.attachments` may contain portable descriptors for locally
stored image, audio, or video files. Each descriptor records a SHA-256 digest,
media kind, allowlisted MIME type, byte size, safe original name, relative
content-addressed path, bounded text description, and optional dimensions or
duration. It never stores an absolute source path. Attachment bytes are private
mode `0600`, bounded to 25 MiB each and eight per memory, and are not sent to a
model or network by Elefante. Text descriptions remain the retrieval fallback
for hosts that cannot render media.

Callers must not treat arbitrary custom metadata as a released query or
lifecycle contract.

## ETL enrichment

`elefante-ETLProcess` selects raw records for agent enrichment.
`elefante-ETLClassify` currently accepts and persists:

- one-line `summary`
- optional `concepts`
- optional `surfaces_when`

It does not accept ring, topic, or knowledge-type fields. Older V5 topology
language is historical and not part of the live MCP schema.

## Serialization

SQLite stores the complete versioned Memory JSON and explicit float32
embedding. The legacy ChromaDB adapter flattens metadata and reconstructs typed
fields on read. The JSON corpus export preserves the Memory ID and metadata but
omits embeddings; `scripts/pipeline/import_memories.py` regenerates them with
the configured local model and refuses ID collisions. Apply mode is fail-closed
unless the operator supplies `--confirm-stopped STOPPED`, and a non-empty
target also requires a verified binary backup. It does not contain the graph
snapshot, so it is not a full backup. Adding a field requires round-trip tests
for every supported configured backend and the customer backup/restore path.

## Related documentation

- [`architecture.md`](architecture.md)
- [`scoring.md`](scoring.md)
- [`tools.md`](tools.md)
