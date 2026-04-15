# Annotated Excerpt: scripts/verify/verify_e2e_tests.py

```python
REQUEST_TIMEOUT_SECONDS = 90

# Supposed to do:
# allow large one-line JSON-RPC responses from tools like ContextGet.
#
# Previous failure:
# the harness used asyncio's default subprocess line limit and failed with
# "Separator is found, but chunk is longer than limit" during the full sweep.
#
# Debugging already done:
# reproduced during the dashboard-enabled self-protocol run, then fixed by
# raising the stream limit to 1 MiB. The full sweep now passes.
STREAM_LIMIT_BYTES = 1024 * 1024


class MCPClient:
    async def start(self) -> dict:
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env=self._env,
            limit=STREAM_LIMIT_BYTES,
        )


async def run_e2e(with_dashboard_open: bool) -> int:
    test_tag = f"self-protocol-{uuid4().hex[:8]}"
    temp_root_manager = tempfile.TemporaryDirectory(prefix="elefante-e2e-")
    temp_root = Path(temp_root_manager.name)
    temp_home = temp_root / "home"
    temp_data_dir = temp_root / "data"
    temp_home.mkdir(parents=True, exist_ok=True)
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    # Supposed to do:
    # run the real MCP server in an isolated temp environment so the verifier
    # never touches durable user data.
    #
    # Current status:
    # working. These env vars are now part of the live verification contract.
    harness_env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "HOME": str(temp_home),
        "USERPROFILE": str(temp_home),
        "ELEFANTE_DATA_DIR": str(temp_data_dir),
        "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
        "BROWSER": "/usr/bin/true",
    }

    # Supposed to do:
    # verify that DashboardOpen(refresh=True) wrote a snapshot where the live
    # runtime actually writes it.
    #
    # Previous failure:
    # the verifier only checked the temp-data path and missed the HOME-derived
    # path that src.mcp.server.DATA_DIR uses at runtime.
    #
    # Debugging already done:
    # compared the harness against src.mcp.server._refresh_dashboard_snapshot(),
    # added both candidate paths, and confirmed the full 45/45 sweep.
    candidate_snapshot_paths = [
        temp_home / ".elefante" / "data" / "dashboard_snapshot.json",
        temp_data_dir / "dashboard_snapshot.json",
    ]
    snapshot_path = next(
        (path for path in candidate_snapshot_paths if path.exists()),
        candidate_snapshot_paths[0],
    )
```