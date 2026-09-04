"""Black-box acceptance for reversible Codex Recall routing."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[3]


def _fake_codex(tmp_path: Path) -> tuple[Path, Path]:
    """Create a host-owned Codex CLI double without importing installer code."""
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    state = tmp_path / "codex-registration.json"
    driver = tmp_path / "fake_codex.py"
    driver.write_text(
        """from __future__ import annotations

import json
import os
import sys
from pathlib import Path

state = Path(os.environ["FAKE_CODEX_STATE"])
arguments = sys.argv[1:]
if arguments[:3] == ["mcp", "get", "elefante"]:
    if not state.exists():
        raise SystemExit(1)
    print(state.read_text(encoding="utf-8"))
    raise SystemExit(0)
if arguments[:3] == ["mcp", "remove", "elefante"]:
    state.unlink(missing_ok=True)
    raise SystemExit(0)
if arguments[:2] == ["mcp", "add"]:
    state.write_text(
        json.dumps(
            {
                "name": "elefante",
                "transport": {
                    "command": "python",
                    "args": ["-m", "src.mcp.stdio_bridge"],
                    "env": {"ELEFANTE_CLIENT_TOOL": "codex"},
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = binary_dir / "codex.cmd"
        launcher.write_text(
            f'@"{sys.executable}" "{driver}" %*\r\n', encoding="utf-8"
        )
    else:
        launcher = binary_dir / "codex"
        launcher.write_text(
            f"#!{sys.executable}\nexec(compile(open({str(driver)!r}, encoding='utf-8').read(), {str(driver)!r}, 'exec'))\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    return binary_dir, state


def _live_mcp_tools(environment: dict[str, str]) -> list[dict]:
    """List tools through the real stdio protocol without importing product code."""
    server = StdioServerParameters(
        command=sys.executable,
        args=[
            "-c",
            "import asyncio; from src.mcp.server import main; asyncio.run(main())",
        ],
        cwd=ROOT,
        env={
            **environment,
            "ELEFANTE_DATA_DIR": str(Path(environment["HOME"]) / ".elefante/data"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
    )

    async def discover() -> list[dict]:
        # Discovery must follow the completed handshake, and the transport must
        # stay open until its response arrives. Piping all requests plus EOF can
        # race server initialization/response delivery on a clean CI runner.
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()
                return [tool.model_dump(by_alias=True) for tool in response.tools]

    async def bounded_discovery() -> list[dict]:
        return await asyncio.wait_for(discover(), timeout=30)

    return asyncio.run(bounded_discovery())


def test_codex_setup_routes_recall_without_owning_user_instructions(tmp_path) -> None:
    """Exercise only documented setup/uninstall commands and user-visible state."""
    home = tmp_path / "home"
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True)
    instructions = codex_home / "AGENTS.md"
    original = "# My instructions\n\n- Keep this user rule.\n"
    instructions.write_text(original, encoding="utf-8")
    binary_dir, registration = _fake_codex(tmp_path)
    environment = {
        **os.environ,
        "CODEX_HOME": str(codex_home),
        "FAKE_CODEX_STATE": str(registration),
        "HOME": str(home),
        "PATH": os.pathsep.join((str(binary_dir), os.environ.get("PATH", ""))),
        "PYTHONPATH": str(ROOT),
        "USERPROFILE": str(home),
    }

    configured = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/setup/configure_cli_agents.py"),
            "--host",
            "codex",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert configured.returncode == 0, configured.stderr
    assert registration.exists()
    rendered = instructions.read_text(encoding="utf-8")
    assert rendered.startswith(original)
    assert rendered.count(original) == 1
    assert "elefante-Recall" in rendered
    assert "complete question" in rendered

    recall = next(
        (tool for tool in _live_mcp_tools(environment) if tool["name"] == "elefante-Recall"),
        None,
    )
    assert recall is not None
    assert recall["inputSchema"]["required"] == ["question"]
    assert recall["annotations"]["readOnlyHint"] is True

    removed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/lifecycle/uninstall_elefante.py"),
            "--apply",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert removed.returncode == 0, removed.stderr
    assert instructions.read_text(encoding="utf-8") == original
    assert not registration.exists()
