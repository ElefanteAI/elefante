#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : installer_gui.py
# PURPOSE : Native macOS tkinter GUI for the Elefante installer. Launched from
#           the DMG .app bundle. Shows branded window with install path picker,
#           real-time progress bar, and scrollable output log.
# WHEN    : Launched automatically when the user double-clicks "Install Elefante"
#           inside the mounted DMG.
# NOTES   : Zero external dependencies — stdlib + tkinter only. Falls back to
#           Terminal via osascript if tkinter is unavailable.
# ─────────────────────────────────────────────────────────────────────────────
"""Elefante Installer — Native macOS GUI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path


INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"
VALID_PACKAGE_OPERATIONS = {"install", "repair", "update", "rollback"}


def default_install_path() -> Path:
    return Path.home() / ".elefante" / "app" / "current"


def default_data_path() -> Path:
    return Path.home() / ".elefante" / "data"


def default_backup_path() -> Path:
    return Path.home() / ".elefante" / "backups"


def read_managed_backup_path(
    installer_dir: Path,
    install_root: str | Path | None,
    *,
    runner=subprocess.run,
) -> Path | None:
    """Ask the package owner which single backup directory it will use."""
    bootstrap = Path(installer_dir) / "scripts" / "setup" / "bootstrap_release_bundle.py"
    if not bootstrap.is_file():
        return None
    try:
        result = runner(
            [
                sys.executable,
                str(bootstrap),
                "--bundle-root",
                str(installer_dir),
                "--install-root",
                str(normalize_install_root(install_root)),
                "--print-managed-backup-path",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, TypeError):
        return None
    raw_path = result.stdout.strip()
    if result.returncode != 0 or not raw_path or "\n" in raw_path:
        return None
    candidate = Path(raw_path).expanduser()
    return candidate if candidate.is_absolute() else None


def normalize_install_root(install_root: str | Path | None) -> Path:
    raw_path = str(install_root or "").strip()
    if not raw_path:
        return default_install_path()
    return Path(raw_path).expanduser()


def read_package_operation(
    installer_dir: Path,
    install_root: str | Path | None,
    *,
    runner=subprocess.run,
) -> dict[str, object] | None:
    """Ask the package transaction owner for one read-only operation description."""
    bootstrap = Path(installer_dir) / "scripts" / "setup" / "bootstrap_release_bundle.py"
    if not bootstrap.is_file():
        return None
    try:
        result = runner(
            [
                sys.executable,
                str(bootstrap),
                "--bundle-root",
                str(installer_dir),
                "--install-root",
                str(normalize_install_root(install_root)),
                "--describe-operation",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
        return None
    if (
        result.returncode != 0
        or not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("operation") not in VALID_PACKAGE_OPERATIONS
    ):
        return None
    if payload.get("operation") == "rollback" and not isinstance(
        payload.get("confirmation_token"), str
    ):
        return None
    return payload


def read_package_uninstall(
    installer_dir: Path,
    install_root: str | Path | None,
    *,
    runner=subprocess.run,
) -> dict[str, object] | None:
    """Ask the package owner for one exact read-only uninstall plan."""
    bootstrap = Path(installer_dir) / "scripts" / "setup" / "bootstrap_release_bundle.py"
    if not bootstrap.is_file():
        return None
    try:
        result = runner(
            [
                sys.executable,
                str(bootstrap),
                "--bundle-root",
                str(installer_dir),
                "--install-root",
                str(normalize_install_root(install_root)),
                "--describe-uninstall",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
        return None
    if (
        result.returncode != 0
        or not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("operation") != "uninstall"
        or payload.get("available") is not True
        or not isinstance(payload.get("confirmation_token"), str)
        or payload.get("data_effect") != "preserved"
    ):
        return None
    return payload


def installer_operation_copy(
    install_root: str | Path | None,
    description: dict[str, object] | None = None,
) -> dict[str, str]:
    """Return concise customer language for the package's exact operation."""
    fallback = "repair" if normalize_install_root(install_root).is_dir() else "install"
    operation = str((description or {}).get("operation") or fallback)
    if operation not in VALID_PACKAGE_OPERATIONS:
        operation = fallback
    verbs = {
        "install": "Install",
        "repair": "Repair",
        "update": "Update",
        "rollback": "Roll Back",
    }
    completion = {
        "install": "Installation verified — projects, Recall cleanup, and local backup are ready.",
        "repair": "Repair verified — Elefante, agent connection, and Recall are ready.",
        "update": "Update verified — Elefante, agent connection, and Recall are ready.",
        "rollback": "Code rollback verified — Elefante, agent connection, and Recall are ready.",
    }
    verb = verbs[operation]
    retained = (description or {}).get("retained_rollback")
    retained = retained if isinstance(retained, dict) else {}
    return {
        "operation": operation,
        "verb": verb,
        "title": f"{verb} Elefante",
        "ready": f"Ready to {verb.lower()}",
        "starting": f"Starting {verb.lower()}…",
        "complete": completion[operation],
        "confirmation_token": str((description or {}).get("confirmation_token") or ""),
        "current_version": str((description or {}).get("current_version") or ""),
        "target_version": str((description or {}).get("target_version") or ""),
        "retained_rollback_available": (
            "true" if retained.get("available") is True else "false"
        ),
        "retained_rollback_token": str(retained.get("confirmation_token") or ""),
        "retained_current_version": str(retained.get("current_version") or ""),
        "retained_target_version": str(retained.get("target_version") or ""),
    }


