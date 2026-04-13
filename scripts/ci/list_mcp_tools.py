"""List MCP tools registered by Elefante."""

import inspect
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.mcp.server import ElefanteMCPServer


def main() -> int:
    server = ElefanteMCPServer()
    source = inspect.getsource(server._register_handlers)
    tool_names = re.findall(r'name="(\w+)"', source)

    print(f"Available MCP Tools: {len(tool_names)}")
    for name in tool_names:
        print(f"  - {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
