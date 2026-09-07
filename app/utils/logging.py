"""Structured logging: console + rotating ``app.log`` / ``error.log`` files."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

_DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB
_DEFAULT_BACKUP_COUNT = 3


def configure_logging(
    log_level: str = "INFO",
    *,
    logs_dir: Path | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
) -> Path | None:
    """Configure structlog + stdlib logging.

    * **stdout** — JSON lines (always)
    * ``{logs_dir}/app.log`` — INFO+ (rotating), if the directory is writable
    * ``{logs_dir}/error.log`` — ERROR+ only, if writable

    Returns the logs directory when file handlers were attached, else ``None``.
    File-permission problems never crash the process: console logging remains.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parents[2] / "logs"
    else:
        logs_dir = Path(logs_dir)

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

    files_ok = False
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        # Probe write access before attaching handlers.
        probe = logs_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

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
        files_ok = True
    except OSError as exc:
        # PermissionError on a Docker volume mount is the usual case.
        root.warning(
            "file_logging_disabled dir=%s error=%s — console only",
            logs_dir,
            exc,
        )

    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    if files_ok:
        root.info(
            "logging_configured dir=%s max_bytes=%s backups=%s level=%s",
            logs_dir,
            max_bytes,
            backup_count,
            log_level.upper(),
        )
    else:
        root.info(
            "logging_configured console_only level=%s",
            log_level.upper(),
        )

    return logs_dir if files_ok else None


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger for ``name`` (usually ``__name__``)."""
    return structlog.get_logger(name)
