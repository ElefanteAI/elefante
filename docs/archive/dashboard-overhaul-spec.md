# Dashboard Overhaul SPEC (Snapshot-First, Curated-First)

**Status**: Production (shipped in v2.0.0)

## 1) Goals

- **Snapshot-first runtime**: the dashboard server and UI must **not** touch ChromaDB or Kuzu at runtime.
- **Curated-first UX**: users should see meaningful titles and summaries, not raw memory dumps.
- **Explainable connectivity**: edges shown by default must be deterministic and typed (e.g., `signal`, `cohesion`, `graph`).
- **Stable, debuggable behavior**: if something looks “isolated”, the UI and tooling should explain why (filters/toggles/edge types).
- **Safe with Elefante Mode OFF**: dashboard must work without acquiring DB locks.

## 2) Non-Goals

- Real-time, live DB querying from the dashboard.
- Runtime embedding/semantic edge computation.
- “Perfect” natural-language rewriting of memories (that belongs in ingestion or dedicated curation pipelines).

## 3) Architecture Constraints (Laws)

- **LAW #1**: Dashboard server cannot import or instantiate services that access databases.
- **LAW #2**: Dashboard reads a **single JSON snapshot** file (see contract).
- **LAW #3**: Snapshot generation is the only place where DB access is allowed for dashboard data.

## 4) Primary User Flows (Acceptance)

### A) Load graph

- Given a valid snapshot, `/api/graph` returns nodes + edges.
- UI renders the graph deterministically given the same snapshot.

### B) Hover a memory

- Hover tooltip shows:
  - Curated title
  - Curated summary
  - Optional classification metadata (ring/topic/knowledge_type)
  - Visible link counts by edge type
- Tooltip must not dump raw `properties.content` by default.

### C) Diagnose “isolation”

- A node that appears isolated in the current view provides explainability:
  - either it truly has degree 0 in the snapshot, or
  - it is hidden by current view toggles/filters.

## 5) Data Quality Requirements

- Every memory node should ideally have:
  - `properties.title` (short, human-friendly)
  - `properties.summary` (one sentence)
- Snapshot curation can be applied offline, but production quality should be enforced at ingestion-time.

## 6) Verification

- Run: `python scripts/verify/verify_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json`
- Optional stricter mode:
  - `--require-curation` to fail if title/summary missing
  - `--strict` to treat warnings as errors
