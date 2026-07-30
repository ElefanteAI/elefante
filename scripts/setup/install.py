# ─────────────────────────────────────────────────────────────────────────────
# NAME    : install.py
# VERSION : 2.7.2
# CHANGED : 2026-04-16
# PURPOSE : Single-entry installer: venv, deps, DB init, daemon plus detected
#           MCP host configuration, status files, rolling terminal UI, and system
#           verification in one cross-platform script.
# WHEN    : First-time installation on any machine, or clean reinstall after a
#           factory reset. NOT for routine restarts (use restart_elefante.py) or
#           IDE reconfiguration (use configure_vscode_bob.py standalone).
# USAGE   : python scripts/setup/install.py [--log-file .elefante-install.log]
#           [--status-file .elefante-install-status.txt]
#           [--summary-file .elefante-install-summary.txt]
#           [--venv-mode ask|fresh|backup|reuse|abort]
# NOTES   : Creates .venv or explicitly handles an existing one, installs
#           requirements.txt, calls init_databases.py, then calls both
#           configure_*.py scripts. Safe to re-run if install is interrupted.
#           Requires Python 3.11+.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""
Elefante Unified Installation Script
------------------------------------
Robust, one-click installation for Windows, macOS, and Linux.
Handles:
1. Virtual Environment creation
2. Dependency installation
3. Database initialization
4. Local daemon and detected MCP host configuration
5. System verification
"""

import os
import sys
import subprocess
import platform
import shutil
import argparse
import datetime
import json
import signal
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX = (3, 14)


def ensure_supported_python() -> None:
    version_tuple = sys.version_info[:2]
    if SUPPORTED_PYTHON_MIN <= version_tuple < SUPPORTED_PYTHON_MAX:
        return

    detected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(
        "ERROR: Elefante requires Python 3.11, 3.12, or 3.13. "
        f"Detected {detected}."
    )
    raise SystemExit(1)


ensure_supported_python()

SETUP_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path(__file__).resolve().parents[2]
VENV_MODE_ASK = "ask"
VENV_MODE_FRESH = "fresh"
VENV_MODE_BACKUP = "backup"
VENV_MODE_REUSE = "reuse"
VENV_MODE_ABORT = "abort"
INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"
DAEMON_HEALTH_URL = "http://127.0.0.1:8765/health"
verbose_mode = False
BRAILLE_SPINNER_FRAMES = [
    "\u280b",
    "\u2819",
    "\u2839",
    "\u2838",
    "\u283c",
    "\u2834",
    "\u2826",
    "\u2827",
    "\u2807",
    "\u280f",
]
ASCII_SPINNER_FRAMES = ["-", "\\", "|", "/"]

# Ensure sibling setup modules are importable when running as a script.
sys.path.insert(0, str(SETUP_DIR))

from configure_vscode_bob import configure_mcp as configure_vscode  # noqa: E402
from configure_antigravity import (  # noqa: E402
    configure_mcp as configure_antigravity,
    host_is_detected as antigravity_is_detected,
)
from configure_cursor_kiro import configure_detected_hosts, infer_repo_python  # noqa: E402
from configure_cli_agents import configure_detected_cli_hosts  # noqa: E402
from host_selection import (  # noqa: E402
    CLI_HOSTS,
    HOST_LABELS,
    JSON_HOSTS,
    SUPPORTED_HOSTS,
    VSCODE_FAMILY,
    normalize_selected_hosts,
    select_family,
)


class InstallationCancelled(Exception):
    """Raised when the operator cancels at a safe checkpoint."""


class Logger:
    def __init__(self, log_file=None, spinner_enabled=True):
        self.log_file = log_file
        self._console_lock = threading.Lock()
        self._spinner_enabled = spinner_enabled and self._supports_interactive_updates()
        self._spinner_frames = (
            BRAILLE_SPINNER_FRAMES if self._supports_unicode_output() else ASCII_SPINNER_FRAMES
        )
        self._spinner_text = ""
        self._spinner_thread = None
        self._spinner_stop_event = None
        self._spinner_visible = False
        if log_file:
            # Ensure log file exists and is writable
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, 'a', encoding='utf-8'):
                    pass
            except Exception as e:
                print(f"WARN: Could not open log file {log_file}: {e}")
                self.log_file = None

    def _supports_interactive_updates(self):
        try:
            return sys.stdout.isatty()
        except Exception:
            return False

    def _supports_unicode_output(self):
        encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
        return "utf" in encoding

    def _clear_status_line_locked(self):
        if not self._spinner_visible:
            return
        width = shutil.get_terminal_size((80, 20)).columns
        print("\r" + (" " * max(0, width - 1)) + "\r", end="", flush=True)
        self._spinner_visible = False

    def _spinner_loop(self):
        frame_index = 0
        while self._spinner_stop_event and not self._spinner_stop_event.is_set():
            with self._console_lock:
                self._clear_status_line_locked()
                frame = self._spinner_frames[frame_index % len(self._spinner_frames)]
                print(f"\r{frame} {self._spinner_text}", end="", flush=True)
                self._spinner_visible = True
            frame_index += 1
            time.sleep(0.12)

        with self._console_lock:
            self._clear_status_line_locked()

    def start_spinner(self, text):
        if not self._spinner_enabled:
            return
        self._spinner_text = text.strip()
        if self._spinner_thread and self._spinner_thread.is_alive():
            return
        self._spinner_stop_event = threading.Event()
        self._spinner_thread = threading.Thread(
            target=self._spinner_loop,
            name="elefante-install-spinner",
            daemon=True,
        )
        self._spinner_thread.start()

    def update_spinner(self, text):
        self._spinner_text = text.strip()

    def stop_spinner(self):
        if not self._spinner_thread:
            return
        if self._spinner_stop_event:
            self._spinner_stop_event.set()
        self._spinner_thread.join(timeout=0.5)
        self._spinner_thread = None
        self._spinner_stop_event = None
        with self._console_lock:
            self._clear_status_line_locked()

    def log(self, msg, end="\n"):
        with self._console_lock:
            self._clear_status_line_locked()
            print(msg, end=end, flush=True)
        # Write to file if configured
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    clean_msg = msg
                    f.write(clean_msg + end)
            except Exception:
                pass

    def log_file_only(self, msg, end="\n"):
        """Write to log file without printing to console (for non-verbose subprocess output)."""
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(msg + end)
            except Exception:
                pass

logger = Logger()
state_tracker = None
cancel_requested = False


class InstallStateTracker:
    def __init__(self, root_dir, logger, status_file=None, summary_file=None, log_file=None):
        self.root_dir = Path(root_dir)
        self.logger = logger
        self.status_file = Path(status_file) if status_file else self.root_dir / INSTALL_STATUS_FILE_NAME
        self.summary_file = Path(summary_file) if summary_file else self.root_dir / INSTALL_SUMMARY_FILE_NAME
        self.log_file = Path(log_file) if log_file else Path(logger.log_file or self.root_dir / INSTALL_LOG_FILE_NAME)
        self.current_state = "starting"
        self.current_stage_id = ""
        self.current_stage_name = ""
        self.cancel_requested = False
        self.final_note = ""
        self.stage_order = []
        self.stages = {}
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.summary_file.parent.mkdir(parents=True, exist_ok=True)
        self._write_status()
        self._write_summary()

    def _timestamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _sanitize(self, detail):
        return (detail or "").replace("\n", " ").strip()

    def request_cancellation(self):
        self.cancel_requested = True
        self._write_status()
        self._write_summary()

    def start_stage(self, stage_id, stage_name, detail=""):
        stage_key = str(stage_id)
        if stage_key not in self.stage_order:
            self.stage_order.append(stage_key)
        self.current_state = "running"
        self.current_stage_id = stage_key
        self.current_stage_name = stage_name
        self.stages[stage_key] = {
            "id": stage_key,
            "name": stage_name,
            "status": "IN_PROGRESS",
            "detail": self._sanitize(detail),
            "updated_at": self._timestamp(),
        }
        self._write_status()
        self._write_summary()

    def _set_stage_status(self, stage_id, stage_name, status, detail=""):
        stage_key = str(stage_id)
        if stage_key not in self.stage_order:
            self.stage_order.append(stage_key)
        self.stages[stage_key] = {
            "id": stage_key,
            "name": stage_name,
            "status": status,
            "detail": self._sanitize(detail),
            "updated_at": self._timestamp(),
        }
        if status in {"COMPLETE", "WARN"}:
            self.current_stage_id = ""
            self.current_stage_name = ""
        self._write_status()
        self._write_summary()

    def complete_stage(self, stage_id, stage_name, detail=""):
        self._set_stage_status(stage_id, stage_name, "COMPLETE", detail)

    def warn_stage(self, stage_id, stage_name, detail=""):
        self._set_stage_status(stage_id, stage_name, "WARN", detail)

    def fail_stage(self, stage_id, stage_name, detail=""):
        self.current_state = "failed"
        self.final_note = self._sanitize(detail)
        self._set_stage_status(stage_id, stage_name, "FAILED", detail)

    def cancel(self, detail=""):
        self.current_state = "cancelled"
        self.final_note = self._sanitize(detail)
        if self.current_stage_id:
            stage = self.stages.get(self.current_stage_id, {
                "id": self.current_stage_id,
                "name": self.current_stage_name or self.current_stage_id,
            })
            self.stages[self.current_stage_id] = {
                "id": stage["id"],
                "name": stage["name"],
                "status": "CANCELLED",
                "detail": self.final_note,
                "updated_at": self._timestamp(),
            }
            if self.current_stage_id not in self.stage_order:
                self.stage_order.append(self.current_stage_id)
        self.current_stage_id = ""
        self.current_stage_name = ""
        self._write_status()
        self._write_summary()

    def finish(self, success, next_action=""):
        if success:
            self.current_state = "completed"
            self.final_note = self._sanitize(next_action)
        self.current_stage_id = ""
        self.current_stage_name = ""
        self._write_status()
        self._write_summary()

    def render_console_summary(self, next_action=""):
        lines = []
        for stage_id in self.stage_order:
            stage = self.stages[stage_id]
            line = f"{stage['name']}: {stage['status']}"
            if stage["detail"]:
                line += f" ({stage['detail']})"
            lines.append(line)

        lines.append(f"Installer state: {self.current_state.upper()}")
        if next_action:
            lines.append(f"Next action: {next_action}")
        elif self.final_note:
            lines.append(f"Note: {self.final_note}")
        lines.append(f"Log file: {self.log_file}")
        lines.append(f"Status file: {self.status_file}")
        lines.append(f"Summary file: {self.summary_file}")
        return lines

    def render_persisted_file_routing(self):
        return [
            "Read these persisted installer files in order:",
            f"1. Summary file: {self.summary_file}",
            f"2. Status file: {self.status_file}",
            f"3. Log file: {self.log_file}",
        ]

    def _write_status(self):
        lines = [
            f"installer_state={self.current_state}",
            f"updated_at={self._timestamp()}",
            f"current_stage_id={self.current_stage_id}",
            f"current_stage_name={self.current_stage_name}",
            f"cancel_requested={str(self.cancel_requested).lower()}",
            f"log_file={self.log_file}",
            f"summary_file={self.summary_file}",
        ]
        if self.final_note:
            lines.append(f"final_note={self.final_note}")
        self.status_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_summary(self):
        lines = [
            f"installer_state={self.current_state}",
            f"updated_at={self._timestamp()}",
            f"log_file={self.log_file}",
            f"status_file={self.status_file}",
            f"summary_file={self.summary_file}",
            "",
            "stage_id|stage_name|status|detail|updated_at",
        ]
        for stage_id in self.stage_order:
            stage = self.stages[stage_id]
            lines.append(
                "|".join(
                    [
                        stage["id"],
                        stage["name"],
                        stage["status"],
                        stage["detail"],
                        stage["updated_at"],
                    ]
                )
            )
        if self.final_note:
            lines.extend(["", f"final_note={self.final_note}"])
        self.summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

def print_header(msg):
    logger.log("\n" + "="*60)
    logger.log(msg)
    logger.log("="*60 + "\n")

def print_step(step, msg):
    logger.log(f"\n[Step {step}] {msg}...")


def resolve_output_path(root_dir, provided_path, default_name):
    if provided_path:
        candidate = Path(provided_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path(root_dir) / candidate
        return candidate
    return Path(root_dir) / default_name


def install_signal_handlers():
    for signum in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if signum is None:
            continue
        try:
            signal.signal(signum, handle_cancel_signal)
        except (ValueError, OSError):
            continue


def handle_cancel_signal(signum, frame):
    del signum, frame
    global cancel_requested
    cancel_requested = True
    logger.log("\nWARN: Cancellation requested. Installer will stop at the next safe checkpoint.")
    if state_tracker is not None:
        state_tracker.request_cancellation()


def check_for_safe_cancellation(stage_name):
    if not cancel_requested:
        return
    detail = f"Cancelled before starting {stage_name}."
    if state_tracker is not None:
        state_tracker.cancel(detail)
    raise InstallationCancelled(detail)

def run_command(cmd, cwd=None, shell=False, env=None):
    """Run a command and check for errors.

    In default (non-verbose) mode, subprocess output goes only to the log file
    while the spinner keeps the user informed. In verbose mode, output streams
    to both console and log file.
    """
    try:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=run_env
        )
        assert process.stdout is not None

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                stripped = line.rstrip()
                if verbose_mode:
                    logger.log(stripped)
                else:
                    logger.log_file_only(stripped)

        return process.poll() == 0
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        logger.log(f"ERROR: Execution error: {e}")
        return False

def check_kuzu_compatibility(root_dir):
    """
    Pre-flight check for Kuzu 0.11+ compatibility issues
    Prevents the "Database path cannot be a directory" error
    """
    logger.log("\nChecking Kuzu compatibility...")
    
    # Check if Kuzu database directory exists
    kuzu_db_path = Path.home() / ".elefante" / "data" / "kuzu_db"
    
    if kuzu_db_path.exists() and kuzu_db_path.is_file():
        logger.log(f"OK: Found existing Kuzu database path at: {kuzu_db_path}")
        logger.log("   Current runtime contract allows kuzu_db to exist as a single file.")
        logger.log("   Leaving it in place.")
        return True

    if kuzu_db_path.exists() and kuzu_db_path.is_dir():
        # Check if it's a valid Kuzu database or empty directory
        kuzu_files = list(kuzu_db_path.glob("*.kz")) + list(kuzu_db_path.glob(".lock"))
        
        if kuzu_files:
            logger.log(f"WARN: Found existing Kuzu database at: {kuzu_db_path}")
            logger.log("   Kuzu 0.11+ requires clean installation for path compatibility.")
            logger.log("")
            logger.log("   Options:")
            logger.log("   1. Backup and remove (recommended)")
            logger.log("   2. Skip and risk installation failure")
            logger.log("")
            
            response = input("   Backup and remove existing database? (Y/n): ").strip().lower()
            
            if response in ['', 'y', 'yes']:
                logger.log("\n   This will MOVE the existing DB directory to a timestamped backup.")
                logger.log("   No data is deleted, but Elefante will start with a fresh DB.")
                confirm = input("   Type DELETE to proceed (or anything else to abort): ").strip()
                if confirm != "DELETE":
                    logger.log("OK: Aborted database move.")
                    logger.log("WARN: Skipping database removal. Installation may fail.")
                    logger.log("   If installation fails, manually move/remove: " + str(kuzu_db_path))
                    logger.log("")
                    return False

                # Move original to backup (safer than copy+delete)
                stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = kuzu_db_path.parent / f"kuzu_db.backup.{stamp}"
                # Ensure unique backup path
                suffix = 1
                while backup_path.exists():
                    backup_path = kuzu_db_path.parent / f"kuzu_db.backup.{stamp}.{suffix}"
                    suffix += 1

                logger.log(f"Moving database to backup at: {backup_path}")
                try:
                    shutil.move(str(kuzu_db_path), str(backup_path))
                except Exception as e:
                    logger.log(f"ERROR: Could not move database to backup: {e}")
                    logger.log("WARN: Skipping database removal. Installation may fail.")
                    logger.log("")
                    return False

                logger.log("OK: Database moved to backup successfully")
                logger.log("")
                return True
            else:
                logger.log("WARN: Skipping database removal. Installation may fail.")
                logger.log("   If installation fails, manually remove: " + str(kuzu_db_path))
                logger.log("")
                return False
        else:
            # Empty directory - safe to remove
            logger.log(f"Removing empty Kuzu directory: {kuzu_db_path}")
            kuzu_db_path.rmdir()
            logger.log("OK: Empty directory removed")
            return True
    else:
        logger.log("OK: No Kuzu compatibility issues detected")
        return True

def check_dependency_versions(root_dir):
    """
    Check for known breaking changes in dependencies
    """
    logger.log("\nChecking dependency versions for breaking changes...")
    
    requirements_file = root_dir / "requirements.lock"
    if not requirements_file.exists():
        logger.log("WARN: requirements.lock not found")
        return True
    
    breaking_changes = {
        "kuzu": {
            "version": "0.11",
            "issue": "Database path handling changed - cannot pre-create directories",
            "fixed_by": "check_kuzu_compatibility()"
        }
    }
    
    with open(requirements_file, 'r') as f:
        requirements = f.read()
    
    issues_found = []
    for package, info in breaking_changes.items():
        if package in requirements and info["version"] in requirements:
            logger.log(f"WARN: {package} {info['version']}+ detected")
            logger.log(f"   Known issue: {info['issue']}")
            logger.log(f"   Mitigation: {info['fixed_by']}")
            issues_found.append(package)
    
    if not issues_found:
        logger.log("OK: No known breaking changes detected")
    
    logger.log("")
    return True

def check_disk_space(root_dir):
    """
    Verify sufficient disk space for installation
    """
    logger.log("\nChecking disk space...")
    
    required_space = 5_000_000_000  # 5 GB
    
    if platform.system() == 'Windows':
        import ctypes
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            logger.log("ERROR: ctypes.windll is unavailable on this Python build")
            return False
        free_bytes = ctypes.c_ulonglong(0)
        windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(str(root_dir)), 
            None, 
            None, 
            ctypes.pointer(free_bytes)
        )
        available = free_bytes.value
    else:
        stat = os.statvfs(root_dir)
        available = stat.f_bavail * stat.f_frsize
    
    available_gb = available / (1024**3)
    required_gb = required_space / (1024**3)
    
    if available < required_space:
        logger.log("ERROR: Insufficient disk space")
        logger.log(f"   Available: {available_gb:.2f} GB")
        logger.log(f"   Required: {required_gb:.2f} GB")
        return False
    else:
        logger.log(f"OK: Sufficient disk space: {available_gb:.2f} GB available")
        return True

def run_preflight_checks(root_dir):
    """
    Run all pre-flight checks before installation
    """
    print_header("PRE-FLIGHT CHECKS")
    logger.log("Running automated checks to prevent common installation issues...")
    
    checks = [
        ("Disk Space", lambda: check_disk_space(root_dir)),
        ("Dependency Versions", lambda: check_dependency_versions(root_dir)),
        ("Kuzu Compatibility", lambda: check_kuzu_compatibility(root_dir)),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
                logger.log(f"ERROR: {check_name} check failed")
        except Exception as e:
            logger.log(f"WARN: {check_name} check error: {e}")
            all_passed = False
    
    if all_passed:
        logger.log("\nOK: All pre-flight checks passed")
        logger.log("="*60 + "\n")
        return True
    else:
        logger.log("\nERROR: Some pre-flight checks failed")
        logger.log("Please resolve the issues above before continuing.")
        logger.log("="*60 + "\n")
        return False

def purge_bytecode(root_dir):
    """Purge compiled bytecode to prevent stale execution"""
    logger.log("\nPurging bytecode...")
    count = 0
    try:
        # Walk and delete __pycache__ folders
        for path in root_dir.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path)
                count += 1
        
        # Walk and delete .pyc files
        for path in root_dir.rglob("*.pyc"):
             if path.is_file():
                 path.unlink()
                 count += 1
                 
        logger.log(f"OK: Cleaned {count} stale bytecode artifacts")
        return True
    except Exception as e:
        logger.log(f"WARN: Bytecode purge failed: {e}")
        return False


def get_python_cmd():
    """Get the correct python command"""
    if sys.platform == 'win32':
        return sys.executable
    return sys.executable


def get_repo_venv_dir(root_dir):
    """Return the repository virtualenv directory."""
    return root_dir / ".venv"


def get_repo_venv_python(root_dir):
    """Return the repository virtualenv Python path."""
    venv_dir = get_repo_venv_dir(root_dir)
    if sys.platform == 'win32':
        return str(venv_dir / "Scripts" / "python.exe")
    return str(venv_dir / "bin" / "python")


def read_venv_metadata(venv_dir):
    """Read lightweight metadata from pyvenv.cfg if available."""
    cfg_path = venv_dir / "pyvenv.cfg"
    metadata = {"version": None, "home": None}

    if not cfg_path.exists():
        return metadata

    try:
        for raw_line in cfg_path.read_text(encoding='utf-8').splitlines():
            if "=" not in raw_line:
                continue
            key, value = [part.strip() for part in raw_line.split("=", 1)]
            if key == "version":
                metadata["version"] = value
            elif key == "home":
                metadata["home"] = value
    except Exception:
        return metadata

    return metadata


def current_process_uses_repo_venv(root_dir):
    """Return True when this installer is running from the repo-local .venv."""
    try:
        repo_venv = get_repo_venv_dir(root_dir).resolve()
        current_exec = Path(sys.executable).resolve()
        return repo_venv in current_exec.parents
    except Exception:
        return False


def prompt_existing_venv_choice(root_dir, allow_destructive=True):
    """Ask the operator how to handle an existing repository virtualenv."""
    venv_dir = get_repo_venv_dir(root_dir)
    metadata = read_venv_metadata(venv_dir)

    logger.log("Existing repository virtual environment detected:")
    logger.log(f"   Path: {venv_dir}")
    if metadata["version"]:
        logger.log(f"   Python: {metadata['version']}")
    if metadata["home"]:
        logger.log(f"   Base Interpreter: {metadata['home']}")
    logger.log("")

    if allow_destructive:
        logger.log("Choose how to continue:")
        logger.log("   1. Delete existing .venv and install fresh [default]")
        logger.log("   2. Backup existing .venv and install fresh")
        logger.log("   3. Reuse existing .venv")
        logger.log("   4. Abort installation")
        options = {
            "": VENV_MODE_FRESH,
            "1": VENV_MODE_FRESH,
            "2": VENV_MODE_BACKUP,
            "3": VENV_MODE_REUSE,
            "4": VENV_MODE_ABORT,
        }
        prompt = "Select option [1-4, Enter=1]: "
    else:
        logger.log("Installer is currently running from this .venv.")
        logger.log("Fresh delete or backup+recreate is blocked while the active interpreter is inside the environment.")
        logger.log("Re-run via install.sh/install.bat, or run this script from system Python outside .venv for a fresh reinstall.")
        logger.log("")
        logger.log("Choose how to continue:")
        logger.log("   1. Reuse existing .venv [default]")
        logger.log("   2. Abort installation")
        options = {
            "": VENV_MODE_REUSE,
            "1": VENV_MODE_REUSE,
            "2": VENV_MODE_ABORT,
        }
        prompt = "Select option [1-2, Enter=1]: "

    while True:
        response = input(prompt).strip()
        if response in options:
            return options[response]
        logger.log("Invalid selection. Please try again.")


def delete_existing_venv(venv_dir):
    """Delete an existing .venv directory."""
    try:
        shutil.rmtree(venv_dir)
        logger.log("OK: Existing virtual environment removed")
        return True
    except Exception as e:
        logger.log(f"ERROR: Failed to remove existing .venv: {e}")
        return False


def backup_existing_venv(venv_dir):
    """Move an existing .venv directory aside before creating a new one."""
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = venv_dir.parent / f".venv.backup.{stamp}"
    suffix = 1
    while backup_dir.exists():
        backup_dir = venv_dir.parent / f".venv.backup.{stamp}.{suffix}"
        suffix += 1

    try:
        shutil.move(str(venv_dir), str(backup_dir))
        logger.log(f"OK: Existing virtual environment moved to {backup_dir}")
        return True
    except Exception as e:
        logger.log(f"ERROR: Failed to back up existing .venv: {e}")
        return False


def create_venv(root_dir, python_executable):
    """Create virtual environment if it doesn't exist"""
    venv_dir = get_repo_venv_dir(root_dir)
    if venv_dir.exists():
        logger.log("OK: Virtual environment already exists")
        return True
    
    logger.log("Creating virtual environment...")
    if run_command([python_executable, "-m", "venv", ".venv"], cwd=root_dir):
        logger.log("OK: Virtual environment created")
        return True
    else:
        logger.log("ERROR: Failed to create virtual environment")
        return False


