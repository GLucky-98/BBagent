import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional


class BackendFormatter(logging.Formatter):
    _LEVEL_COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        level = record.levelname.ljust(8)
        module = record.name
        msg = record.getMessage()

        op = getattr(record, "operation", None)
        agent = getattr(record, "agent_name", None)
        dur = getattr(record, "duration_ms", None)
        status = getattr(record, "status", None)

        parts = []
        if op:
            parts.append(f"op={op}")
        if agent:
            parts.append(f"agent={agent}")
        if dur is not None:
            parts.append(f"dur={dur}ms")
        if status:
            parts.append(f"status={status}")
        extra = " ".join(parts)
        if extra:
            msg = f"{msg} [{extra}]"

        color = self._LEVEL_COLORS.get(record.levelname, "")
        reset = self._RESET
        line = f"{color}{level}{reset} {ts} {module} {msg}"

        if record.exc_info and record.exc_info[1]:
            line += f"\n{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"

        return line


_BACKEND_HANDLER: Optional[logging.Handler] = None


def get_backend_logger(name: str) -> logging.Logger:
    global _BACKEND_HANDLER
    logger = logging.getLogger(f"bb.{name}")

    if _BACKEND_HANDLER is not None:
        logger.handlers.clear()
        logger.addHandler(_BACKEND_HANDLER)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


def setup_backend_logging():
    global _BACKEND_HANDLER
    handler = logging.StreamHandler()
    handler.setFormatter(BackendFormatter())
    handler.setLevel(logging.DEBUG)
    _BACKEND_HANDLER = handler

    # reconfigure all existing backend loggers
    root = logging.getLogger("bb")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    root.propagate = False


def get_uvicorn_log_config() -> dict:
    """Return a log config dict for uvicorn that uses BackendFormatter."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "backend": {
                "()": BackendFormatter,
            },
        },
        "handlers": {
            "backend_stream": {
                "class": "logging.StreamHandler",
                "formatter": "backend",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["backend_stream"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["backend_stream"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["backend_stream"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


@contextmanager
def log_operation(logger: logging.Logger, operation: str, agent_name: str = ""):
    start = time.monotonic()
    extra = {"operation": operation}
    if agent_name:
        extra["agent_name"] = agent_name
    logger.info("[OP] %s started", operation, extra=extra)
    try:
        yield
        elapsed_ms = int((time.monotonic() - start) * 1000)
        extra["status"] = "ok"
        extra["duration_ms"] = elapsed_ms
        logger.info("[OP] %s done in %dms", operation, elapsed_ms, extra=extra)
    except Exception:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        extra["status"] = "error"
        extra["duration_ms"] = elapsed_ms
        logger.error("[OP] %s failed after %dms", operation, elapsed_ms, extra=extra, exc_info=True)
        raise
