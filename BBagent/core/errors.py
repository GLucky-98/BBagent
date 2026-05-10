from enum import Enum
from dataclasses import dataclass, field
from typing import List


class ErrorCategory(Enum):
    TOOL_ERROR = "tool_error"
    MODEL_ERROR = "model_error"
    FATAL_ERROR = "fatal_error"


class ToolErrorType(Enum):
    MISSING_PARAMETER = "MissingParameter"
    PATH_NOT_FOUND = "PathNotFound"
    PERMISSION_DENIED = "PermissionDenied"
    INVALID_INPUT = "InvalidInput"
    INVALID_FILE_TYPE = "InvalidFileType"
    TYPE_MISMATCH = "TypeMismatch"
    TOOL_NOT_FOUND = "ToolNotFound"
    TIMEOUT = "Timeout"
    EXECUTION_ERROR = "ExecutionError"
    COMMAND_FAILED = "CommandFailed"
    SKIPPED_FILE = "SkippedFile"
    UNKNOWN = "Unknown"


class ModelErrorType(Enum):
    RATE_LIMITED = "RateLimited"
    SERVER_ERROR = "ServerError"
    AUTH_ERROR = "AuthError"
    BAD_REQUEST = "BadRequest"
    NETWORK_ERROR = "NetworkError"
    STREAM_BROKEN = "StreamBroken"
    UNKNOWN = "Unknown"


@dataclass
class ErrorInferenceRule:
    pattern: str
    error_type: ToolErrorType
    suggestion: str


ERROR_INFERENCE_RULES: List[ErrorInferenceRule] = [
    ErrorInferenceRule(
        pattern=r"is required$",
        error_type=ToolErrorType.MISSING_PARAMETER,
        suggestion="Provide the required parameter and try again."
    ),
    ErrorInferenceRule(
        pattern=r"Path not found:|File not found:",
        error_type=ToolErrorType.PATH_NOT_FOUND,
        suggestion="The path does not exist. Use LS to list the directory contents, or Glob/Find to search for the correct file."
    ),
    ErrorInferenceRule(
        pattern=r"Path is not a directory",
        error_type=ToolErrorType.TYPE_MISMATCH,
        suggestion="The path you provided is a file, not a directory. Use LS on a directory path instead."
    ),
    ErrorInferenceRule(
        pattern=r"Cannot write to file|Cannot read file|permission denied",
        error_type=ToolErrorType.PERMISSION_DENIED,
        suggestion="Permission denied. Try a different path or check file permissions with Bash 'ls -la'."
    ),
    ErrorInferenceRule(
        pattern=r"Invalid regex",
        error_type=ToolErrorType.INVALID_INPUT,
        suggestion="The regex pattern is invalid. Check for unmatched brackets, invalid escape sequences, or other syntax errors."
    ),
    ErrorInferenceRule(
        pattern=r"not a valid text file",
        error_type=ToolErrorType.INVALID_FILE_TYPE,
        suggestion="The file appears to be binary, not text. Use Read on a text file instead."
    ),
    ErrorInferenceRule(
        pattern=r"Missing required parameter",
        error_type=ToolErrorType.MISSING_PARAMETER,
        suggestion="A required parameter was not provided. Check the tool's input schema and provide all required parameters."
    ),
    ErrorInferenceRule(
        pattern=r"Unknown tool:",
        error_type=ToolErrorType.TOOL_NOT_FOUND,
        suggestion="The tool name is not recognized. Check the available tools and use the correct name."
    ),
    ErrorInferenceRule(
        pattern=r"Working directory does not exist",
        error_type=ToolErrorType.PATH_NOT_FOUND,
        suggestion="The working directory does not exist. Verify the path or create it first."
    ),
    ErrorInferenceRule(
        pattern=r"Command timed out|Request.*timed out",
        error_type=ToolErrorType.TIMEOUT,
        suggestion="The command took too long and timed out. Try reducing the scope (e.g. fewer files, smaller search area) or increase the timeout parameter."
    ),
    ErrorInferenceRule(
        pattern=r"No matches found",
        error_type=ToolErrorType.EXECUTION_ERROR,
        suggestion="No matches were found for the given pattern. Try a broader pattern or search in a different directory."
    ),
    ErrorInferenceRule(
        pattern=r"Error finding files:|Error reading file:|Error writing file:|Error editing file:|Error listing directory:|Error searching files:|Error executing command:",
        error_type=ToolErrorType.EXECUTION_ERROR,
        suggestion="An unexpected error occurred during tool execution. Check the error details and try again with corrected parameters."
    ),
]
