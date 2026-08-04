# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_release_authorization.py
# VERSION : 2.12.1
# CHANGED : 2026-08-04
# PROVES  : A reviewed release-request marker validates the package version,
#           creates an immutable tag, and explicitly dispatches publication.
# RUN     : pytest tests/test_release_authorization.py -v
# WHEN    : After changes to .github/workflows/authorize-release.yml
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_authorized_release_request_is_validated_and_dispatched() -> None:
    workflow = (ROOT / ".github/workflows/authorize-release.yml").read_text(
        encoding="utf-8"
    )
    marker = ROOT / ".github/release-requests/v2.12.1"
    package = (ROOT / "src/__init__.py").read_text(encoding="utf-8")
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', package)

    assert marker.is_file()
    assert version_match is not None
    assert marker.name == f"v{version_match.group(1)}"
    assert "branches:\n      - main" in workflow
    assert '".github/release-requests/v*.*.*"' in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert 'Path("src/__init__.py")' in workflow
    assert "from src import __version__" not in workflow
    assert "python scripts/ci/bump_version.py --check" in workflow
    assert 'python scripts/ci/render_release_notes.py "$tag"' in workflow
    assert 'git tag -a "$tag" "$GITHUB_SHA"' in workflow
    assert 'git push origin "refs/tags/$tag"' in workflow
    assert 'gh workflow run build-binaries.yml --ref "$RELEASE_TAG"' in workflow
    assert "git tag -f" not in workflow
    assert "git push --force" not in workflow
