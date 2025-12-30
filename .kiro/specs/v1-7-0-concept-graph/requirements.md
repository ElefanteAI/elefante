# Requirements: V1.7.0 Concept Graph

*Methodology: Kiro Spec-Driven Development (R>D>T = Requirements -> Design -> Tasks)*

## 1. Goal

Make `concepts` first-class graph entities (nodes) in Kuzu so memories with shared concepts are visually and traversably connected. This improves:
- Knowledge graph visualization (see concept clusters)
- Traversal-based retrieval (find memories via concept paths)
- Coactivation scoring (V4 already uses graph density; concept edges add signal)

## 2. Problem Statement

Currently:
- `concepts` are stored as metadata strings in ChromaDB (after v1.6.1 standardization)
- V4 concept-overlap scoring computes set intersection at query time
- There are NO graph edges connecting memories that share concepts
- The Kuzu graph has Entity nodes (person, project, file, etc.) but no Concept nodes
- Coactivation signal in V4 retrieval is weak because memories lack relational density

Result: the knowledge graph is sparse; memories are isolated islands unless manually linked via entities.

## 3. Non-Goals

- Do not change V4 scoring weights (concept overlap weight stays at 0.20)
- Do not auto-generate concepts from content (concepts come from metadata at ingestion)
- Do not create edges between concept nodes themselves (keep it simple: memory <-> concept only)
- Do not retroactively link ALL memories in a single migration (migration is opt-in via script)

## 4. Definitions

- **Concept Node**: A Kuzu Entity node with `type=concept`, `name=<canonical_label>`.
- **HAS_CONCEPT edge**: A relationship from Memory node to Concept node (or from Entity node to Concept node).
- **Concept cluster**: The set of memories/entities connected to the same Concept node.

## 5. User Stories

1. As a user, when I store a memory with `concepts: ["elefante", "mcp"]`, I want graph nodes "elefante" and "mcp" to exist and be linked to that memory, so I can traverse the graph by concept.
2. As a user, when I query the dashboard or run a graph query, I want to see which memories share concepts visually, so I can understand knowledge clusters.
3. As the system (V4 retriever), when I compute coactivation score, I want concept edges to contribute to graph density, so retrieval ranking improves.

## 6. Acceptance Criteria (EARS)

- WHEN a memory is ingested with non-empty `concepts`, THE SYSTEM SHALL create or reuse Concept nodes for each canonical label and create `HAS_CONCEPT` edges from the memory to those nodes.
- WHEN a Concept node with a given canonical name already exists, THE SYSTEM SHALL reuse it (no duplicates).
- WHEN querying the graph for a concept name, THE SYSTEM SHALL return all memories linked to that concept.
- WHEN the dashboard generates a snapshot, THE SYSTEM SHALL include Concept nodes and their edges in the graph data.

## 7. Out of Scope (Future)

- Weighted concept edges (all edges have equal strength for now)
- Concept hierarchy/taxonomy (parent-child concepts)
- Auto-extraction of concepts from memory content via NLP

## 8. Verification

- Integration test: ingest 2 memories with overlapping concepts, verify shared Concept node exists with 2 edges.
- Graph query test: `MATCH (m:Memory)-[:HAS_CONCEPT]->(c:Concept {name: 'elefante'}) RETURN m` returns expected memories.
- Dashboard test: snapshot includes `concept_stats` with node counts.

## 9. Approval Gate

Stop here.

Do not proceed to **Design** until the user explicitly approves these **Requirements**.