def ensure_virtual_environment(root_dir, launcher_python, requested_mode):
    """Resolve how to handle .venv and return the Python executable to use."""
    venv_dir = get_repo_venv_dir(root_dir)
    repo_python = get_repo_venv_python(root_dir)
    allow_destructive = not current_process_uses_repo_venv(root_dir)

    if requested_mode in {VENV_MODE_FRESH, VENV_MODE_BACKUP} and venv_dir.exists() and not allow_destructive:
        logger.log("ERROR: Cannot replace the active repository .venv from within itself.")
        logger.log("   Re-run via install.sh/install.bat, or run this installer from system Python outside .venv.")
        return "failed", None

    if venv_dir.exists():
        chosen_mode = requested_mode
        if requested_mode == VENV_MODE_ASK:
            chosen_mode = prompt_existing_venv_choice(root_dir, allow_destructive=allow_destructive)

        if chosen_mode == VENV_MODE_ABORT:
            logger.log("Installation cancelled by user before dependency changes.")
            return "aborted", None

        if chosen_mode == VENV_MODE_REUSE:
            if Path(repo_python).exists():
                logger.log("OK: Reusing existing virtual environment")
                return "ready", repo_python
            logger.log("ERROR: Existing .venv does not contain a usable Python executable.")
            logger.log("   Re-run and choose a fresh or backup+fresh install.")
            return "failed", None

        if chosen_mode == VENV_MODE_BACKUP:
            logger.log("Backing up existing virtual environment before fresh install...")
            if not backup_existing_venv(venv_dir):
                return "failed", None
        elif chosen_mode == VENV_MODE_FRESH:
            logger.log("Deleting existing virtual environment before fresh install...")
            if not delete_existing_venv(venv_dir):
                return "failed", None

    if create_venv(root_dir, launcher_python):
        return "ready", repo_python
    return "failed", None

