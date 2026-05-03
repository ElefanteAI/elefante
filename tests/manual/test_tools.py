"""Manual script to verify MCP tool and prompt registration from source."""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "src" / "mcp" / "server.py"


def _tool_names(source: str) -> list[str]:
    return sorted(set(re.findall(r'types\.Tool\(\s*name="(elefante-[^"]+)"', source, re.DOTALL)))


def _prompt_names(source: str) -> list[str]:
    return sorted(set(re.findall(r'Prompt\(\s*name="(elefante-[^"]+)"', source, re.DOTALL)))


def _run_tool_registration() -> bool:
    print("=" * 60)
    print("ELEFANTE MCP SERVER - TOOL AND PROMPT REGISTRATION TEST")
    print("=" * 60)

    print("\n[1/3] Reading MCP server source...")
    source = SERVER_PATH.read_text(encoding="utf-8")
    print(f"[OK] Loaded {SERVER_PATH}")

    print("\n[2/3] Extracting tool and prompt lists from source...")
    tool_names = _tool_names(source)
    prompt_names = _prompt_names(source)
    print(f"Found {len(tool_names)} tools and {len(prompt_names)} prompts in source code")

    print(f"\n[3/3] Registered tools ({len(tool_names)} total):")
    for i, name in enumerate(tool_names, 1):
        print(f"  {i}. {name}")

    print(f"\nRegistered prompts ({len(prompt_names)} total):")
    for i, name in enumerate(prompt_names, 1):
        print(f"  {i}. {name}")

    expected_tools = [
        'elefante-Memory',
        'elefante-GraphConnect',
        'elefante-GraphQuery',
        'elefante-ContextGet',
        'elefante-SessionsList',
        'elefante-SystemStatusGet',
        'elefante-DashboardOpen',
        'elefante-System',
        'elefante-TaskCreate',
        'elefante-TaskUpdate',
        'elefante-TaskGraph',
        'elefante-ETLProcess',
        'elefante-ETLClassify',
        'elefante-DirectiveAdd',
        'elefante-DirectiveList',
        'elefante-DirectiveRemove',
    ]

    expected_prompts = [
        'elefante-context',
        'elefante-grounding',
    ]
    
    missing = [t for t in expected_tools if t not in tool_names]
    extra = [t for t in tool_names if t not in expected_tools]
    missing_prompts = [p for p in expected_prompts if p not in prompt_names]
    extra_prompts = [p for p in prompt_names if p not in expected_prompts]
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    print(f"Expected tools: {len(expected_tools)}")
    print(f"Found in code:  {len(tool_names)}")
    print(f"Expected prompts: {len(expected_prompts)}")
    print(f"Found in code:    {len(prompt_names)}")
    
    if missing:
        print(f"\n[FAIL] Missing tools: {missing}")
    if extra:
        print(f"\n[WARN] Extra tools: {extra}")
    if missing_prompts:
        print(f"\n[FAIL] Missing prompts: {missing_prompts}")
    if extra_prompts:
        print(f"\n[WARN] Extra prompts: {extra_prompts}")
    
    if (
        len(tool_names) == len(expected_tools)
        and not missing
        and len(prompt_names) == len(expected_prompts)
        and not missing_prompts
    ):
        print("\n[SUCCESS] All expected tools and prompts are defined in the code!")
        return True
    else:
        print("\n[FAIL] Tool/prompt registration incomplete in code")
        return False


def test_tool_registration():
    pytest.skip("Manual verification script; run this module directly to execute")

if __name__ == "__main__":
    raise SystemExit(0 if _run_tool_registration() else 1)

