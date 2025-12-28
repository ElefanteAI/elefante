# Workspace Cleanup Report (2025-12-12)

This file tracks non-destructive workspace cleanup work.

## Summary

- Removed emoji characters from user-facing output in the unified installer.
- Confirmed legacy tool names appear primarily in archive history (intentionally left as-is).
- Flagged remaining emoji usage across dashboard UI and various legacy scripts for follow-up.

## Changes Applied

### Installer output normalization

- Updated `scripts/install.py` to remove emoji characters and standardize tags:
  - `OK:` for success
  - `WARN:` for warnings
  - `ERROR:` for errors

## Flags / Follow-ups (Not Yet Changed)

### Emoji usage (non-archive)

Large emoji usage remains in:

- `src/dashboard/app.py`
- `src/dashboard/ui/src/App.tsx`
- `src/dashboard/ui/src/components/GraphCanvas.tsx`
- Several scripts under `scripts/` and `scripts/debug/`

Decision needed: keep emojis in the dashboard UI (UX choice) or remove to enforce a strict "no emojis anywhere" policy.

### VS Code MCP config duplication

We currently document/configure MCP in multiple formats depending on IDE:

- VS Code built-in MCP: `mcp.json` (`servers`)
- Roo-Cline: `settings.json` (`roo-cline.mcpServers`)
- VS Code chat MCP (experimental): `settings.json` (`chat.mcp.servers`)
- Cursor/Bob/Antigravity: `mcp_config.json` (`mcpServers`)
- Some Bob-IDE builds: `mcp_settings.json` (`mcpServers`)

Follow-up recommendation: add a single authoritative doc page that lists each IDE + exact file path + exact JSON shape, and link to it from install/troubleshooting.

Status: resolved.

- Authoritative IDE MCP config reference: `docs/technical/ide-mcp-configuration.md`
- Failure pattern: VS Code merges **User** and **Workspace** MCP server definitions; if both define `servers.elefante`, VS Code may show two identical Elefante servers.
- Policy: Elefante is enabled globally (User `mcp.json` is the source of truth).
- Required prevention: keep workspace `.vscode/mcp.json` free of a `servers.elefante` entry (workspace config can be empty).

## Notes

- No files were deleted.
- Archive content remains unchanged.
