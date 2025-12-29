"""
Elefante Mode Manager (v1.1.0) - Transaction-Scoped Locking

EVOLUTION from v1.0.1:
- Locks are now PER-OPERATION, not per-session
- No more "enable/disable" ceremony - operations auto-acquire/release
- Multiple IDEs can interleave operations safely
- Stale locks auto-expire after configurable timeout

Versioning:
- v1.0.0: Initial release (session-based locking)
- v1.0.1: Multi-IDE safety with enable/disable ceremony
- v1.1.0: Transaction-scoped locking (this version)

Design Principles:
1. SHORT TRANSACTIONS: Acquire → Work → Release (milliseconds, not hours)
2. AUTO-EXPIRY: Locks older than LOCK_TIMEOUT_SECONDS are considered stale
3. READ vs WRITE: Reads can proceed without locks; writes need brief exclusive lock
4. GRACEFUL DEGRADATION: If lock fails, return helpful error (don't crash)
"""

import os
import fcntl
import time
import atexit
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import contextmanager
import threading

from src.utils.config import get_config, DATA_DIR, ELEFANTE_HOME
from src.utils.version import PACKAGE_VERSION
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lock file paths
LOCK_DIR = ELEFANTE_HOME / "locks"
MASTER_LOCK_FILE = LOCK_DIR / "elefante.lock"
WRITE_LOCK_FILE = LOCK_DIR / "write.lock"

# Default timeout for stale lock detection (seconds)
DEFAULT_LOCK_TIMEOUT = 30
# Max time to wait for lock acquisition (seconds)
DEFAULT_ACQUIRE_TIMEOUT = 10


class TransactionLock:
    """
    A short-lived, auto-releasing lock for database operations.
    
    Usage:
        with TransactionLock("write") as lock:
            if lock.acquired:
                # do work
            else:
                # lock unavailable, handle gracefully
    """
    
    def __init__(
        self,
        lock_type: str = "write",
        timeout: float = DEFAULT_ACQUIRE_TIMEOUT,
        stale_threshold: float = DEFAULT_LOCK_TIMEOUT
    ):
        self.lock_type = lock_type
        self.timeout = timeout
        self.stale_threshold = stale_threshold
        self.acquired = False
        self._fd: Optional[int] = None
        self._lock_path = WRITE_LOCK_FILE if lock_type == "write" else MASTER_LOCK_FILE
        self._holder_info: Optional[Dict[str, str]] = None
        
    def __enter__(self) -> 'TransactionLock':
        self._acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release()
        return False  # Don't suppress exceptions
    
    def _is_lock_stale(self) -> bool:
        """Check if existing lock is stale (holder dead or timed out)."""
        if not self._lock_path.exists():
            return True
            
        try:
            content = self._lock_path.read_text().strip()
            if not content:
                return True
                
            parts = content.split("|")
            if len(parts) < 2:
                return True
                
            pid_str, timestamp_str = parts[0], parts[1]
            
            # Check if PID is still alive
            try:
                pid = int(pid_str)
                os.kill(pid, 0)  # Signal 0 = check existence
            except (ValueError, ProcessLookupError, PermissionError):
                logger.info(f"Lock holder PID {pid_str} is dead, lock is stale")
                return True
            
            # Check if lock is older than threshold
            try:
                lock_time = datetime.fromisoformat(timestamp_str)
                age = (datetime.utcnow() - lock_time).total_seconds()
                if age > self.stale_threshold:
                    logger.info(f"Lock is {age:.1f}s old (threshold: {self.stale_threshold}s), treating as stale")
                    return True
            except ValueError:
                return True
                
            # Lock is valid and held by alive process
            self._holder_info = {"pid": pid_str, "timestamp": timestamp_str}
            return False
            
        except Exception as e:
            logger.warning(f"Error checking lock staleness: {e}")
            return True
    
    def _clear_stale_lock(self):
        """Remove a stale lock file."""
        try:
            if self._lock_path.exists():
                self._lock_path.unlink()
                logger.info(f"Cleared stale lock: {self._lock_path}")
        except Exception as e:
            logger.warning(f"Failed to clear stale lock: {e}")
    
    def _acquire(self) -> bool:
        """Attempt to acquire the lock with timeout."""
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        
        while (time.time() - start_time) < self.timeout:
            # Check for stale lock first
            if self._is_lock_stale():
                self._clear_stale_lock()
            
            try:
                # Open/create lock file
                self._fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT)
                
                # Try non-blocking exclusive lock
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Write our PID and timestamp
                os.ftruncate(self._fd, 0)
                os.lseek(self._fd, 0, os.SEEK_SET)
                lock_info = f"{os.getpid()}|{datetime.utcnow().isoformat()}\n"
                os.write(self._fd, lock_info.encode())
                
                self.acquired = True
                logger.debug(f"Lock acquired: {self._lock_path}")
                return True
                
            except (IOError, OSError):
                # Lock held by another process
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except:
                        pass
                    self._fd = None
                
                # Brief sleep before retry
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Unexpected error acquiring lock: {e}")
                break
        
        # Timeout - couldn't acquire
        logger.warning(f"Failed to acquire {self.lock_type} lock after {self.timeout}s")
        return False
    
    def _release(self):
        """Release the lock."""
        if not self.acquired or self._fd is None:
            return
            
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            
            # Clear lock file content (don't delete - avoids race)
            try:
                self._lock_path.write_text("")
            except:
                pass
                
            logger.debug(f"Lock released: {self._lock_path}")
            
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")
            
        finally:
            self._fd = None
            self.acquired = False


