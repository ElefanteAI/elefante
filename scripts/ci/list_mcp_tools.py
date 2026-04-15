"""List MCP tools and prompts registered by Elefante."""

import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _read_server_source() -> str:
    return (ROOT_DIR / "src" / "mcp" / "server.py").read_text(encoding="utf-8")


def _tool_names(source: str) -> list[str]:
    return sorted(set(re.findall(r'types\.Tool\(\s*name="(elefante-[^"]+)"', source, re.DOTALL)))


def _prompt_names(source: str) -> list[str]:
    return sorted(set(re.findall(r'Prompt\(\s*name="(elefante-[^"]+)"', source, re.DOTALL)))


def main() -> int:
    source = _read_server_source()
    tool_names = _tool_names(source)
    prompt_names = _prompt_names(source)

    print(f"Available MCP Tools: {len(tool_names)}")
    for name in tool_names:
        print(f"  - {name}")

    print()
    print(f"Available MCP Prompts: {len(prompt_names)}")
    for name in prompt_names:
        print(f"  - {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
