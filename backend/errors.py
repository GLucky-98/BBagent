import traceback
from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_ALREADY_EXISTS = "AGENT_ALREADY_EXISTS"
    AGENT_ALREADY_RUNNING = "AGENT_ALREADY_RUNNING"
    AGENT_NOT_RUNNING = "AGENT_NOT_RUNNING"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TEAM_NOT_FOUND = "TEAM_NOT_FOUND"
    MCP_NOT_FOUND = "MCP_NOT_FOUND"
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"
    PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
    AGENT_CREATE_FAILED = "AGENT_CREATE_FAILED"
    AGENT_START_FAILED = "AGENT_START_FAILED"
    AGENT_STOP_FAILED = "AGENT_STOP_FAILED"
    TEAM_START_FAILED = "TEAM_START_FAILED"
    TEAM_STOP_FAILED = "TEAM_STOP_FAILED"
    SESSION_SWITCH_FAILED = "SESSION_SWITCH_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TOOLCONFIG_NOT_FOUND = "TOOLCONFIG_NOT_FOUND"
    TOOLCONFIG_INVALID = "TOOLCONFIG_INVALID"


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str = "",
                 status_code: int = 500, detail: str = ""):
        self.code = code
        self.message = message or code.value
        self.status_code = status_code
        self.detail = detail

    def to_response(self, include_traceback: bool = False) -> dict:
        resp = {
            "error": {
                "code": self.code.value,
                "message": self.message,
            }
        }
        if self.detail:
            resp["error"]["detail"] = self.detail
        if include_traceback:
            resp["error"]["traceback"] = traceback.format_exc()
        return resp


class NotFoundError(AppError):
    def __init__(self, code: ErrorCode, message: str = "", detail: str = ""):
        super().__init__(code, message, status_code=404, detail=detail)


class ConflictError(AppError):
    def __init__(self, code: ErrorCode, message: str = "", detail: str = ""):
        super().__init__(code, message, status_code=409, detail=detail)


class InternalError(AppError):
    def __init__(self, message: str = "", detail: str = "",
                 code: ErrorCode = ErrorCode.INTERNAL_ERROR):
        super().__init__(code, message, status_code=500, detail=detail)

    @classmethod
    def from_exception(cls, e: Exception) -> "InternalError":
        return cls(
            message=str(e),
            detail=traceback.format_exc(),
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(include_traceback=True),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    err = InternalError.from_exception(exc)
    return JSONResponse(
        status_code=err.status_code,
        content=err.to_response(include_traceback=True),
    )