def build_project_specs(paths: list[str | Path]) -> list[str]:
    """Build stable NAME=ABSOLUTE_PATH values from customer-selected folders."""
    selected: list[Path] = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        if path not in selected:
            selected.append(path)
    used_names: set[str] = set()
    specs: list[str] = []
    for path in selected:
        base = path.name.replace("=", "-").strip() or "Project"
        base = base[:90]
        name = base
        suffix = 2
        while name.casefold() in used_names:
            name = f"{base} {suffix}"
            suffix += 1
        used_names.add(name.casefold())
        specs.append(f"{name}={path}")
    return specs


def build_install_artifact_paths(install_root: str | Path | None) -> dict[str, Path]:
    install_root = normalize_install_root(install_root)
    return {
        "log": install_root / INSTALL_LOG_FILE_NAME,
        "status": install_root / INSTALL_STATUS_FILE_NAME,
        "summary": install_root / INSTALL_SUMMARY_FILE_NAME,
    }


def render_install_artifact_paths(install_root: str | Path | None) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Persistent installer files:",
        f"Summary file: {paths['summary']}",
        f"Status file: {paths['status']}",
        f"Log file: {paths['log']}",
    ]


def render_failed_install_guidance(install_root: str | Path | None) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Read these persisted installer files in order:",
        f"1. Summary file: {paths['summary']}",
        f"2. Status file: {paths['status']}",
        f"3. Log file: {paths['log']}",
    ]


def _status_from_stage_line(line: str) -> str | None:
    if line.startswith("[Step"):
        match = re.match(r"\[Step \S+\]\s*(.*?)\.{0,3}$", line)
        if match:
            return f"Installing: {match.group(1)}"
    if "PRE-FLIGHT" in line:
        return "Running pre-flight checks…"
    if "Purging" in line:
        return "Purging stale bytecode…"
    if "MCP handshake" in line:
        return "Verifying MCP handshake…"
    return None


def process_stage_marker(line: str, seen_markers: set[str]) -> tuple[int, str | None]:
    for marker in STAGE_MARKERS:
        if marker in line and marker not in seen_markers:
            seen_markers.add(marker)
            return 1, _status_from_stage_line(line)
    return 0, None

# ── Stage markers parsed from installer stdout for progress tracking ─────
STAGE_MARKERS = [
    "Purging bytecode",
    "PRE-FLIGHT CHECKS",
    "[Step 1]",
    "[Step 2]",
    "[Step 2a]",
    "[Step 3]",
    "[Step 3a]",
    "[Step 4]",
    "[Step 4a]",
    "[Step 5]",
    "Verifying MCP handshake",
    "[Step 5b]",
    "[Step 5c]",
]
TOTAL_STAGES = len(STAGE_MARKERS)


# ── Helpers that work without tkinter ────────────────────────────────────

def _osascript_alert(title: str, message: str, icon: str = "stop") -> None:
    subprocess.run(
        ["osascript", "-e",
         f'display dialog "{message}" buttons {{"OK"}} default button "OK" '
         f'with icon {icon} with title "{title}"'],
        check=False,
    )


