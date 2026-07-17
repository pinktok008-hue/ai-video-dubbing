"""
core/logger.py
===============
Centralized logging configuration for the AI Video Dubbing Platform V3.

Every module in this project obtains its logger via `get_logger(__name__)`
so that log formatting, log level, console output, and rotating file
output are all configured in exactly one place.

Python: 3.12
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

from config import settings

# Module-level cache so repeated calls to get_logger() for the same name
# return the exact same configured logger instance instead of re-attaching
# handlers (which would duplicate log lines).
_configured_loggers: Dict[str, logging.Logger] = {}

_ROOT_LOGGER_NAME = "dubbing_platform"


def _build_formatter() -> logging.Formatter:
    """Builds the shared log formatter from configuration."""
    return logging.Formatter(fmt=settings.LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


def _build_file_handler() -> RotatingFileHandler:
    """
    Builds a rotating file handler that writes to the configured log
    directory, rotating once the log file exceeds LOG_FILE_MAX_BYTES,
    keeping LOG_FILE_BACKUP_COUNT backup files.
    """
    log_file_path: Path = settings.LOG_DIR / settings.LOG_FILE_NAME
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_build_formatter())
    return handler


def _build_console_handler() -> logging.StreamHandler:
    """Builds a console (stdout) handler."""
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_build_formatter())
    return handler


def _get_root_logger() -> logging.Logger:
    """
    Returns the single root logger for the application, configuring its
    handlers exactly once regardless of how many times this is called.
    """
    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)

    if not root_logger.handlers:
        root_logger.setLevel(settings.LOG_LEVEL)
        root_logger.propagate = False

        root_logger.addHandler(_build_file_handler())

        if settings.LOG_TO_CONSOLE:
            root_logger.addHandler(_build_console_handler())

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Returns a namespaced child logger (e.g. `services.audio_extractor`)
    that inherits the handlers and level of the shared root logger.

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A fully configured `logging.Logger` instance.
    """
    if name in _configured_loggers:
        return _configured_loggers[name]

    _get_root_logger()  # Ensures root handlers exist before children log.

    child_logger = logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
    child_logger.setLevel(settings.LOG_LEVEL)
    child_logger.propagate = True

    _configured_loggers[name] = child_logger
    return child_logger
