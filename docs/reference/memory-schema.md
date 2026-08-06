# Memory Schema

This reference describes the current `Memory` and `MemoryMetadata` models in
`src/models/memory.py`. Design-only governance fields are not part of this
released schema.

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

- `score`: integer `0–100`; defaults to 100 and is system-managed
- `confidence`: float `0.0–1.0`; defaults to 0.7
- `tags`, `keywords`, `entities`
- `concepts`: deterministic or agent-supplied key terms
- `surfaces_when`: query patterns used as retrieval hints
- `authority_score`: float `0.0–1.0`

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
The current schema does not include user locks, retention class, injection
policy, dormant state, utility confidence, or automatic forgetting controls.
Those remain developer design work.

### Provenance

- `source`, `source_detail`, `source_reliability`, `verified`
- `session_id`, `author`
- `project`, `workspace`, `file_path`, `line_number`, `url`, `location`

Transport Source provenance also exists in the graph for installed multi-host
workflows. Provenance indicates origin; it does not by itself prove truth.

### Temporal fields

- `last_accessed`, `last_modified`, `access_count`
- `decay_rate`, `reinforcement_factor`

Type decay is assigned when a Memory is constructed. Specifications and
directives have zero type decay, but freshness still affects vitality. The
exact formula is in [`scoring.md`](scoring.md).

### Extension fields

- `custom_metadata`: extension/application data
- `system_metadata`: Elefante-managed data such as token density

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
fields on read. Adding a field requires round-trip tests for every supported
configured backend and the customer backup/restore path.

## Related documentation

- [`architecture.md`](architecture.md)
- [`scoring.md`](scoring.md)
- [`tools.md`](tools.md)
