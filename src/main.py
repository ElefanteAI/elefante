# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/main.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Application entry point for non-MCP execution paths (CLI, scripts).
# ROLE    : Top-level launcher — enforces Python version, then delegates.
# TOUCHED : Rarely. Only when the entry point dispatch logic changes or a new
#           top-level execution mode is added.
# ─────────────────────────────────────────────────────────────────────────────
import sys

def main():
    ensure_supported_python()

    if "--mcp" in sys.argv or "stdio" in sys.argv:
        from src.mcp.server import main as mcp_main
        sys.exit(mcp_main())
    else:
        from src.desktop import run_gui
        sys.exit(run_gui())

if __name__ == "__main__":
    main()
