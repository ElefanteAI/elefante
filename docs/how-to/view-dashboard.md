# View the Local Dashboard

**Applies to:** v2.12.3

The dashboard is a loopback-only, read-only view of
`dashboard_snapshot.json`. It never opens the live vector store or Kuzu.

## Open through Elefante

From an MCP host, call:

```text
elefante-DashboardOpen(refresh=true)
```

`refresh=true` regenerates the redacted snapshot before opening the UI. Browser
reload only rereads the existing snapshot.

## Open from a source checkout

Generate and validate the snapshot, then start the server:

```bash
./.venv/bin/python scripts/pipeline/update_dashboard_data.py
./.venv/bin/python scripts/verify/verify_dashboard_snapshot.py \
  --path ~/.elefante/data/dashboard_snapshot.json
./.venv/bin/python -m src.dashboard.server
```

Open <http://127.0.0.1:8000>.

The standalone pipeline opens the configured stores while it exports the
snapshot. Do not run it beside another direct database-owning source process.
For a customer daemon, use `elefante-DashboardOpen(refresh=true)` instead.

## What the views mean

- **Briefing:** selects a durable current memory and may show a grounded
  assumption -> evidence -> decision -> guard trail when explicit graph edges
  exist.
- **Memories:** searches and sorts records present in the snapshot.
- **Connections:** shows topic/distribution views and explicit graph
  relationships.

Snapshot search is lexical. It is not the same as MCP semantic and graph
retrieval. The UI must not invent reasoning paths or per-query score signals
that the snapshot does not contain.

## Verify

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/api/stats
./.venv/bin/python scripts/verify/verify_dashboard_health.py --port 8000
```

Expected health payload:

```json
{"status":"ok","service":"elefante-dashboard"}
```

The read-only endpoints are `/api/graph`, `/api/search`, and `/api/stats`.

## Troubleshooting

### Snapshot is empty or stale

Regenerate it through `elefante-DashboardOpen(refresh=true)` or the pipeline
command above. A stale dashboard does not mean the live memory store is empty.

### Port 8000 is busy

First check whether the dashboard is already healthy. If another process owns
the port, stop that process or configure a different local port. Do not kill an
unknown process blindly.

### Snapshot export reports a Kuzu lock

Wait for the current transaction or stop the competing database-owning
process. Follow [`kuzu-troubleshooting.md`](kuzu-troubleshooting.md); never
delete Kuzu's internal lock file as the default repair.

### Browser reports CORS or connection errors

The default allowed origins are `http://127.0.0.1:8000` and
`http://localhost:8000`. Use the exact URL printed by the server. External
origins require an explicit `ELEFANTE_DASHBOARD_CORS_ORIGINS` list and a
separately authenticated network boundary.

## Safe showcase

To inspect the UI without exposing or changing a real memory store:

```bash
./.venv/bin/python scripts/demo/generate_showcase_snapshot.py \
  --output /tmp/elefante-showcase/dashboard_snapshot.json
ELEFANTE_DATA_DIR=/tmp/elefante-showcase \
  ./.venv/bin/python -m src.dashboard.server
```

The maintained showcase is deterministic and discloses synthetic behavior
metadata. It does not represent customer usage or product performance.

## Security boundary

The snapshot can contain private memory content even though it is redacted for
the dashboard. Keep the server on `127.0.0.1`. Docker Compose publishes the
container only to host loopback; its internal `0.0.0.0` bind is not permission
to expose the dashboard publicly.

The snapshot schema is defined in
[`../reference/dashboard-snapshot.md`](../reference/dashboard-snapshot.md).
