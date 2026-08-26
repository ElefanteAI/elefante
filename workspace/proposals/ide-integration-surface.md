# IDE and Agent Integration Surface

> **Status:** PARTIALLY IMPLEMENTED. The v2.12.2 customer-global runtime and
> detected-host adapters are released. Additional host certification,
> extension-managed surfaces, and automated documentation-drift inspection are
> Upcoming without a promised version or date.

## Problem

Elefante loses its purpose if each editor owns a different process or memory
store. Multiple hosts must share one account-level local runtime without
overwriting user configuration or creating concurrent graph writers.

## Released architecture

1. One user-level, loopback-only daemon owns SQLite vector storage and Kuzu.
2. Hosts connect through native local HTTP when supported or the shipped
   storage-free stdio bridge.
3. Every write carries Source provenance identifying the host, instance,
   session, and workspace when available.
4. Installers detect supported hosts, preserve unrelated configuration, record
   only Elefante-owned changes, and remove only unchanged owned entries.
5. Rerunning the customer installer repairs and reconnects detected compatible
   hosts to the stable account-level runtime.

The source authority for adapters is `scripts/setup/`; the current compatibility
and ownership inventory is
[`agents/manifests/ide-integration.yaml`](../../agents/manifests/ide-integration.yaml).
Released user instructions are in
[`docs/how-to/configure-ide.md`](../../docs/how-to/configure-ide.md).

## Compatibility language

- **Certified:** the actual host has passed install, reconnect, concurrent use,
  upgrade, and uninstall on the stated platform.
- **Compatible:** Elefante emits the documented host contract and adapter tests
  pass, but full host-driven certification is incomplete.
- **Community:** a documented manual route exists; Elefante does not own the
  host lifecycle.
- **Planned:** no released integration exists.

Marketing and user docs must use only these terms and must not infer support
from a hostname appearing in this proposal.

## Released milestones

| Milestone | Result |
|---|---|
| v2.10 foundation | Consolidated MCP contract and developer documentation routing |
| v2.11 integration baseline | Daemon, bridge, Source provenance, safe ownership, compatible adapters |
| v2.12.0 installer baseline | Host-aware selection and platform launchers |
| v2.12.2 customer-global runtime | One stable customer installation, client-only archives, real bridge/daemon handshake |

## Upcoming work

- Host-driven certification for every advertised surface.
- Additional adapters where a stable vendor contract and test environment exist.
- Automated manifest and vendor-document drift checks.
- Broader `elefante doctor` integration verification.
- Extension-managed instruction surfaces that cannot be configured safely by a
  normal file or native CLI adapter.

These items have no assigned release or date. Windsurf and any other surface
without a released adapter remain Planned, not supported.

## Acceptance for a new adapter

1. Vendor configuration contract is cited and reverified.
2. Detection is read-only and has no false-positive path.
3. Dry-run shows the exact proposed change without mutation.
4. Install preserves unrelated and user-owned Elefante entries.
5. Runtime handshake uses the installed bridge and shared daemon.
6. Upgrade preserves user changes and refreshes only installer-owned state.
7. Uninstall removes only fingerprint-matching owned state.
8. Source provenance identifies the host without leaking secrets.
9. Compatibility matrix, user guide, tests, and changelog are updated together.

## Explicit non-goals

- A separate memory store per IDE.
- Provider-specific memory semantics.
- Public network exposure by default.
- Silent mutation of legacy stores or user-owned host configuration.
- Claiming certification from adapter unit tests alone.

## Verification

Use the smallest relevant adapter tests first, then the shared installer and
bridge contracts:

```bash
./.venv/bin/python -m pytest tests/test_install_setup.py tests/test_mcp_handshake_verifier.py -q
./.venv/bin/python scripts/ci/list_mcp_tools.py
```

External host certification remains **UNKNOWN** until an actual host-driven run
records evidence for that platform and version.
