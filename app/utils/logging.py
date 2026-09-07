"""Structured logging: console + rotating ``app.log`` / ``error.log`` files."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

# Defaults when callers omit size settings.
_DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB
_DEFAULT_BACKUP_COUNT = 3


def configure_logging(
    log_level: str = "INFO",
    *,
    logs_dir: Path | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
) -> Path:
    """Configure structlog + stdlib logging.

    * **stdout** — JSON lines (same shape as the files)
    * ``{logs_dir}/app.log`` — INFO+ (rotating)
    * ``{logs_dir}/error.log`` — ERROR+ only (rotating)

    Returns the resolved logs directory (created if missing).

    Must be called **before** the first ``get_logger()`` use in the process
    (or re-call after clearing handler state). ``app.main`` configures
    logging as the first step inside ``main()``.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if logs_dir is None:
        # app/utils/logging.py → parents: utils, app, project root
        logs_dir = Path(__file__).resolve().parents[2] / "logs"
    else:
        logs_dir = Path(logs_dir)

    logs_dir.mkdir(parents=True, exist_ok=True)

    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    json_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(json_formatter)
    root.addHandler(console)

    app_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=max(max_bytes, 1024),
        backupCount=max(backup_count, 1),
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(json_formatter)
    root.addHandler(app_handler)

    error_handler = RotatingFileHandler(
        logs_dir / "error.log",
        maxBytes=max(max_bytes, 1024),
        backupCount=max(backup_count, 1),
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root.addHandler(error_handler)

    # Reduce library noise (per-update "handled in N ms", etc.).
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Confirm path once on the root logger (goes to console + app.log).
    root.info(
        "logging_configured dir=%s max_bytes=%s backups=%s level=%s",
        logs_dir,
        max_bytes,
        backup_count,
        log_level.upper(),
    )
    return logs_dir


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger for ``name`` (usually ``__name__``)."""
    return structlog.get_logger(name)
