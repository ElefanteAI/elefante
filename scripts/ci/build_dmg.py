#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : build_dmg.py
# VERSION : 2.7.2
# CHANGED : 2026-04-16
# PURPOSE : Build a branded macOS .dmg installer from the Elefante installer
#           bundle zip. Produces a drag-to-install disk image with Elefante
#           branding, logo, tagline, and a link to www.elefante.ai.
# WHEN    : In CI after build_installer_bundle.py, or locally when validating
#           DMG packaging before release publication.
# USAGE   : python scripts/ci/build_dmg.py --bundle dist/elefante-installer-macOS.zip
#           [--output dist/Elefante-Installer.dmg] [--volume-name "Elefante Installer"]
# NOTES   : macOS only. Requires hdiutil (ships with macOS). Icon from
#           assets/icons/Elefante.icns. No code signing by default — pass
#           --sign "Developer ID Application: ..." when ready.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Build a branded macOS .dmg from the Elefante installer bundle."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ICON = ROOT_DIR / "assets" / "icons" / "Elefante.icns"
DEFAULT_LOGO_PNG = ROOT_DIR / "docs" / "assets" / "Elefante Logo 1024 white.png"
VOLUME_NAME = "Elefante Installer"
PRODUCT_URL = "https://www.elefante.ai"
TAGLINE = "Elefante never forgets."
WINDOW_WIDTH = 660
WINDOW_HEIGHT = 400


def validate_inputs(bundle_zip: Path, icon_path: Path) -> None:
    if not bundle_zip.exists():
        raise FileNotFoundError(f"Installer bundle not found: {bundle_zip}")
    if not icon_path.exists():
        raise FileNotFoundError(f"Icon not found: {icon_path}")
    if sys.platform != "darwin":
        raise RuntimeError("DMG builds require macOS (hdiutil)")