class ElefanteModeManager:
    """
    Transaction-scoped lock manager for Elefante (v2.0.0).
    
    Key changes from v1.x:
    - No persistent "enabled/disabled" state
    - Operations acquire locks on-demand and release immediately
    - `is_enabled` always returns True (mode concept deprecated)
    - `enable()`/`disable()` are no-ops for backward compatibility
    """
    
    _instance: Optional['ElefanteModeManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._startup_time = datetime.utcnow()
        self._orchestrator_ref = None
        
        # Ensure lock directory exists
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        
        # Get config for timeouts
        try:
            config = get_config()
            self._lock_timeout = config.elefante.elefante_mode.lock_timeout_seconds
        except:
            self._lock_timeout = DEFAULT_LOCK_TIMEOUT
        
        logger.info(
            "ElefanteModeManager v1.1.0 initialized (transaction-scoped locking)",
            startup_time=self._startup_time.isoformat()
        )
    
    @property
    def is_enabled(self) -> bool:
        """
        Always returns True in v2.0.0.
        
        The "enabled/disabled" concept is deprecated. Operations now
        acquire locks on-demand and release immediately.
        """
        return True
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            "enabled": True,  # Always enabled in v1.1.0
            "version": PACKAGE_VERSION,
            "mode": "transaction-scoped",
            "startup_time": self._startup_time.isoformat(),
            "lock_timeout_seconds": self._lock_timeout,
            "data_dir": str(DATA_DIR),
            "pid": os.getpid()
        }
    
    @contextmanager
    def write_transaction(self, timeout: float = None):
        """
        Context manager for write operations.
        
        Usage:
            with mode_manager.write_transaction() as txn:
                if txn.acquired:
                    # safe to write
                else:
                    # another process is writing, handle gracefully
        """
        timeout = timeout or self._lock_timeout
        lock = TransactionLock("write", timeout=timeout, stale_threshold=self._lock_timeout)
        with lock:
            yield lock
    
    @contextmanager  
    def read_transaction(self):
        """
        Context manager for read operations.
        
        Reads don't need locks in our model - ChromaDB and Kuzu
        handle read consistency internally.
        """
        # No-op context manager - reads are lock-free
        class ReadLock:
            acquired = True
        yield ReadLock()
    
    def check_locks(self) -> Dict[str, Any]:
        """Check status of lock files."""
        lock_status = {}
        
        for name, path in [("write", WRITE_LOCK_FILE), ("master", MASTER_LOCK_FILE)]:
            status = {
                "path": str(path),
                "exists": path.exists(),
                "holder_info": None,
                "is_stale": False
            }
            
            if path.exists():
                try:
                    content = path.read_text().strip()
                    if content:
                        parts = content.split("|")
                        if len(parts) >= 2:
                            status["holder_info"] = {
                                "pid": parts[0],
                                "timestamp": parts[1]
                            }
                            # Check staleness
                            try:
                                pid = int(parts[0])
                                os.kill(pid, 0)
                                lock_time = datetime.fromisoformat(parts[1])
                                age = (datetime.utcnow() - lock_time).total_seconds()
                                status["is_stale"] = age > self._lock_timeout
                                status["age_seconds"] = age
                            except:
                                status["is_stale"] = True
                except:
                    status["is_stale"] = True
            
            lock_status[name] = status
        
        return lock_status
    
    def enable(self, force: bool = False) -> Dict[str, Any]:
        """
        DEPRECATED in v1.1.0 - kept for backward compatibility.
        
        Always returns success. Operations now auto-acquire locks.
        """
        logger.info("enable() called - no-op in v1.1.0 (transaction-scoped mode)")
        
        if force:
            # Force flag = clear any stale locks
            self._clear_all_stale_locks()
        
        return {
            "success": True,
            "message": "Elefante v1.1.0: Transaction-scoped locking active. No enable needed.",
            "status": self.status
        }
    
    def disable(self) -> Dict[str, Any]:
        """
        DEPRECATED in v1.1.0 - kept for backward compatibility.
        
        Clears any locks this process might hold and resets orchestrator ref.
        """
        logger.info("disable() called - clearing resources in v1.1.0")
        
        # Best-effort cleanup of orchestrator
        if self._orchestrator_ref is not None:
            try:
                from src.core.graph_store import get_graph_store, reset_graph_store
                graph_store = get_graph_store()
                graph_store.close()
                reset_graph_store()
            except Exception as e:
                logger.warning(f"GraphStore cleanup: {e}")
            self._orchestrator_ref = None
        
        return {
            "success": True,
            "message": "Resources cleared. Other IDEs can now access databases.",
            "status": self.status
        }
    
    def _clear_all_stale_locks(self):
        """Clear any stale lock files."""
        for path in [WRITE_LOCK_FILE, MASTER_LOCK_FILE]:
            if path.exists():
                lock = TransactionLock()
                lock._lock_path = path
                if lock._is_lock_stale():
                    lock._clear_stale_lock()
    
    def set_orchestrator_ref(self, orchestrator):
        """Store reference to orchestrator for cleanup."""
        self._orchestrator_ref = orchestrator
    
    def get_disabled_response(self, tool_name: str) -> Dict[str, Any]:
        """
        DEPRECATED in v1.1.0 - operations should not be blocked.
        
        Kept for backward compatibility but should rarely be called.
        """
        return {
            "success": False,
            "elefante_mode": "transaction-scoped",
            "message": f"Tool '{tool_name}' temporarily unavailable - another process is writing.",
            "reason": "Write lock held by another process. Retry in a moment.",
            "lock_status": self.check_locks(),
            "help": [
                "1. Wait a few seconds and retry (locks are short-lived)",
                "2. If persistent, another IDE may have crashed - restart it",
                "3. Check lock status with elefanteSystemStatusGet"
            ]
        }


# Global instance
_mode_manager: Optional[ElefanteModeManager] = None


def get_mode_manager() -> ElefanteModeManager:
    """Get the global ElefanteModeManager instance."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ElefanteModeManager()
    return _mode_manager


def is_elefante_enabled() -> bool:
    """Always returns True in v1.1.0 - operations auto-acquire locks."""
    return True


def require_elefante_mode(func):
    """
    DEPRECATED decorator in v1.1.0.
    
    Kept for backward compatibility - just passes through to function.
    Operations should use write_transaction() context manager instead.
    """
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@contextmanager
def write_lock(timeout: float = DEFAULT_ACQUIRE_TIMEOUT):
    """
    Convenience function for write operations.
    
    Usage:
        with write_lock() as lock:
            if lock.acquired:
                # do write operation
    """
    manager = get_mode_manager()
    with manager.write_transaction(timeout) as txn:
        yield txn


@contextmanager
def read_lock():
    """
    Convenience function for read operations (no-op, reads are lock-free).
    """
    manager = get_mode_manager()
    with manager.read_transaction() as txn:
        yield txn
