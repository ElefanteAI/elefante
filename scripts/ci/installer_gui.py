#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : installer_gui.py
# VERSION : 2.8.0
# CHANGED : 2026-04-16
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
import os
import re
import subprocess
import sys
import threading
from pathlib import Path


INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"


def default_install_path() -> Path:
    return Path.home() / ".elefante" / "app" / "current"


def default_data_path() -> Path:
    return Path.home() / ".elefante" / "data"


def normalize_install_root(install_root: str | Path | None) -> Path:
    raw_path = str(install_root or "").strip()
    if not raw_path:
        return default_install_path()
    return Path(raw_path).expanduser()


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

        self.default_install_path = default_install_path()
        self.default_data_path = default_data_path()
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
        w, h = 920, 820
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(40, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(820, 700)

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
        outer.rowconfigure(7, weight=1)

        hero = ttk.Frame(outer)
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(1, weight=1)

        badge = self._load_badge_image()
        if badge is not None:
            ttk.Label(hero, image=badge).grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 18))

        ttk.Label(hero, text="Install Elefante", style="Title.TLabel").grid(
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

        recovery = ttk.LabelFrame(outer, text="Recovery files", padding=(18, 14), style="Section.TLabelframe")
        recovery.grid(row=4, column=0, sticky="ew", pady=(16, 0))
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
        actions.grid(row=5, column=0, sticky="ew", pady=(16, 10))
        actions.columnconfigure(1, weight=1)

        self.install_btn = ttk.Button(
            actions,
            text="Install Elefante",
            command=self._start_install,
            style="Install.TButton",
        )
        self.install_btn.grid(row=0, column=0, sticky="w")

        ttk.Label(
            actions,
            text="The installer will show real-time progress below and can be retried if something fails.",
            style="Muted.TLabel",
            wraplength=560,
            justify=tk.LEFT,
        ).grid(row=0, column=1, sticky="w", padx=(18, 0))

        progress_wrap = ttk.Frame(outer)
        progress_wrap.grid(row=6, column=0, sticky="ew")
        progress_wrap.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(progress_wrap, variable=self.progress_var, maximum=TOTAL_STAGES)
        self.progress.grid(row=0, column=0, sticky="ew")

        self.status_label = ttk.Label(progress_wrap, text="Ready to install", style="Muted.TLabel")
        self.status_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

        log_frame = ttk.LabelFrame(outer, text="Installer output", padding=(12, 12), style="Section.TLabelframe")
        log_frame.grid(row=7, column=0, sticky="nsew", pady=(16, 0))
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

    def _on_path_changed(self, *_args):
        self._refresh_artifact_paths()

    def _current_install_root(self) -> Path:
        return normalize_install_root(self.path_var.get())

    def _current_artifact_paths(self) -> dict[str, Path]:
        return build_install_artifact_paths(self._current_install_root())

    def _refresh_artifact_paths(self):
        paths = self._current_artifact_paths()
        self.summary_path_var.set(f"Summary: {paths['summary']}")
        self.status_path_var.set(f"Status:  {paths['status']}")
        self.log_path_var.set(f"Log:     {paths['log']}")

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

    def _start_install(self):
        if self.installing:
            return
        install_path = str(self._current_install_root())
        if not install_path:
            self._set_status("Please choose an install location", "err")
            return

        self.installing = True
        self.stages_hit = 0
        self.seen_markers.clear()
        self.cancel_requested = False
        self.progress_var.set(0)
        self.install_btn.configure(state=self.tk.DISABLED)
        self.browse_btn.configure(state=self.tk.DISABLED)
        self.path_entry.configure(state=self.tk.DISABLED)

        self._set_status("Starting installation\u2026", "muted")
        for line in render_install_artifact_paths(install_path):
            self._append(line, "hdr")
        self._append("")

        cmd = [
            str(self.installer_dir / "install.sh"),
            "--install-root", install_path,
            "--venv-mode", "fresh",
            "--verbose",
        ]
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

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
            self._set_status("Installation complete!", "ok")
            self._append("")
            self._append(
                "Installation complete! Restart your IDE to activate Elefante.", "ok",
            )
            self.install_btn.configure(
                text="  Done  ", state=self.tk.NORMAL,
                command=self.root.destroy,
            )
        else:
            failure_status = (
                "Installation stopped \u2014 use the recovery files below"
                if self.cancel_requested
                else "Installation failed \u2014 use the recovery files below"
            )
            self._set_status(failure_status, "err")
            self._append("")
            self._append(
                "Installation stopped before completion."
                if self.cancel_requested
                else "Installation failed.",
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
        self.cancel_requested = False

    def _retry(self):
        self.output.configure(state=self.tk.NORMAL)
        self.output.delete("1.0", self.tk.END)
        self.output.configure(state=self.tk.DISABLED)
        self.install_btn.configure(text="  Install Elefante  ")
        self.installing = False
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
