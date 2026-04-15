# Annotated Excerpt: src/mcp/server.py

```python
# Snapshot was just refreshed - restart so the new data is served immediately.
self.logger.info("Dashboard restart requested: killing existing server process.")
_kill_existing()
already_running = False
DASHBOARD_STARTED = False

if not already_running:
    subprocess.Popen(
        [sys.executable, "-m", "src.dashboard.server"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(self._get_project_root()),
    )
    self.logger.info(f"Dashboard server started via subprocess on port {port}")

    # Supposed to do:
    # wait for Uvicorn to bind before opening the browser.
    #
    # Previous failure:
    # browser launch happened before readiness, which produced a blank page.
    #
    # Debugging already done:
    # fixed by adding readiness polling and forced restart on refresh; guarded
    # in tests/test_dashboard_serializer.py.
    ready = _wait_for_ready(max_wait=15.0)
    if not ready:
        self.logger.warning("Dashboard server did not become ready within 15s.")
else:
    ready = True
    self.logger.info(f"Dashboard already running on port {port}")

# Supposed to do:
# only open the browser once the dashboard is confirmed ready.
#
# Current status:
# working. This was BUG-003 and is no longer the blocker.
if ready:
    try:
        webbrowser.open(url)
        message = f"Dashboard opened at {url}"
    except Exception as e:
        message = f"Dashboard server running at {url}, but failed to open browser: {e}"


async def _refresh_dashboard_snapshot(self) -> Dict[str, Any]:
    import os
    from src.utils.config import DATA_DIR

    orchestrator = await self._get_orchestrator()
    memories = await orchestrator.vector_store.get_all(limit=1000)

    # ... unrelated node/edge serialization omitted ...

    # Supposed to do:
    # write the live dashboard snapshot to the runtime data directory.
    #
    # Why it mattered:
    # the self-protocol originally assumed a simpler temp-data path, but the
    # real runtime resolves DATA_DIR from HOME at import time.
    #
    # Debugging already done:
    # the verifier now accepts both candidate paths and no longer misclassifies
    # this as a dashboard regression.
    output_path = str(DATA_DIR / "dashboard_snapshot.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)


async def _handle_get_elefante_dashboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
    refresh = bool(args.get("refresh", False))

    # Supposed to do:
    # prevent refresh=true from reading live data when Elefante Mode is disabled.
    #
    # Current status:
    # working, and already documented correctly in docs/technical/spec-tools.md.
    if refresh:
        if not self.mode_manager.is_enabled:
            return self.mode_manager.get_disabled_response("elefante-DashboardOpen")
        refresh_result = await self._refresh_dashboard_snapshot()
```