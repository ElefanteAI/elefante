# ─────────────────────────────────────────────────────────────────────────────
# NAME    : test_dmg_workflow_contract.py
# PURPOSE : Guard the optional signed macOS DMG from build through release selection.
# RUN     : pytest tests/test_dmg_workflow_contract.py -q
# WHEN    : After changes to the macOS DMG workflow or release-asset selector.
# ─────────────────────────────────────────────────────────────────────────────
"""Regression guards for the signed macOS DMG artifact handoff."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-binaries.yml"
SELECTOR = ROOT / "scripts" / "ci" / "select_release_assets.py"


def test_signed_dmg_has_an_explicit_optional_output_and_release_artifact_path():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    selector = SELECTOR.read_text(encoding="utf-8")

    sign_start = workflow.index("      - name: Sign and Notarize DMG")
    upload_start = workflow.index("      - name: Upload Installer Bundle", sign_start)
    sign_block = workflow[sign_start:upload_start]
    upload_block = workflow[workflow.index("      - name: Upload DMG", sign_start):]

    assert "id: sign_notarize" in sign_block
    assert "if: runner.os == 'macOS'" in sign_block
    assert 'echo "signed=false" >> "$GITHUB_OUTPUT"' in sign_block
    assert 'echo "signed=true" >> "$GITHUB_OUTPUT"' in sign_block
    assert "env.APPLE_DEVELOPER_ID" not in sign_block
    assert "steps.sign_notarize.outputs.signed == 'true'" in upload_block
    assert "name: elefante-macOS-installer-dmg" in upload_block
    assert "pattern: elefante-*-installer*" in workflow
    assert 'Path("artifacts/elefante-macOS-installer-dmg/Elefante-Installer.dmg")' in selector
