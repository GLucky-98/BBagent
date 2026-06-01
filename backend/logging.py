import logging
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4 as uuid


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
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }

        op = getattr(record, "operation", None)
        if op:
            entry["op"] = op
        agent = getattr(record, "agent_name", None)
        if agent:
            entry["agent"] = agent
        dur = getattr(record, "duration_ms", None)
        if dur is not None:
            entry["dur_ms"] = dur
        status = getattr(record, "status", None)
        if status:
            entry["status"] = status

        if record.exc_info and record.exc_info[1]:
            entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "msg": str(record.exc_info[1]),
            }

        json_str = json.dumps(entry, ensure_ascii=False, default=str)
        level_prefix = f"{record.levelname}:".ljust(10)
        color = self._LEVEL_COLORS.get(record.levelname, "")
        level_prefix = f"{color}{level_prefix}{self._RESET}"
        return level_prefix + json_str


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