def install_dependencies(root_dir, python_cmd):
    """Install the checked-in, hash-verified dependency lock."""
    logger.log("Installing dependencies...")

    lock_file = root_dir / "requirements.lock"
    if not lock_file.is_file():
        logger.log("ERROR: requirements.lock is missing; refusing an unverified dependency resolution.")
        return False

    if not run_command([python_cmd, "-m", "pip", "--version"], cwd=root_dir):
        logger.log("WARN: Pip is missing from the selected virtual environment. Bootstrapping with ensurepip...")
        if not run_command([python_cmd, "-m", "ensurepip", "--upgrade"], cwd=root_dir):
            logger.log(
                "ERROR: Pip bootstrap failed. Read workspace/postmortems/installation.md Issue #13 for recovery."
            )
            logger.log("ERROR: Failed to install dependencies")
            return False
        if not run_command([python_cmd, "-m", "pip", "--version"], cwd=root_dir):
            logger.log(
                "ERROR: Pip is still unavailable after ensurepip. Read workspace/postmortems/installation.md Issue #13 for recovery."
            )
            logger.log("ERROR: Failed to install dependencies")
            return False
        logger.log("OK: Bootstrapped pip with ensurepip")
    
    # Upgrade pip when possible, but do not fail the installer if this optional step fails.
    if not run_command([python_cmd, "-m", "pip", "install", "--upgrade", "pip"], cwd=root_dir):
        logger.log("WARN: Pip self-upgrade failed. Continuing with the existing pip version.")
    
    # Install the complete, hash-checked lock rather than resolving ranges at install time.
    if run_command(
        [python_cmd, "-m", "pip", "install", "--require-hashes", "-r", "requirements.lock"],
        cwd=root_dir,
    ):
        logger.log("OK: Dependencies installed")
        return True
    else:
        logger.log("ERROR: Failed to install dependencies")
        return False