def _fallback_terminal(installer_dir: Path) -> None:
    """If tkinter is unavailable, ask for path via osascript then open Terminal."""
    default = str(default_install_path())
    result = subprocess.run(
        ["osascript", "-e",
         f'set p to text returned of (display dialog '
         f'"Where should Elefante be installed?" '
         f'default answer "{default}" '
         f'with title "Elefante Installer" '
         f'buttons {{"Cancel", "Install"}} default button "Install")\nreturn p'],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return
    install_path = result.stdout.strip() or default
    cmd = f'"{installer_dir / "install.sh"}" --install-root "{install_path}" --venv-mode fresh --verbose'
    subprocess.run(
        ["osascript", "-e",
         f'tell application "Terminal"\n  activate\n  do script "{cmd}"\nend tell'],
        check=False,
    )


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

    parser = argparse.ArgumentParser(description="Elefante Installer GUI")
    parser.add_argument("--installer-dir", required=True)
    args = parser.parse_args()

    installer_dir = Path(args.installer_dir)
    if not (installer_dir / "install.sh").exists():
        _osascript_alert("Elefante", f"Installer payload not found.\\n\\n{installer_dir}")
        sys.exit(1)

    try:
        import tkinter as tk  # noqa: F401
    except ImportError:
        _osascript_alert(
            "Elefante",
            "Python tkinter is not available.\\nFalling back to Terminal installer.",
            "caution",
        )
        _fallback_terminal(installer_dir)
        sys.exit(0)

    root = tk.Tk()
    InstallerApp(root, installer_dir)
    root.mainloop()


# ── GUI ──────────────────────────────────────────────────────────────────

class InstallerApp:
    """Native macOS installer window."""

    def __init__(self, root, installer_dir: Path):
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        self.tk = tk
        self.ttk = ttk
        self.scrolledtext = scrolledtext

        self.root = root
        self.installer_dir = installer_dir
        self.process: subprocess.Popen | None = None
        self.installing = False
        self.stages_hit = 0
        self.seen_markers: set[str] = set()
        self.cancel_requested = False
        self.retry_retained_rollback = False
        self.retry_uninstall = False
        self.project_paths: list[Path] = []

        self.default_install_path = default_install_path()
        self.default_data_path = default_data_path()
        self.active_operation = self._read_operation_copy(self.default_install_path)
        self.managed_backup_path = (
            read_managed_backup_path(
                self.installer_dir,
                self.default_install_path,
            )
            or default_backup_path()
        )
        self.active_uninstall_description = read_package_uninstall(
            self.installer_dir,
            self.default_install_path,
        )
        self.badge_image = None

        # Keep colors limited to log/status accents. The main layout uses native
        # ttk widgets to avoid Aqua rendering regressions.
        self.C = dict(
            accent="#0f766e",
            ok="#15803d",
            err="#b91c1c",
            warn="#a16207",
            log_bg="#f7f8fa",
            log_fg="#243041",
        )

        self.root.title("Install Elefante")

        # Center on screen
        w, h = 920, 920
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(40, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(820, 780)

        # Bring to front
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))

        try:
            ttk.Style().theme_use("aqua")
        except Exception:
            pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._configure_styles()
        self._build_ui()

    def _configure_styles(self):
        style = self.ttk.Style(self.root)
        style.configure("Title.TLabel", font=("SF Pro Display", 28, "bold"))
        style.configure("Subtitle.TLabel", font=("SF Pro Text", 13))
        style.configure("Section.TLabelframe.Label", font=("SF Pro Text", 12, "bold"))
        style.configure("SectionTitle.TLabel", font=("SF Pro Text", 12, "bold"))
        style.configure("Body.TLabel", font=("SF Pro Text", 11))
        style.configure("Mono.TLabel", font=("Menlo", 11))
        style.configure("Install.TButton", font=("SF Pro Text", 13, "bold"))
        style.configure("Muted.TLabel", font=("SF Pro Text", 11), foreground="#5b6472")
        style.configure("Success.TLabel", font=("SF Pro Text", 11), foreground=self.C["ok"])
        style.configure("Error.TLabel", font=("SF Pro Text", 11), foreground=self.C["err"])

    def _load_badge_image(self):
        candidates = [
            Path(__file__).resolve().with_name("installer-badge.png"),
            Path(__file__).resolve().parents[2] / "assets" / "icons" / "Elefante-installer-badge.png",
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                image = self.tk.PhotoImage(file=str(candidate))
            except Exception:
                continue
            if image.width() > 160:
                divisor = max(1, image.width() // 160)
                image = image.subsample(divisor, divisor)
            self.badge_image = image
            return image
        return None

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        tk = self.tk
        ttk = self.ttk
        outer = ttk.Frame(self.root, padding=(28, 24, 28, 24))
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(8, weight=1)

        hero = ttk.Frame(outer)
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(1, weight=1)

        badge = self._load_badge_image()
        if badge is not None:
            ttk.Label(hero, image=badge).grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 18))

        self.operation_title_var = tk.StringVar(value=self.active_operation["title"])
        ttk.Label(hero, textvariable=self.operation_title_var, style="Title.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(
            hero,
            text="Private local memory for your AI. Stored on this Mac.",
            style="Subtitle.TLabel",
            wraplength=640,
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))

        hero_meta = ttk.Frame(hero)
        hero_meta.grid(row=2, column=1, sticky="w", pady=(12, 0))
        ttk.Label(hero_meta, text="Private by default", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(hero_meta, text="Recommended path", style="Body.TLabel").grid(row=0, column=1, sticky="w", padx=(18, 0))
        ttk.Label(hero_meta, text="Live install log", style="Body.TLabel").grid(row=0, column=2, sticky="w", padx=(18, 0))

        ttk.Separator(outer, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="ew", pady=(18, 18))

        summary = ttk.LabelFrame(outer, text="Recommended setup", padding=(18, 14), style="Section.TLabelframe")
        summary.grid(row=2, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)
        ttk.Label(
            summary,
            text="For most people, keep the default location. Elefante installs into a hidden folder in your home directory, not into Documents.",
            style="Body.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(summary, text=f"App files:  {self.default_install_path}", style="Mono.TLabel").grid(
            row=1, column=0, sticky="w", pady=(10, 2)
        )
        ttk.Label(summary, text=f"Data:       {self.default_data_path}", style="Mono.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        self.backup_path_var = tk.StringVar(
            value=f"Backups:    {self.managed_backup_path}"
        )
        ttk.Label(summary, textvariable=self.backup_path_var, style="Mono.TLabel").grid(
            row=3, column=0, sticky="w", pady=(2, 0)
        )

        location = ttk.LabelFrame(outer, text="Install location", padding=(18, 14), style="Section.TLabelframe")
        location.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        location.columnconfigure(0, weight=1)
        ttk.Label(
            location,
            text="Change this only if you want the app files somewhere else.",
            style="Body.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")

        row = ttk.Frame(location)
        row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        row.columnconfigure(0, weight=1)

        self.path_var = tk.StringVar(value=str(self.default_install_path))
        self.path_var.trace_add("write", self._on_path_changed)
        self.path_entry = ttk.Entry(row, textvariable=self.path_var, font=("Menlo", 12))
        self.path_entry.grid(row=0, column=0, sticky="ew")

        self.browse_btn = ttk.Button(row, text="Browse\u2026", command=self._browse)
        self.browse_btn.grid(row=0, column=1, padx=(10, 0))

        ttk.Label(
            location,
            text="Memories stay local on this Mac. Installation logs are written into the chosen install folder.",
            style="Muted.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.projects_frame = ttk.LabelFrame(
            outer,
            text="Choose where Elefante may remember",
            padding=(18, 14),
            style="Section.TLabelframe",
        )
        self.projects_frame.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        self.projects_frame.columnconfigure(0, weight=1)
        ttk.Label(
            self.projects_frame,
            text=(
                "Select at least one real project folder. Each folder receives an "
                "isolated memory scope; Elefante never scans or changes project files."
            ),
            style="Body.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")
        self.project_summary_var = tk.StringVar(value="No project folders selected")
        self.project_summary_label = ttk.Label(
            self.projects_frame,
            textvariable=self.project_summary_var,
            style="Error.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        )
        self.project_summary_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
        project_actions = ttk.Frame(self.projects_frame)
        project_actions.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.add_project_btn = ttk.Button(
            project_actions,
            text="Add Project Folder…",
            command=self._add_project,
        )
        self.add_project_btn.grid(row=0, column=0, sticky="w")
        self.remove_project_btn = ttk.Button(
            project_actions,
            text="Remove Last",
            command=self._remove_project,
        )
        self.remove_project_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(
            project_actions,
            text="Disposable Recall and a verified local backup run automatically.",
            style="Success.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(14, 0))

        recovery = ttk.LabelFrame(outer, text="Recovery files", padding=(18, 14), style="Section.TLabelframe")
        recovery.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        recovery.columnconfigure(0, weight=1)
        ttk.Label(
            recovery,
            text="If installation fails or you stop this window, these files survive inside the chosen install folder.",
            style="Body.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")

        self.summary_path_var = tk.StringVar()
        self.status_path_var = tk.StringVar()
        self.log_path_var = tk.StringVar()

        ttk.Label(recovery, textvariable=self.summary_path_var, style="Mono.TLabel", wraplength=760, justify=tk.LEFT).grid(
            row=1, column=0, sticky="w", pady=(10, 2)
        )
        ttk.Label(recovery, textvariable=self.status_path_var, style="Mono.TLabel", wraplength=760, justify=tk.LEFT).grid(
            row=2, column=0, sticky="w", pady=(0, 2)
        )
        ttk.Label(recovery, textvariable=self.log_path_var, style="Mono.TLabel", wraplength=760, justify=tk.LEFT).grid(
            row=3, column=0, sticky="w"
        )

        recovery_actions = ttk.Frame(recovery)
        recovery_actions.grid(row=4, column=0, sticky="w", pady=(10, 0))

        ttk.Button(recovery_actions, text="Open Summary", command=self._open_summary_file).grid(row=0, column=0, sticky="w")
        ttk.Button(recovery_actions, text="Open Status", command=self._open_status_file).grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Button(recovery_actions, text="Open Log", command=self._open_log_file).grid(row=0, column=2, sticky="w", padx=(10, 0))
        ttk.Button(recovery_actions, text="Open Install Folder", command=self._open_install_folder).grid(row=0, column=3, sticky="w", padx=(10, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=6, column=0, sticky="ew", pady=(16, 10))
        actions.columnconfigure(3, weight=1)

        self.install_btn = ttk.Button(
            actions,
            text=self.active_operation["title"],
            command=self._start_install,
            style="Install.TButton",
        )
        self.install_btn.grid(row=0, column=0, sticky="w")

        self.rollback_btn = ttk.Button(
            actions,
            text="Roll Back Previous Version",
            command=self._start_retained_rollback,
        )
        self.rollback_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))
        if self.active_operation["retained_rollback_available"] != "true":
            self.rollback_btn.grid_remove()

        self.uninstall_btn = ttk.Button(
            actions,
            text="Uninstall Elefante",
            command=self._start_uninstall,
        )
        self.uninstall_btn.grid(row=0, column=2, sticky="w", padx=(10, 0))
        if self.active_uninstall_description is None:
            self.uninstall_btn.grid_remove()

        ttk.Label(
            actions,
            text="The installer will show real-time progress below and can be retried if something fails.",
            style="Muted.TLabel",
            wraplength=560,
            justify=tk.LEFT,
        ).grid(row=0, column=3, sticky="w", padx=(18, 0))

        progress_wrap = ttk.Frame(outer)
        progress_wrap.grid(row=7, column=0, sticky="ew")
        progress_wrap.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(progress_wrap, variable=self.progress_var, maximum=TOTAL_STAGES)
        self.progress.grid(row=0, column=0, sticky="ew")

        self.status_label = ttk.Label(
            progress_wrap,
            text=self.active_operation["ready"],
            style="Muted.TLabel",
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

        log_frame = ttk.LabelFrame(outer, text="Installer output", padding=(12, 12), style="Section.TLabelframe")
        log_frame.grid(row=8, column=0, sticky="nsew", pady=(16, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.output = self.scrolledtext.ScrolledText(
            log_frame,
            font=("Menlo", 10),
            bg=self.C["log_bg"],
            fg=self.C["log_fg"],
            insertbackground=self.C["log_fg"],
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=12,
            state=tk.DISABLED,
            wrap=tk.WORD,
            height=14,
        )
        self.output.grid(row=0, column=0, sticky="nsew")

        self.output.tag_configure("ok", foreground=self.C["ok"])
        self.output.tag_configure("err", foreground=self.C["err"])
        self.output.tag_configure("warn", foreground=self.C["warn"])
        self.output.tag_configure("step", foreground=self.C["log_fg"], font=("Menlo", 10, "bold"))
        self.output.tag_configure("hdr", foreground=self.C["accent"], font=("Menlo", 10, "bold"))

        self._refresh_artifact_paths()
        self._refresh_project_summary()
        self._append("Live installer output will appear here once installation starts.", "hdr")

    # ── Actions ──────────────────────────────────────────────────────────

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(
            title="Choose Elefante Install Location",
            initialdir=str(Path(self.path_var.get()).parent),
        )
        if path:
            self.path_var.set(path)

    def _add_project(self):
        from tkinter import filedialog

        path = filedialog.askdirectory(title="Choose a Project Folder")
        if path:
            selected = Path(path).expanduser().resolve()
            if selected not in self.project_paths:
                self.project_paths.append(selected)
            self._refresh_project_summary()

    def _remove_project(self):
        if self.project_paths:
            self.project_paths.pop()
        self._refresh_project_summary()

    def _refresh_project_summary(self):
        is_install = self.active_operation["operation"] == "install"
        if is_install:
            self.projects_frame.grid()
        else:
            self.projects_frame.grid_remove()
        if self.project_paths:
            visible = [f"• {path.name} — {path}" for path in self.project_paths[:3]]
            if len(self.project_paths) > 3:
                visible.append(f"+ {len(self.project_paths) - 3} more")
            self.project_summary_var.set("\n".join(visible))
            self.project_summary_label.configure(style="Mono.TLabel")
        else:
            self.project_summary_var.set("No project folders selected")
            self.project_summary_label.configure(style="Error.TLabel")
        enabled = not self.installing and is_install
        self.add_project_btn.configure(state=self.tk.NORMAL if enabled else self.tk.DISABLED)
        self.remove_project_btn.configure(
            state=(
                self.tk.NORMAL
                if enabled and self.project_paths
                else self.tk.DISABLED
            )
        )
        self.install_btn.configure(
            state=(
                self.tk.NORMAL
                if not self.installing and (not is_install or self.project_paths)
                else self.tk.DISABLED
            )
        )

    def _on_path_changed(self, *_args):
        self._refresh_artifact_paths()
        self._refresh_operation_copy()

    def _current_install_root(self) -> Path:
        return normalize_install_root(self.path_var.get())

    def _current_artifact_paths(self) -> dict[str, Path]:
        return build_install_artifact_paths(self._current_install_root())

    def _read_operation_copy(self, install_root: str | Path) -> dict[str, str]:
        description = read_package_operation(self.installer_dir, install_root)
        return installer_operation_copy(install_root, description)

    def _refresh_artifact_paths(self):
        paths = self._current_artifact_paths()
        self.summary_path_var.set(f"Summary: {paths['summary']}")
        self.status_path_var.set(f"Status:  {paths['status']}")
        self.log_path_var.set(f"Log:     {paths['log']}")

    def _refresh_operation_copy(self):
        if self.installing:
            return
        self.active_operation = self._read_operation_copy(self._current_install_root())
        self.managed_backup_path = (
            read_managed_backup_path(
                self.installer_dir,
                self._current_install_root(),
            )
            or default_backup_path()
        )
        self.backup_path_var.set(f"Backups:    {self.managed_backup_path}")
        self.active_uninstall_description = read_package_uninstall(
            self.installer_dir,
            self._current_install_root(),
        )
        self.operation_title_var.set(self.active_operation["title"])
        self.install_btn.configure(text=self.active_operation["title"])
        if self.active_operation["retained_rollback_available"] == "true":
            target = self.active_operation["retained_target_version"]
            self.rollback_btn.configure(
                text=f"Roll Back to {target}" if target else "Roll Back Previous Version",
                state=self.tk.NORMAL,
            )
            self.rollback_btn.grid()
        else:
            self.rollback_btn.grid_remove()
        if self.active_uninstall_description is not None:
            self.uninstall_btn.configure(state=self.tk.NORMAL)
            self.uninstall_btn.grid()
        else:
            self.uninstall_btn.grid_remove()
        self._refresh_project_summary()
        self._set_status(self.active_operation["ready"], "muted")

    def _open_path_or_parent(self, path: Path, missing_message: str):
        target = path if path.exists() else path.parent
        subprocess.run(["open", str(target)], check=False)
        if not path.exists():
            self._set_status(missing_message, "muted")
            self._append(f"Not created yet: {path}", "warn")

    def _open_summary_file(self):
        self._open_path_or_parent(
            self._current_artifact_paths()["summary"],
            "Summary file will be written during installation.",
        )

    def _open_status_file(self):
        self._open_path_or_parent(
            self._current_artifact_paths()["status"],
            "Status file will be written during installation.",
        )

    def _open_log_file(self):
        self._open_path_or_parent(
            self._current_artifact_paths()["log"],
            "Log file will be written during installation.",
        )

    def _open_install_folder(self):
        install_root = self._current_install_root()
        target = install_root if install_root.exists() else install_root.parent
        subprocess.run(["open", str(target)], check=False)

    def _confirm_code_rollback(self, current_version: str, target_version: str) -> bool:
        from tkinter import messagebox

        return messagebox.askokcancel(
            "Roll Back Elefante?",
            (
                f"Product code will change from {current_version} to {target_version}.\n\n"
                "Your memories will not be restored or reversed. Elefante will create "
                "a verified data backup first and restore the current code automatically "
                "if the target fails verification."
            ),
            icon="warning",
        )

    def _begin_operation(self, install_path: str, cmd: list[str]):
        self.installing = True
        self.retry_retained_rollback = "--rollback-retained" in cmd
        self.retry_uninstall = "--uninstall" in cmd
        self.stages_hit = 0
        self.seen_markers.clear()
        self.cancel_requested = False
        self.progress_var.set(0)
        self.install_btn.configure(state=self.tk.DISABLED)
        self.rollback_btn.configure(state=self.tk.DISABLED)
        self.uninstall_btn.configure(state=self.tk.DISABLED)
        self.browse_btn.configure(state=self.tk.DISABLED)
        self.path_entry.configure(state=self.tk.DISABLED)
        self.add_project_btn.configure(state=self.tk.DISABLED)
        self.remove_project_btn.configure(state=self.tk.DISABLED)

        self._set_status(self.active_operation["starting"], "muted")
        if self.retry_uninstall:
            self._append("A verified backup will be created before app removal.", "hdr")
            self._append("Memories remain local and available for reinstall.", "hdr")
        else:
            for line in render_install_artifact_paths(install_path):
                self._append(line, "hdr")
            if self.active_operation["operation"] == "install":
                self._append(
                    f"Projects: {len(self.project_paths)} isolated folder(s); "
                    "disposable Recall and local backup included",
                    "hdr",
                )
        self._append("")
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _start_install(self):
        if self.installing:
            return
        install_path = str(self._current_install_root())
        if not install_path:
            self._set_status("Please choose an install location", "err")
            return

        self.active_operation = self._read_operation_copy(install_path)
        project_specs = build_project_specs(self.project_paths)
        if self.active_operation["operation"] == "install" and not project_specs:
            self._set_status("Choose at least one project folder", "err")
            self._refresh_project_summary()
            return
        if self.active_operation["operation"] == "rollback":
            current_version = self.active_operation["current_version"] or "current version"
            target_version = self.active_operation["target_version"] or "older version"
            if not self.active_operation["confirmation_token"]:
                self._set_status("Code rollback cannot be verified from this package", "err")
                return
            if not self._confirm_code_rollback(current_version, target_version):
                self._set_status("Code rollback cancelled; nothing changed", "muted")
                return

        cmd = [
            str(self.installer_dir / "install.sh"),
            "--install-root", install_path,
            "--venv-mode", "fresh",
            "--verbose",
        ]
        if self.active_operation["operation"] == "rollback":
            cmd.extend(
                [
                    "--confirm-code-rollback",
                    self.active_operation["confirmation_token"],
                ]
            )
        if self.active_operation["operation"] == "install":
            for project in project_specs:
                cmd.extend(["--project", project])
        self._begin_operation(install_path, cmd)

    def _start_uninstall(self):
        if self.installing:
            return
        from tkinter import messagebox

        install_path = str(self._current_install_root())
        description = read_package_uninstall(self.installer_dir, install_path)
        if description is None:
            self._set_status("Use the exact official package that installed Elefante", "err")
            self._refresh_operation_copy()
            return
        token = str(description.get("confirmation_token") or "")
        if not token:
            self._set_status("Uninstall confirmation could not be verified", "err")
            return
        if not messagebox.askokcancel(
            "Uninstall Elefante?",
            (
                "Elefante app files and unchanged Elefante-owned agent connections "
                "will be removed. A verified backup is created first.\n\n"
                "Your memories remain on this computer for reinstall. Modified "
                "customer configuration is preserved. Create a support report first "
                "if you are uninstalling to diagnose a problem."
            ),
            icon="warning",
        ):
            self._set_status("Uninstall cancelled; nothing changed", "muted")
            return
        self.active_operation = {
            **self.active_operation,
            "operation": "uninstall",
            "verb": "Uninstall",
            "title": "Uninstall Elefante",
            "ready": "Ready to uninstall",
            "starting": "Starting uninstall…",
            "complete": "Uninstall verified — app removed and memories preserved for reinstall.",
        }
        cmd = [
            str(self.installer_dir / "install.sh"),
            "--install-root",
            install_path,
            "--uninstall",
            token,
        ]
        self._begin_operation(install_path, cmd)

    def _start_retained_rollback(self):
        if self.installing:
            return
        install_path = str(self._current_install_root())
        package_operation = self._read_operation_copy(install_path)
        token = package_operation["retained_rollback_token"]
        current_version = package_operation["retained_current_version"]
        target_version = package_operation["retained_target_version"]
        if (
            package_operation["retained_rollback_available"] != "true"
            or not token
            or not current_version
            or not target_version
        ):
            self._set_status("No exact verified previous product is available", "err")
            self._refresh_operation_copy()
            return
        if not self._confirm_code_rollback(current_version, target_version):
            self._set_status("Code rollback cancelled; nothing changed", "muted")
            return
        self.active_operation = installer_operation_copy(
            install_path,
            {
                "operation": "rollback",
                "current_version": current_version,
                "target_version": target_version,
                "confirmation_token": token,
            },
        )
        cmd = [
            str(self.installer_dir / "install.sh"),
            "--install-root",
            install_path,
            "--rollback-retained",
            token,
        ]
        self._begin_operation(install_path, cmd)

    def _run(self, cmd: list[str]):
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(self.installer_dir),
            )
            assert self.process.stdout is not None
            for line in iter(self.process.stdout.readline, ""):
                stripped = line.rstrip()
                self.root.after(0, self._handle_line, stripped)
            self.process.wait()
            rc = self.process.returncode
        except Exception as e:
            self.root.after(0, self._append, f"ERROR: {e}", "err")
            rc = 1
        self.root.after(0, self._finished, rc)

    # ── Output parsing ───────────────────────────────────────────────────

    def _handle_line(self, line: str):
        if not line:
            return

        # Color tag
        tag = None
        if line.startswith("OK:"):
            tag = "ok"
        elif line.startswith("ERROR"):
            tag = "err"
        elif line.startswith("WARN"):
            tag = "warn"
        elif line.startswith("[Step"):
            tag = "step"
        elif "=====" in line:
            tag = "hdr"

        advance, status_text = process_stage_marker(line, self.seen_markers)
        if advance:
            self.stages_hit += advance
            self.progress_var.set(min(self.stages_hit, TOTAL_STAGES))
        if status_text:
            self._set_status(status_text, "muted")

        self._append(line, tag)

    def _finished(self, rc: int):
        self.installing = False
        self.process = None

        if rc == 0:
            self.progress_var.set(TOTAL_STAGES)
            self._set_status(self.active_operation["complete"], "ok")
            self._append("")
            self._append(self.active_operation["complete"], "ok")
            self.install_btn.configure(
                text="  Done  ", state=self.tk.NORMAL,
                command=self.root.destroy,
            )
        else:
            operation = self.active_operation["verb"]
            failure_status = (
                f"{operation} stopped \u2014 use the recovery files below"
                if self.cancel_requested
                else f"{operation} failed \u2014 use the recovery files below"
            )
            self._set_status(failure_status, "err")
            self._append("")
            self._append(
                f"{operation} stopped before completion."
                if self.cancel_requested
                else f"{operation} failed.",
                "err",
            )
            for guidance_line in render_failed_install_guidance(self._current_install_root()):
                self._append(guidance_line, "hdr")
            self.install_btn.configure(
                text="  Retry  ", state=self.tk.NORMAL,
                command=self._retry,
            )
            self.browse_btn.configure(state=self.tk.NORMAL)
            self.path_entry.configure(state=self.tk.NORMAL)
            self.rollback_btn.configure(state=self.tk.NORMAL)
            self.uninstall_btn.configure(state=self.tk.NORMAL)
            self._refresh_project_summary()
        self.cancel_requested = False

    def _retry(self):
        self.output.configure(state=self.tk.NORMAL)
        self.output.delete("1.0", self.tk.END)
        self.output.configure(state=self.tk.DISABLED)
        self.installing = False
        self._refresh_operation_copy()
        if self.retry_uninstall:
            self._start_uninstall()
        elif self.retry_retained_rollback:
            self._start_retained_rollback()
        else:
            self._start_install()

    # ── Window close ─────────────────────────────────────────────────────

    def _on_close(self):
        if self.installing and self.process:
            from tkinter import messagebox
            if not messagebox.askokcancel(
                "Cancel Installation?",
                "Installation is in progress.\nAre you sure you want to cancel?",
            ):
                return
            try:
                self.cancel_requested = True
                self.process.terminate()
            except Exception:
                pass
        self.root.destroy()

    # ── Utilities ────────────────────────────────────────────────────────

    def _append(self, text: str, tag: str | None = None):
        self.output.configure(state=self.tk.NORMAL)
        if tag:
            self.output.insert(self.tk.END, text + "\n", tag)
        else:
            self.output.insert(self.tk.END, text + "\n")
        self.output.see(self.tk.END)
        self.output.configure(state=self.tk.DISABLED)

    def _set_status(self, text: str, tone: str = "muted"):
        styles = {
            "muted": "Muted.TLabel",
            "ok": "Success.TLabel",
            "err": "Error.TLabel",
        }
        self.status_label.configure(text=text, style=styles.get(tone, "Muted.TLabel"))


if __name__ == "__main__":
    main()
