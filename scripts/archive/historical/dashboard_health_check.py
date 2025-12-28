#!/usr/bin/env python3
"""Dashboard health check (no DB access required).

Checks that the dashboard server responds and that API endpoints return
the expected JSON shapes.

Usage:
  python scripts/dashboard_health_check.py --port 8000
  python scripts/dashboard_health_check.py --url http://127.0.0.1:8001
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict


def _get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description="Dashboard health check")
    p.add_argument("--url", type=str, default=None, help="Base URL, e.g. http://127.0.0.1:8000")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    base = args.url.rstrip("/") if args.url else f"http://127.0.0.1:{int(args.port)}"

    try:
        stats = _get_json(f"{base}/api/stats")
        graph = _get_json(f"{base}/api/graph")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[error] cannot reach dashboard at {base}: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[error] invalid response from dashboard at {base}: {e}", file=sys.stderr)
        return 2

    ok = True
    if "snapshot" not in stats and "vector_store" not in stats:
        print("[warn] /api/stats shape unexpected (missing snapshot/vector_store)", file=sys.stderr)
        ok = False

    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        print("[warn] /api/graph missing nodes[] or edges[]", file=sys.stderr)
        ok = False

    print(
        f"[ok] dashboard reachable: {base} nodes={len(graph.get('nodes', []))} edges={len(graph.get('edges', []))}",
        file=sys.stderr,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
