import logging
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from uuid import uuid4 as uuid


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra_context = getattr(record, 'context', None) or {}

        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "agent": getattr(record, 'agent_name', record.name),
            "trace_id": getattr(record, 'trace_id', ''),
            "span_id": getattr(record, 'span_id', ''),
            "message": record.getMessage(),
        }

        if extra_context:
            log_entry["context"] = extra_context

        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "detail": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ContextFilter(logging.Filter):
    def __init__(self, logger_instance: 'AgentLogger'):
        super().__init__()
        self._logger = logger_instance

    def filter(self, record):
        record.trace_id = self._logger.trace_id
        record.span_id = self._logger.current_span_id
        record.agent_name = self._logger.name
        return True


class AgentLogger:
    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        level: int = logging.DEBUG,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        propagate: bool = False,
    ):
        self.name = name
        self._level = level
        self._log_dir = log_dir

        self._logger = logging.getLogger(f"agent.{name}.{uuid().hex[:8]}")
        self._logger.setLevel(level)
        self._logger.propagate = propagate
        self._logger.handlers.clear()

        self._trace_id = ""
        self._span_stack: List[str] = []

        self._context_filter = ContextFilter(self)
        self._logger.addFilter(self._context_filter)

        self._console_handler = logging.StreamHandler(sys.stderr)
        self._console_handler.setLevel(console_level)
        self._console_handler.setFormatter(StructuredFormatter())
        self._logger.addHandler(self._console_handler)

        self._file_handler: Optional[logging.FileHandler] = None
        if log_dir is not None:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"{name}.log"
            self._file_handler = logging.FileHandler(str(log_path), encoding='utf-8')
            self._file_handler.setLevel(file_level)
            self._file_handler.setFormatter(StructuredFormatter())
            self._logger.addHandler(self._file_handler)

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def current_span_id(self) -> str:
        return self._span_stack[-1] if self._span_stack else ""

    def set_trace_id(self, trace_id: str = ""):
        self._trace_id = trace_id or uuid().hex[:12]

    def clear_trace_id(self):
        self._trace_id = ""

    @contextmanager
    def span(self, span_name: str):
        span_id = f"{span_name}_{uuid().hex[:6]}"
        self._span_stack.append(span_id)
        try:
            yield
        finally:
            self._span_stack.pop()

    def _log(self, level: int, msg: str, context: dict = None, exc_info=None):
        self._logger.log(level, msg, extra={"context": context or {}}, exc_info=exc_info)

    def debug(self, msg: str, context: dict = None):
        self._log(logging.DEBUG, msg, context)

    def info(self, msg: str, context: dict = None):
        self._log(logging.INFO, msg, context)

    def warning(self, msg: str, context: dict = None):
        self._log(logging.WARNING, msg, context)

    def error(self, msg: str, context: dict = None, exc_info=None):
        self._log(logging.ERROR, msg, context, exc_info=exc_info)

    def fatal(self, msg: str, context: dict = None, exc_info=None):
        self._log(logging.CRITICAL, msg, context, exc_info=exc_info)

    def add_handler(self, handler: logging.Handler):
        self._logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler):
        self._logger.removeHandler(handler)

    def set_level(self, level: int):
        self._logger.setLevel(level)

    def set_console_level(self, level: int):
        self._console_handler.setLevel(level)

    def set_file_level(self, level: int):
        if self._file_handler:
            self._file_handler.setLevel(level)

    @property
    def logger(self) -> logging.Logger:
        return self._logger


class _NullLogger:
    """No-op logger that implements the same logging interface as AgentLogger.

    Used by SubAgent when no logger is provided, so that logging calls
    can be made unconditionally without None-checking.
    """

    def debug(self, msg: str, context: dict = None):
        pass

    def info(self, msg: str, context: dict = None):
        pass

    def warning(self, msg: str, context: dict = None):
        pass

    def error(self, msg: str, context: dict = None, exc_info=None):
        pass

    def fatal(self, msg: str, context: dict = None, exc_info=None):
        pass

    @contextmanager
    def span(self, span_name: str):
        yield