def build_dashboard_ui(root_dir):
    """Build the React frontend for the dashboard"""
    logger.log("Building Dashboard UI (this may take a minute)...")
    ui_dir = root_dir / "src" / "dashboard" / "ui"
    bundled_dist = ui_dir / "dist" / "index.html"
    
    if not ui_dir.exists():
        logger.log("WARN: Dashboard UI directory not found")
        return "skipped"

    if bundled_dist.exists():
        logger.log(f"OK: Using bundled dashboard assets at {bundled_dist}")
        return "bundled"
        
    try:
        npm_cmd = "npm.cmd" if platform.system() == 'Windows' else "npm"
        subprocess.check_call([npm_cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        logger.log("WARN: 'npm' is not installed or not in PATH. Skipping UI build.")
        logger.log("   To view the dashboard, install Node.js and run 'npm install && npm run build' in src/dashboard/ui")
        return "skipped"

    logger.log("   Installing npm dependencies...")
    if not run_command([npm_cmd, "install"], cwd=ui_dir):
        logger.log("WARN: Failed to install npm dependencies")
        return "skipped"
        
    logger.log("   Building production assets...")
    if not run_command([npm_cmd, "run", "build"], cwd=ui_dir):
        logger.log("WARN: Failed to build Dashboard UI")
        return "skipped"
        
    logger.log("OK: Dashboard UI built successfully")
    return "built"

def init_databases(root_dir, python_cmd):
    """Initialize the configured embedded vector store and Kuzu."""
    logger.log("Initializing databases...")
    script_path = root_dir / "scripts" / "setup" / "init_databases.py"
    if run_command([python_cmd, str(script_path)], cwd=root_dir, env={'ELEFANTE_LOG_FORMAT': 'text', 'ELEFANTE_LOGGING_FORMAT': 'text'}):
        logger.log("OK: Databases initialized")
        return True
    else:
        logger.log("ERROR: Database initialization failed")
        return False

def generate_dashboard_snapshot(root_dir, python_cmd):
    """Generate initial dashboard snapshot so the dashboard works on first open."""
    logger.log("Generating dashboard snapshot...")
    script_path = root_dir / "scripts" / "pipeline" / "update_dashboard_data.py"
    if run_command([python_cmd, str(script_path)], cwd=root_dir, env={'ELEFANTE_LOG_FORMAT': 'text', 'ELEFANTE_LOGGING_FORMAT': 'text'}):
        logger.log("OK: Dashboard snapshot generated")
        return "generated"
    else:
        logger.log("WARN: Dashboard snapshot generation failed (non-fatal)")
        return "skipped"  # Non-fatal — dashboard will generate on first refresh

def run_health_check(root_dir, python_cmd):
    """Run health check script"""
    logger.log("Running health check...")
    script_path = root_dir / "scripts" / "verify" / "verify_health.py"
    if run_command([python_cmd, str(script_path)], cwd=root_dir, env={'ELEFANTE_LOG_FORMAT': 'text', 'ELEFANTE_LOGGING_FORMAT': 'text'}):
        logger.log("OK: Health check passed")
        return True
    else:
        logger.log("ERROR: Health check failed")
        return False

def verify_copilot_instructions(root_dir):
    """Verify .github/copilot-instructions.md exists — the bootstrap layer for agent behavior"""
    logger.log("Verifying agent behavior bootstrap...")
    instructions_path = root_dir / ".github" / "copilot-instructions.md"
    if instructions_path.exists():
        logger.log(f"OK: copilot-instructions.md found at {instructions_path}")
        return True
    else:
        logger.log("ERROR: .github/copilot-instructions.md is MISSING")
        logger.log("   This file is the bootstrap layer that tells AI agents how to use Elefante.")
        logger.log("   Without it, agents will NOT proactively search memory.")
        logger.log("   Expected at: " + str(instructions_path))
        return False


def daemon_health_check(opener=urlopen) -> bool:
    """Confirm that the expected loopback daemon—not merely a listening port—is ready."""
    try:
        with opener(DAEMON_HEALTH_URL, timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False
    return payload == {
        "status": "ok",
        "service": "elefante-daemon",
        "transport": "streamable-http",
    }


def wait_for_daemon_health(
    *,
    timeout_seconds: float = 15,
    poll_seconds: float = 0.25,
    health_check=daemon_health_check,
    clock=time.monotonic,
    sleeper=time.sleep,
) -> bool:
    """Wait a bounded interval for the service manager to start the local daemon."""
    deadline = clock() + timeout_seconds
    while clock() <= deadline:
        if health_check():
            return True
        sleeper(poll_seconds)
    return False


def install_daemon_service(root_dir, python_cmd, *, health_waiter=wait_for_daemon_health):
    """Install the daemon and prove its health before configuring any MCP client."""
    service_script = root_dir / "scripts" / "lifecycle" / "daemon_service.py"
    if not run_command([python_cmd, str(service_script), "install", "--apply"], cwd=root_dir):
        return False
    if not health_waiter():
        logger.log("ERROR: Daemon service did not report healthy loopback status within 15 seconds")
        return False
    return True


def generate_proof(root_dir, status):
    """Generate installation proof block"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_status = str(status).upper()
    
    proof = f"""
============================================================
INSTALLATION PROOF
============================================================
Date:   {timestamp}
Status: {normalized_status}
Path:   {root_dir}
System: {platform.system()} {platform.release()}
============================================================
"""
    logger.log(proof)
    return proof

def main():
    global logger, state_tracker, verbose_mode
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", help="Path to log file")
    parser.add_argument("--status-file", help="Path to machine-readable install status file")
    parser.add_argument("--summary-file", help="Path to machine-readable install summary file")
    parser.add_argument(
        "--venv-mode",
        choices=[VENV_MODE_ASK, VENV_MODE_FRESH, VENV_MODE_BACKUP, VENV_MODE_REUSE, VENV_MODE_ABORT],
        default=VENV_MODE_ASK,
        help="How to handle an existing repository .venv: ask, fresh, backup, reuse, or abort.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full subprocess output. Default: clean progress with details in log file.",
    )
    parser.add_argument(
        "--host",
        action="append",
        choices=SUPPORTED_HOSTS,
        help="Configure only this detected agent host. Repeat to select multiple hosts.",
    )
    args = parser.parse_args()

    verbose_mode = args.verbose
    selected_hosts = normalize_selected_hosts(args.host)

    root_dir = ROOT_DIR
    log_file = resolve_output_path(root_dir, args.log_file, INSTALL_LOG_FILE_NAME)
    status_file = resolve_output_path(root_dir, args.status_file, INSTALL_STATUS_FILE_NAME)
    summary_file = resolve_output_path(root_dir, args.summary_file, INSTALL_SUMMARY_FILE_NAME)

    logger = Logger(str(log_file))
    state_tracker = InstallStateTracker(
        root_dir=root_dir,
        logger=logger,
        status_file=str(status_file),
        summary_file=str(summary_file),
        log_file=str(log_file),
    )
    install_signal_handlers()

    os.chdir(root_dir)
    
    data_dir = os.environ.get("ELEFANTE_DATA_DIR") or str(Path.home() / ".elefante" / "data")

    print_header("ELEFANTE INSTALLATION WIZARD")
    logger.log(f"  Install to:  {root_dir}")
    logger.log(f"  Data:        {data_dir}")
    logger.log(f"  Log:         {log_file}")
    logger.log(f"  Python:      {sys.version.split()[0]}")
    if selected_hosts is None:
        logger.log("  Agent hosts: all detected compatible hosts")
    else:
        labels = ", ".join(HOST_LABELS[host] for host in SUPPORTED_HOSTS if host in selected_hosts)
        logger.log(f"  Agent hosts: {labels}")
    if verbose_mode:
        logger.log("  Mode:        verbose (full subprocess output)")
    else:
        logger.log("  Mode:        clean (details in log file)")
    logger.log("")
    logger.log("Cancellation: press Ctrl+C to request a clean stop at the next safe checkpoint.")

    success = True
    install_status = "FAILED"
    next_action = ""
    python_cmd = get_python_cmd()

    try:
        check_for_safe_cancellation("bytecode purge")
        state_tracker.start_stage("0a", "Bytecode Purge", "Removing stale bytecode artifacts")
        logger.start_spinner("Purging stale bytecode artifacts")
        bytecode_ok = purge_bytecode(root_dir)
        logger.stop_spinner()
        if bytecode_ok:
            state_tracker.complete_stage("0a", "Bytecode Purge", "Stale bytecode artifacts removed")
        else:
            state_tracker.warn_stage("0a", "Bytecode Purge", "Bytecode purge reported warnings")

        check_for_safe_cancellation("pre-flight checks")
        state_tracker.start_stage("0b", "Pre-Flight Checks", "Running automated compatibility checks")
        logger.start_spinner("Running pre-flight checks")
        preflight_ok = run_preflight_checks(root_dir)
        logger.stop_spinner()
        if not preflight_ok:
            state_tracker.fail_stage("0b", "Pre-Flight Checks", "Resolve the reported pre-flight issues and retry")
            success = False
        else:
            state_tracker.complete_stage("0b", "Pre-Flight Checks", "All automated checks passed")

        if success:
            check_for_safe_cancellation("environment setup")
            print_step(1, "Environment Setup")
            state_tracker.start_stage("1", "Environment Setup", "Preparing repository virtual environment")
            venv_status, venv_python = ensure_virtual_environment(root_dir, python_cmd, args.venv_mode)
            if venv_status == "aborted":
                state_tracker.cancel("Installation cancelled by user before dependency changes")
                raise InstallationCancelled("Installation cancelled by user before dependency changes")
            if venv_status != "ready" or not venv_python:
                state_tracker.fail_stage("1", "Environment Setup", "Repository virtual environment setup failed")
                success = False
            else:
                python_cmd = venv_python
                state_tracker.complete_stage("1", "Environment Setup", f"Using repository Python at {python_cmd}")

        if success:
            check_for_safe_cancellation("dependency installation")
            print_step(2, "Dependencies")
            state_tracker.start_stage("2", "Dependencies", "Installing Python requirements")
            logger.start_spinner("Installing Python dependencies")
            deps_ok = install_dependencies(root_dir, python_cmd)
            logger.stop_spinner()
            if not deps_ok:
                state_tracker.fail_stage("2", "Dependencies", "Python dependency installation failed")
                success = False
            else:
                state_tracker.complete_stage("2", "Dependencies", "Python dependencies installed")

        if success:
            check_for_safe_cancellation("dashboard ui build")
            print_step("2a", "Dashboard UI Build")
            state_tracker.start_stage("2a", "Dashboard UI Build", "Preparing dashboard assets")
            logger.start_spinner("Preparing dashboard assets")
            ui_status = build_dashboard_ui(root_dir)
            logger.stop_spinner()
            if ui_status == "built":
                state_tracker.complete_stage("2a", "Dashboard UI Build", "Production dashboard assets built locally")
            elif ui_status == "bundled":
                state_tracker.complete_stage("2a", "Dashboard UI Build", "Bundled dashboard assets detected and reused")
            else:
                state_tracker.warn_stage("2a", "Dashboard UI Build", "Dashboard build skipped; see installer log for details")

        if success:
            check_for_safe_cancellation("database initialization")
            print_step(3, "Database Initialization")
            state_tracker.start_stage(
                "3",
                "Database Initialization",
                "Initializing the embedded vector store and Kuzu",
            )
            logger.start_spinner("Initializing databases")
            databases_ok = init_databases(root_dir, python_cmd)
            logger.stop_spinner()
            if not databases_ok:
                state_tracker.fail_stage("3", "Database Initialization", "Database initialization failed")
                success = False
            else:
                state_tracker.complete_stage("3", "Database Initialization", "Database initialization completed")

        if success:
            check_for_safe_cancellation("dashboard snapshot generation")
            logger.log("")
            logger.log("[Step 3a] Dashboard Snapshot...")
            state_tracker.start_stage("3a", "Dashboard Snapshot", "Generating initial dashboard snapshot")
            logger.start_spinner("Generating dashboard snapshot")
            snapshot_status = generate_dashboard_snapshot(root_dir, python_cmd)
            logger.stop_spinner()
            if snapshot_status == "generated":
                state_tracker.complete_stage("3a", "Dashboard Snapshot", "Initial dashboard snapshot generated")
            else:
                state_tracker.warn_stage("3a", "Dashboard Snapshot", "Snapshot generation failed; dashboard can refresh later")

        if success:
            check_for_safe_cancellation("daemon service installation")
            logger.log("")
            logger.log("[Step 3b] Local Daemon Service...")
            state_tracker.start_stage("3b", "Local Daemon Service", "Installing the shared local storage owner")
            if not install_daemon_service(root_dir, python_cmd):
                state_tracker.fail_stage("3b", "Local Daemon Service", "Daemon service installation failed")
                success = False
            else:
                state_tracker.complete_stage("3b", "Local Daemon Service", "User-scope daemon service installed")

        if success:
            check_for_safe_cancellation("ide configuration")
            print_step(4, "IDE Configuration")
            state_tracker.start_stage("4", "IDE Configuration", "Configuring MCP clients for supported IDEs")
            ide_detail = ""
            try:
                vscode_selection = select_family(selected_hosts, VSCODE_FAMILY)
                json_selection = select_family(selected_hosts, JSON_HOSTS)
                cli_selection = select_family(selected_hosts, CLI_HOSTS)

                vscode_success = False
                if vscode_selection is None or vscode_selection:
                    vscode_args = [
                        argument
                        for host in sorted(vscode_selection or [])
                        for argument in ("--host", host)
                    ]
                    vscode_success = configure_vscode(vscode_args)

                antigravity_success = False
                antigravity_selected = selected_hosts is not None and "antigravity" in selected_hosts
                if antigravity_selected or (selected_hosts is None and antigravity_is_detected()):
                    antigravity_success = configure_antigravity([])

                additional_hosts = {}
                if json_selection is None or json_selection:
                    additional_hosts = configure_detected_hosts(
                        root_dir,
                        infer_repo_python(root_dir),
                        selected=json_selection,
                    )

                cli_hosts = {}
                if cli_selection is None or cli_selection:
                    cli_hosts = configure_detected_cli_hosts(
                        root_dir,
                        infer_repo_python(root_dir),
                        selected=cli_selection,
                    )

                detail_parts = []
                if vscode_success:
                    configured_labels = (
                        [HOST_LABELS[host] for host in SUPPORTED_HOSTS if host in vscode_selection]
                        if vscode_selection is not None
                        else ["VS Code/Bob"]
                    )
                    configured_family = ", ".join(configured_labels)
                    logger.log(f"OK: MCP Server configured for {configured_family}")
                    detail_parts.append(f"{configured_family} configured")

                if antigravity_success:
                    logger.log("OK: MCP Server configured for Antigravity")
                    detail_parts.append("Antigravity configured")

                for host, configured in additional_hosts.items():
                    if configured:
                        logger.log(f"OK: MCP Server configured for {host.title()}")
                        detail_parts.append(f"{host.title()} configured")

                for host, result in cli_hosts.items():
                    if result == "configured":
                        logger.log(f"OK: MCP Server configured for {host}")
                        detail_parts.append(f"{host} configured")
                    elif result == "updated":
                        logger.log(f"OK: MCP Server registration refreshed for {host}")
                        detail_parts.append(f"{host} refreshed")
                    elif result == "already-present":
                        logger.log(f"INFO: Existing {host} Elefante registration preserved")
                        detail_parts.append(f"{host} preserved")
                    else:
                        logger.log(f"WARN: {host} MCP configuration was not changed ({result})")

                if (
                    not vscode_success
                    and not antigravity_success
                    and not any(additional_hosts.values())
                    and not any(result in {"configured", "updated", "already-present"} for result in cli_hosts.values())
                ):
                    logger.log("WARN: Automatic MCP configuration skipped")
                    logger.log("   Please configure your IDE manually.")
                    logger.log("   See docs/how-to/install.md and docs/how-to/run-mcp-server.md for instructions.")
                    ide_detail = "Automatic IDE configuration skipped"
                    state_tracker.warn_stage("4", "IDE Configuration", ide_detail)
                else:
                    ide_detail = "; ".join(detail_parts)
                    state_tracker.complete_stage("4", "IDE Configuration", ide_detail)
            except Exception as e:
                logger.log(f"ERROR: Error configuring MCP: {e}")
                state_tracker.warn_stage("4", "IDE Configuration", f"IDE configuration error: {e}")

        if success:
            check_for_safe_cancellation("agent behavior bootstrap verification")
            logger.log("")
            logger.log("[Step 4a] Agent Behavior Bootstrap...")
            state_tracker.start_stage("4a", "Agent Behavior Bootstrap", "Verifying agent bootstrap instructions")
            logger.start_spinner("Verifying agent bootstrap files")
            instructions_ok = verify_copilot_instructions(root_dir)
            logger.stop_spinner()
            if not instructions_ok:
                logger.log("WARN: Agent behavior bootstrap missing. Agents will not proactively use Elefante.")
                logger.log("   See docs/how-to/install.md Section 4a for details.")
                state_tracker.warn_stage("4a", "Agent Behavior Bootstrap", "copilot-instructions.md is missing")
            else:
                state_tracker.complete_stage("4a", "Agent Behavior Bootstrap", "Agent bootstrap instructions verified")

        if success:
            check_for_safe_cancellation("system verification")
            print_step(5, "System Verification")
            state_tracker.start_stage("5", "System Verification", "Running health checks")
            logger.start_spinner("Running system health check")
            health_ok = run_health_check(root_dir, python_cmd)
            logger.stop_spinner()
            if not health_ok:
                logger.log("WARN: Health check failed. Please review the errors.")
                state_tracker.fail_stage("5", "System Verification", "Health check failed")
                success = False
            else:
                state_tracker.complete_stage("5", "System Verification", "Health check passed")

        if success:
            check_for_safe_cancellation("mcp handshake verification")
            logger.log("\nVerifying MCP handshake...")
            state_tracker.start_stage("5a", "MCP Handshake Verification", "Checking live MCP protocol response")
            logger.start_spinner("Verifying MCP handshake")
            handshake_script = root_dir / "scripts" / "verify" / "verify_mcp_handshake.py"
            handshake_ok = run_command([python_cmd, str(handshake_script)], cwd=root_dir)
            logger.stop_spinner()
            if handshake_ok:
                logger.log("OK: MCP handshake verified")
                state_tracker.complete_stage("5a", "MCP Handshake Verification", "MCP server responded successfully")
            else:
                logger.log("ERROR: MCP handshake failed. Server is not responding to protocol.")
                state_tracker.fail_stage("5a", "MCP Handshake Verification", "MCP server did not respond to protocol handshake")
                success = False

    except InstallationCancelled:
        logger.stop_spinner()
        install_status = "CANCELLED"
        print_header("INSTALLATION CANCELLED")
        generate_proof(root_dir, install_status)
        for line in state_tracker.render_console_summary():
            logger.log(line)
        for line in state_tracker.render_persisted_file_routing():
            logger.log(line)
        if os.name == 'nt':
            input("Press Enter to exit...")
        return

    install_status = "SUCCESS" if success else "FAILED"
    next_action = "restart your IDE" if success else f"review {log_file}"
    state_tracker.finish(success, next_action=next_action)
    generate_proof(root_dir, install_status)

    if success:
        print_header("INSTALLATION COMPLETE")
        for line in state_tracker.render_console_summary(next_action=next_action):
            logger.log(line)
        logger.log("Let's prove it works.")
        logger.log("\n1. Restart your IDE to load the Elefante MCP server.")
        logger.log("2. Open your AI Chat (Copilot / Cursor / etc).")
        logger.log("3. Copy and paste exactly this question:\n")
        logger.log('   "What is my Elefante test passcode?"\n')
        logger.log("4. Watch your AI fetch the embedded seed memory autonomously.")
    else:
        print_header("INSTALLATION FAILED")
        for line in state_tracker.render_console_summary(next_action=next_action):
            logger.log(line)
        for line in state_tracker.render_persisted_file_routing():
            logger.log(line)
        logger.log("If the failure happened during dependency installation, copy the last 80 log lines before retrying.")
        sys.exit(1)
    
    if os.name == 'nt':
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
