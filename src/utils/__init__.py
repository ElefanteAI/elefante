"""Utility modules for Elefante memory system.

Keep package import dependency-free so standard-library-only utilities remain
available during clean installer preflight. Runtime conveniences load lazily.
"""


def __getattr__(name: str):
    if name in {"Config", "get_config"}:
        from src.utils.config import Config, get_config

        return {"Config": Config, "get_config": get_config}[name]
    if name in {"get_logger", "setup_logging"}:
        from src.utils.logger import get_logger, setup_logging

        return {"get_logger": get_logger, "setup_logging": setup_logging}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Config",
    "get_config",
    "get_logger",
    "setup_logging",
]