def extract_bundle(bundle_zip: Path, staging_dir: Path) -> Path:
    """Extract the installer bundle zip into the staging directory."""
    with zipfile.ZipFile(bundle_zip, "r") as zf:
        zf.extractall(staging_dir)

    # The bundle extracts to a single top-level dir like elefante-installer-macOS/
    entries = list(staging_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return staging_dir


def create_dmg_staging(bundle_dir: Path, staging_root: Path, icon_path: Path) -> Path:
    """Create the DMG content directory with a native .app GUI installer."""
    dmg_content = staging_root / "dmg_content"
    dmg_content.mkdir(parents=True, exist_ok=True)

    # Hidden installer payload
    installer_dest = dmg_content / ".elefante-installer"
    shutil.copytree(bundle_dir, installer_dest)
    install_sh = installer_dest / "install.sh"
    if install_sh.exists():
        install_sh.chmod(0o755)

    # ── Build the .app bundle (primary UX) ───────────────────────────────
    _create_installer_app(dmg_content, icon_path)

    # ── README ───────────────────────────────────────────────────────────
    readme_text = f"""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551                                                              \u2551
\u2551                     E L E F A N T E                          \u2551
\u2551                                                              \u2551
\u2551              {TAGLINE}                    \u2551
\u2551                                                              \u2551
\u2551                    {PRODUCT_URL}                     \u2551
\u2551                                                              \u2551
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d

INSTALLATION
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

  Double-click "Install Elefante" to begin.

  The installer window lets you:
    \u2022 Choose where Elefante is installed (default: ~/.elefante/app/current)
    \u2022 Watch real-time progress and logs
    \u2022 Retry if something fails

  Your data lives at: ~/.elefante/data/

  CLI alternative (GitHub download):
    ./install.sh

AFTER INSTALLATION
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

  Reload your IDE window (Cmd+Shift+P -> "Developer: Reload Window").
  A full IDE restart is NOT required.

LINKS
\u2550\u2550\u2550\u2550\u2550

  Website:   {PRODUCT_URL}
  GitHub:    https://github.com/ElefanteAI/elefante
  Releases:  https://github.com/ElefanteAI/elefante/releases

"""
    (dmg_content / "README.txt").write_text(readme_text, encoding="utf-8")

    # ── Website link ─────────────────────────────────────────────────────
    webloc_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>URL</key>
    <string>{PRODUCT_URL}</string>
</dict>
</plist>
"""
    (dmg_content / "www.elefante.ai.webloc").write_text(webloc_content, encoding="utf-8")

    return dmg_content


def _create_installer_app(dmg_content: Path, icon_path: Path) -> None:
    """Build an Install Elefante.app bundle inside the DMG staging directory.

    The .app is a minimal macOS application bundle whose executable is a
    bash launcher script. It finds python3, verifies tkinter, and opens
    the GUI installer (installer_gui.py). Falls back to Terminal if
    tkinter is unavailable.
    """
    app_dir = dmg_content / "Install Elefante.app"
    contents = app_dir / "Contents"
    macos_dir = contents / "MacOS"
    resources = contents / "Resources"
    macos_dir.mkdir(parents=True)
    resources.mkdir(parents=True)

    # ── Info.plist ──
    (contents / "Info.plist").write_text(_APP_INFO_PLIST, encoding="utf-8")

    # ── Launcher script ──
    launcher = macos_dir / "launcher"
    launcher.write_text(_APP_LAUNCHER_SCRIPT, encoding="utf-8")
    launcher.chmod(0o755)

    # ── GUI Python script ──
    gui_src = Path(__file__).resolve().parent / "installer_gui.py"
    if not gui_src.exists():
        raise FileNotFoundError(f"installer_gui.py not found at {gui_src}")
    shutil.copy2(gui_src, resources / "installer_gui.py")

    # ── Icon ──
    if icon_path.exists():
        shutil.copy2(icon_path, resources / "elefante.icns")


_APP_INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleName</key>
    <string>Install Elefante</string>
    <key>CFBundleIdentifier</key>
    <string>ai.elefante.installer</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>elefante</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
"""

_APP_LAUNCHER_SCRIPT = r"""#!/bin/bash
# ── Elefante Installer — .app launcher ───────────────────────────────────
# Finds python3, verifies tkinter, and opens the GUI installer.
# Falls back to a Terminal session if tkinter is unavailable.
set -euo pipefail

CONTENTS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DMG_ROOT="$(cd "$CONTENTS_DIR/../.." && pwd)"
INSTALLER_DIR="$DMG_ROOT/.elefante-installer"
GUI_SCRIPT="$CONTENTS_DIR/Resources/installer_gui.py"

# .app bundles don't inherit shell profile — add common Python locations
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"

# Find a Python 3 that can actually import tkinter.
# Homebrew Python often exists without the _tkinter module, which would
# incorrectly trigger the Terminal fallback even when another system Python works.
PYTHON=""
SEEN="|"
for candidate in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3 \
    "$(command -v python3 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        case "$SEEN" in
            *"|$candidate|"*)
                continue
                ;;
        esac
        SEEN="$SEEN$candidate|"

        if "$candidate" - <<'PY' >/dev/null 2>&1
import tkinter
PY
        then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "A Python 3 runtime with tkinter is required to show the Elefante installer window.\n\nDetected python3 interpreters on this Mac do not provide tkinter.\n\nInstall the python.org macOS build or use the CLI installer directly." buttons {"OK"} default button "OK" with icon stop with title "Elefante Installer"'
    exit 1
fi

if [ ! -f "$INSTALLER_DIR/install.sh" ]; then
    osascript -e "display dialog \"Installer payload not found.\n\nExpected:\n$INSTALLER_DIR/install.sh\" buttons {\"OK\"} default button \"OK\" with icon stop with title \"Elefante Installer\""
    exit 1
fi

exec "$PYTHON" "$GUI_SCRIPT" --installer-dir "$INSTALLER_DIR"
"""


def build_dmg_applescript(volume_name: str) -> str:
    """Generate AppleScript to style the DMG window."""
    return f"""
tell application "Finder"
    tell disk "{volume_name}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {{100, 100, {100 + WINDOW_WIDTH}, {100 + WINDOW_HEIGHT}}}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 80
        set text size of viewOptions to 13
        -- .app is the primary UX, prominently positioned
        set position of item "Install Elefante.app" of container window to {{170, 180}}
        set position of item "README.txt" of container window to {{500, 140}}
        set position of item "www.elefante.ai.webloc" of container window to {{500, 260}}
        close
    end tell
end tell
"""


def create_dmg(
    dmg_content: Path,
    output_path: Path,
    volume_name: str,
    icon_path: Path,
    sign_identity: str | None = None,
) -> Path:
    """Create the .dmg file using hdiutil."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DMG
    if output_path.exists():
        output_path.unlink()

    # Create a temporary writable DMG first
    temp_dmg = output_path.with_suffix(".temp.dmg")
    if temp_dmg.exists():
        temp_dmg.unlink()

    # Calculate size: content size + 20MB headroom
    content_size_mb = sum(
        f.stat().st_size for f in dmg_content.rglob("*") if f.is_file()
    ) // (1024 * 1024) + 20

    # Create writable DMG
    subprocess.run(
        [
            "hdiutil", "create",
            "-srcfolder", str(dmg_content),
            "-volname", volume_name,
            "-fs", "HFS+",
            "-fsargs", "-c c=64,a=16,e=16",
            "-format", "UDRW",
            "-size", f"{content_size_mb}m",
            str(temp_dmg),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Mount the writable DMG to apply styling
    mount_result = subprocess.run(
        ["hdiutil", "attach", "-readwrite", "-noverify", str(temp_dmg)],
        check=True,
        capture_output=True,
        text=True,
    )

    # Find the mount point
    mount_point = None
    for line in mount_result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 3:
            mount_point = parts[-1].strip()

    if not mount_point:
        raise RuntimeError("Could not determine DMG mount point")

    try:
        # Set volume icon
        volume_icon_dest = Path(mount_point) / ".VolumeIcon.icns"
        shutil.copy2(icon_path, volume_icon_dest)

        # Set the has-custom-icon attribute on the volume
        subprocess.run(
            ["SetFile", "-a", "C", mount_point],
            check=False,  # SetFile may not be available without Xcode CLI tools
            capture_output=True,
        )

        # Apply AppleScript window styling
        applescript = build_dmg_applescript(volume_name)
        subprocess.run(
            ["osascript", "-e", applescript],
            check=False,  # Non-fatal if Finder scripting fails in CI
            capture_output=True,
            text=True,
        )

    finally:
        # Unmount
        subprocess.run(
            ["hdiutil", "detach", mount_point, "-quiet"],
            check=False,
            capture_output=True,
        )

    # Convert to compressed read-only DMG
    subprocess.run(
        [
            "hdiutil", "convert",
            str(temp_dmg),
            "-format", "UDZO",
            "-imagekey", "zlib-level=9",
            "-o", str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Clean up temp DMG
    temp_dmg.unlink(missing_ok=True)

    # Code signing (optional)
    if sign_identity:
        subprocess.run(
            ["codesign", "-s", sign_identity, str(output_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Signed DMG with: {sign_identity}")

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a branded macOS DMG installer")
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to the installer bundle zip (e.g. dist/elefante-installer-macOS.zip)",
    )
    parser.add_argument(
        "--output",
        help="Output DMG path (default: dist/Elefante-Installer.dmg)",
    )
    parser.add_argument(
        "--volume-name",
        default=VOLUME_NAME,
        help=f"DMG volume name (default: {VOLUME_NAME})",
    )
    parser.add_argument(
        "--icon",
        default=str(DEFAULT_ICON),
        help="Path to .icns icon file",
    )
    parser.add_argument(
        "--sign",
        default=None,
        help="Code signing identity (e.g. 'Developer ID Application: ...')",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_zip = Path(args.bundle).expanduser().resolve()
    icon_path = Path(args.icon).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else ROOT_DIR / "dist" / "Elefante-Installer.dmg"
    )

    validate_inputs(bundle_zip, icon_path)

    with tempfile.TemporaryDirectory(prefix="elefante-dmg-") as tmpdir:
        staging_root = Path(tmpdir)

        print(f"Extracting bundle: {bundle_zip}")
        bundle_dir = extract_bundle(bundle_zip, staging_root / "extract")

        print("Staging DMG content...")
        dmg_content = create_dmg_staging(bundle_dir, staging_root, icon_path)

        print(f"Building DMG: {output_path}")
        result = create_dmg(
            dmg_content,
            output_path,
            args.volume_name,
            icon_path,
            sign_identity=args.sign,
        )

        size_mb = result.stat().st_size / (1024 * 1024)
        print(f"Wrote DMG: {result} ({size_mb:.1f} MB)")
        print(f"  Volume: {args.volume_name}")
        print(f"  Tagline: {TAGLINE}")
        print(f"  URL: {PRODUCT_URL}")

        if not args.sign:
            print()
            print("WARNING: DMG is unsigned. macOS Gatekeeper will block downloaded copies.")
            print("  Users will see: 'cannot be opened because the developer cannot be verified'")
            print("  For distribution: pass --sign 'Developer ID Application: ...'")
            print("  Then notarize: xcrun notarytool submit <dmg> --apple-id ... --wait")
            print("  Then staple:   xcrun stapler staple <dmg>")
            print("  This DMG is safe for local development and testing only.")


if __name__ == "__main__":
    main()
