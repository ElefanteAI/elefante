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

# Made with Bob