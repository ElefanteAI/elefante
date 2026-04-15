# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/mcp/__main__.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Module entry point enabling `python -m src.mcp` execution.
#           Fixes the RuntimeWarning about src.mcp.server in sys.modules.
# ROLE    : MCP package glue — do not put logic here; delegate to server.py.
# TOUCHED : Only if the module launch mechanism changes. Do not add business logic.
# ─────────────────────────────────────────────────────────────────────────────
"""
Entry point for running Elefante MCP server as a module.

This file fixes the RuntimeWarning about 'src.mcp.server' found in sys.modules
by providing a proper __main__.py entry point.

Usage:
    python -m src.mcp
"""

import asyncio
from src.mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())

