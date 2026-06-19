from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_FILE = "logs/app.log"
DEFAULT_MAX_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FILES = 5
DEFAULT_LEVEL = "info"


@dataclass(frozen=True)
class FileLoggerConfig:
    enabled: bool
    file_path: str
    max_size_bytes: int
    max_files: int
    console: bool
    level: str


def _truthy(raw: str | None, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_max_size_bytes(raw: str | None) -> int:
    if not raw or not raw.strip():
        return DEFAULT_MAX_SIZE_BYTES
    text = raw.strip().lower()
    import re

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(b|kb|mb|gb)?", text)
    if not match:
        try:
            value = int(text)
            return value if value > 0 else DEFAULT_MAX_SIZE_BYTES
        except ValueError:
            return DEFAULT_MAX_SIZE_BYTES
    amount = float(match.group(1))
    unit = match.group(2) or "b"
    multipliers = {"b": 1, "kb": 1024, "mb": 1024 * 1024, "gb": 1024 * 1024 * 1024}
    return int(amount * multipliers.get(unit, 1))


def _resolve_log_file_path() -> str:
    from app.core.config import settings

    raw = (
        (settings.log_file or "").strip()
        or (settings.log_file_path or "").strip()
        or (os.getenv("LOG_FILE") or "").strip()
        or DEFAULT_FILE
    )
    return str(Path(raw).resolve() if Path(raw).is_absolute() else (Path.cwd() / raw).resolve())


def resolve_file_logger_config() -> FileLoggerConfig:
    from app.core.config import settings

    max_files = settings.log_file_max_files
    if max_files < 1:
        max_files = DEFAULT_MAX_FILES

    app_env = settings.app_env.strip().lower()
    default_console = app_env != "production"

    return FileLoggerConfig(
        enabled=settings.log_file_enabled,
        file_path=_resolve_log_file_path(),
        max_size_bytes=_parse_max_size_bytes(settings.log_file_max_size),
        max_files=max_files,
        console=settings.log_console if settings.log_console is not None else default_console,
        level=(settings.log_level or DEFAULT_LEVEL).lower(),
    )


def ensure_log_directory(file_path: str) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def _level_value(level_name: str) -> int:
    value = logging.getLevelName(level_name.upper())
    return value if isinstance(value, int) else logging.INFO


def setup_logging() -> None:
    """Configure root logging with optional rotating file + console handlers."""
    config = resolve_file_logger_config()
    level = _level_value(config.level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handlers: list[logging.Handler] = []

    if config.enabled:
        ensure_log_directory(config.file_path)
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_size_bytes,
            backupCount=max(0, config.max_files - 1),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        handlers.append(file_handler)

    if config.console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        handlers.append(console_handler)

    if not handlers:
        null_handler = logging.NullHandler()
        null_handler.setLevel(level)
        handlers.append(null_handler)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in handlers:
        root.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        named = logging.getLogger(logger_name)
        named.handlers.clear()
        named.propagate = True
        named.setLevel(level)

    logging.getLogger(__name__).info(
        "Logging initialized (file=%s, console=%s, level=%s)",
        config.file_path if config.enabled else "disabled",
        config.console,
        config.level,
    )
