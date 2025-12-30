"""
Logging configuration for Elefante memory system

Provides structured logging with JSON formatting and file rotation.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
import structlog


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_size: str = "10MB",
    backup_count: int = 5,
    console: bool = True,
    format_type: str = "json"
) -> None:
    """
    Set up structured logging for Elefante
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None for no file logging)
        max_size: Maximum log file size before rotation (e.g., "10MB")
        backup_count: Number of backup files to keep
        console: Whether to log to console
        format_type: Log format ("json" or "text")
    """
    # Convert log level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        
        if format_type == "json":
            formatter = logging.Formatter(
                '{"timestamp":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse max_size (e.g., "10MB" -> 10485760 bytes)
        max_bytes = _parse_size(max_size)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        
        if format_type == "json":
            formatter = logging.Formatter(
                '{"timestamp":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def _parse_size(size_str: str) -> int:
    """
    Parse size string to bytes
    
    Args:
        size_str: Size string (e.g., "10MB", "1GB")
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    # Extract number and unit
    number = ""
    unit = ""
    for char in size_str:
        if char.isdigit() or char == '.':
            number += char
        else:
            unit += char
    
    try:
        size = float(number)
    except ValueError:
        size = 10.0  # Default to 10
    
    # Convert to bytes
    unit = unit.strip()
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
    }
    
    multiplier = multipliers.get(unit, 1024 * 1024)  # Default to MB
    return int(size * multiplier)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


# Context manager for adding context to logs
class LogContext:
    """
    Context manager for adding context to logs
    
    Usage:
        with LogContext(request_id="123", user="alice"):
            logger.info("processing request")
    """
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None
    
    def __enter__(self):
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())
        return False


# Convenience function to log with context
def log_with_context(logger: structlog.BoundLogger, level: str, message: str, **context):
    """
    Log a message with additional context
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context key-value pairs
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, **context)


# Initialize default logging on module import
def _init_default_logging():
    """Initialize default logging configuration"""
    try:
        from src.utils.config import get_config
        config = get_config()
        
        setup_logging(
            level=config.elefante.logging.level,
            log_file=config.elefante.logging.file,
            max_size=config.elefante.logging.max_size,
            backup_count=config.elefante.logging.backup_count,
            console=config.elefante.logging.console,
            format_type=config.elefante.logging.format
        )
    except Exception:
        # Fallback to basic logging if config fails
        setup_logging(level="INFO", console=True, format_type="text")


# Auto-initialize logging when module is imported
_init_default_logging()

