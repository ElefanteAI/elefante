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


def default_install_path() -> Path:
    return Path.home() / ".elefante" / "app" / "current"


def default_data_path() -> Path:
    return Path.home() / ".elefante" / "data"

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

        self.default_install_path = default_install_path()
        self.default_data_path = default_data_path()

        # Native light-mode-safe palette. macOS Aqua can ignore custom widget
        # backgrounds, so default to readable high-contrast colors.
        self.C = dict(
            bg="#f6f7f9",
            panel="#ffffff",
            fg="#111827",
            subtle="#374151",
            muted="#6b7280",
            accent="#0f766e",
            accent_h="#115e59",
            border="#d1d5db",
            input_bg="#ffffff",
            ok="#15803d",
            err="#b91c1c",
            warn="#a16207",
        )

        self.root.title("Install Elefante")
        self.root.configure(bg=self.C["bg"])

        # Center on screen
        w, h = 840, 680
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(40, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(640, 500)

        # Bring to front
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))

        try:
            ttk.Style().theme_use("aqua")
        except Exception:
            pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        tk = self.tk
        ttk = self.ttk
        C = self.C

        outer = tk.Frame(self.root, bg=C["bg"])
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)

        card = tk.Frame(outer, bg=C["panel"], highlightthickness=1,
                        highlightbackground=C["border"])
        card.pack(fill=tk.BOTH, expand=True)

        # ── Header ──
        hdr = tk.Frame(card, bg=C["panel"])
        hdr.pack(fill=tk.X, padx=28, pady=(24, 12))
        tk.Label(hdr, text="ELEFANTE",
                 font=("Helvetica Neue", 28, "bold"),
                 fg=C["fg"]).pack(anchor=tk.W)
        tk.Label(hdr, text="Local memory for your AI. Stored on this Mac.",
                 font=("Helvetica Neue", 13),
                 fg=C["subtle"]).pack(anchor=tk.W, pady=(4, 0))

        # ── Privacy / default path panel ──
        privacy = tk.Frame(card, bg="#f0fdf4", highlightthickness=1,
                           highlightbackground="#bbf7d0")
        privacy.pack(fill=tk.X, padx=28, pady=(0, 16))
        tk.Label(
            privacy, text="Recommended default",
            font=("Helvetica Neue", 12, "bold"),
            fg=C["ok"],
        ).pack(anchor=tk.W, padx=14, pady=(12, 2))
        tk.Label(
            privacy,
            text="Install app files in a hidden folder inside your user home. Not in Documents.",
            font=("Helvetica Neue", 11),
            fg=C["subtle"],
        ).pack(anchor=tk.W, padx=14)
        tk.Label(
            privacy, text=f"App:  {self.default_install_path}",
            font=("Menlo", 11), fg=C["fg"],
        ).pack(anchor=tk.W, padx=14, pady=(8, 2))
        tk.Label(
            privacy, text=f"Data: {self.default_data_path}",
            font=("Menlo", 11), fg=C["fg"],
        ).pack(anchor=tk.W, padx=14, pady=(0, 12))

        # ── Install path ─────────────────────────────────────────────────
        sec = tk.Frame(card, bg=C["panel"])
        sec.pack(fill=tk.X, padx=28, pady=(0, 6))
        tk.Label(sec, text="Install location",
                 font=("Helvetica Neue", 12, "bold"),
                 fg=C["fg"]).pack(anchor=tk.W)
        tk.Label(sec, text="Change this only if you want the app files somewhere else.",
                 font=("Helvetica Neue", 10),
                 fg=C["muted"]).pack(anchor=tk.W, pady=(2, 8))

        row = tk.Frame(sec, bg=C["panel"])
        row.pack(fill=tk.X)

        self.path_var = tk.StringVar(value=str(self.default_install_path))
        self.path_entry = tk.Entry(
            row, textvariable=self.path_var,
            font=("Menlo", 12), bg=C["input_bg"], fg=C["fg"],
            insertbackground=C["fg"], relief=tk.FLAT,
            highlightthickness=1, highlightbackground=C["border"],
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        self.browse_btn = tk.Button(
            row, text="Browse\u2026", command=self._browse,
            font=("Helvetica Neue", 11), bg="#eef2f7", fg=C["fg"],
            activebackground="#e5e7eb", relief=tk.FLAT, padx=14, pady=6,
        )
        self.browse_btn.pack(side=tk.RIGHT, padx=(8, 0))

        tk.Label(sec,
                 text="Memories stay local on this Mac. Logs are written into the chosen install folder.",
                 font=("Helvetica Neue", 10), fg=C["muted"]).pack(anchor=tk.W, pady=(6, 0))

        # ── Install button ───────────────────────────────────────────────
        self.install_btn = tk.Button(
            card, text="  Install Elefante  ", command=self._start_install,
            font=("Helvetica Neue", 15, "bold"),
            highlightbackground=C["accent"], padx=28, pady=10,
            cursor="hand2", default="active",
        )
        self.install_btn.pack(pady=18)

        # ── Progress ─────────────────────────────────────────────────────
        pf = tk.Frame(card, bg=C["panel"])
        pf.pack(fill=tk.X, padx=28, pady=(0, 2))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            pf, variable=self.progress_var, maximum=TOTAL_STAGES,
        )
        self.progress.pack(fill=tk.X)

        self.status_label = tk.Label(
            card, text="Ready to install",
            font=("Helvetica Neue", 11), fg=C["muted"],
        )
        self.status_label.pack(pady=(2, 6))

        # ── Output log ───────────────────────────────────────────────────
        tk.Label(card, text="Installer output",
                 font=("Helvetica Neue", 12, "bold"),
                 fg=C["fg"]).pack(anchor=tk.W, padx=28)

        border_wrap = tk.Frame(card, bg=C["border"], padx=1, pady=1)
        border_wrap.pack(fill=tk.BOTH, expand=True, padx=28, pady=(8, 24))

        self.output = self.scrolledtext.ScrolledText(
            border_wrap, font=("Menlo", 10),
            bg="#fbfbfc", fg=C["subtle"],
            insertbackground=C["fg"], relief=tk.FLAT,
            state=tk.DISABLED, wrap=tk.WORD,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        self.output.tag_configure("ok", foreground=C["ok"])
        self.output.tag_configure("err", foreground=C["err"])
        self.output.tag_configure("warn", foreground=C["warn"])
        self.output.tag_configure("step", foreground=C["fg"], font=("Menlo", 10, "bold"))
        self.output.tag_configure("hdr", foreground=C["accent"], font=("Menlo", 10, "bold"))

    # ── Actions ──────────────────────────────────────────────────────────

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(
            title="Choose Elefante Install Location",
            initialdir=str(Path(self.path_var.get()).parent),
        )
        if path:
            self.path_var.set(path)

    def _start_install(self):
        if self.installing:
            return
        install_path = self.path_var.get().strip()
        if not install_path:
            self._set_status("Please choose an install location", self.C["err"])
            return

        self.installing = True
        self.stages_hit = 0
        self.progress_var.set(0)
        self.install_btn.configure(state=self.tk.DISABLED)
        self.browse_btn.configure(state=self.tk.DISABLED)
        self.path_entry.configure(state=self.tk.DISABLED)

        self._set_status("Starting installation\u2026", self.C["fg"])

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

        # Progress tracking
        for marker in STAGE_MARKERS:
            if marker in line:
                self.stages_hit += 1
                self.progress_var.set(min(self.stages_hit, TOTAL_STAGES))
                # Friendly status
                if line.startswith("[Step"):
                    m = re.match(r"\[Step \S+\]\s*(.*?)\.{0,3}$", line)
                    if m:
                        self._set_status(f"Installing: {m.group(1)}", self.C["fg"])
                elif "PRE-FLIGHT" in line:
                    self._set_status("Running pre-flight checks\u2026", self.C["fg"])
                elif "Purging" in line:
                    self._set_status("Purging stale bytecode\u2026", self.C["fg"])
                elif "MCP handshake" in line:
                    self._set_status("Verifying MCP handshake\u2026", self.C["fg"])
                break

        self._append(line, tag)

    def _finished(self, rc: int):
        self.installing = False
        self.process = None

        if rc == 0:
            self.progress_var.set(TOTAL_STAGES)
            self._set_status("Installation complete!", self.C["ok"])
            self._append("")
            self._append(
                "Installation complete! Restart your IDE to activate Elefante.", "ok",
            )
            self.install_btn.configure(
                text="  Done  ", state=self.tk.NORMAL,
                command=self.root.destroy,
            )
        else:
            self._set_status("Installation failed \u2014 check log above", self.C["err"])
            self._append("")
            self._append("Installation failed. Review the output above for details.", "err")
            self.install_btn.configure(
                text="  Retry  ", state=self.tk.NORMAL,
                command=self._retry,
            )
            self.browse_btn.configure(state=self.tk.NORMAL)
            self.path_entry.configure(state=self.tk.NORMAL)

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

    def _set_status(self, text: str, color: str | None = None):
        self.status_label.configure(text=text, fg=color or self.C["muted"])


if __name__ == "__main__":
    main()
