import asyncio
import inspect
import json
import logging
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from .tool import Tool

_SAFE_TOOL_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
_UNDERSCORE_RUN_RE = re.compile(r"_+")


def _slug_tool_name_part(value: str, fallback: str) -> str:
    slug = _SAFE_TOOL_NAME_RE.sub("_", value)
    slug = _UNDERSCORE_RUN_RE.sub("_", slug).strip("_")
    return slug or fallback


def make_safe_mcp_runtime_name(server_name: str, tool_name: str) -> str:
    server_slug = _slug_tool_name_part(server_name, "server")
    tool_slug = _slug_tool_name_part(tool_name, "tool")
    return f"mcp__{server_slug}__{tool_slug}"

@dataclass
class MCPServerConfig:
    name: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, json_str: str) -> "MCPServerConfig":
        data = json.loads(json_str)
        return cls(
            name=data.get("name", ""),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {})
        )

    @classmethod
    def from_json_file(cls, file_path: str) -> "MCPServerConfig":
        with open(file_path, encoding='utf-8') as f:
            return cls.from_json(f.read())

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def to_json_file(self, file_path: str, indent: int = 2) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json(indent))

# ------------------------------------------------------------
# MCP JSON-RPC message construction helper functions
# ------------------------------------------------------------
def make_request(id: int, method: str, params: dict | None = None) -> str:
    req: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
    }
    if params is not None:
        req["params"] = params
    return json.dumps(req)

def make_notification(method: str, params: dict | None = None) -> str:
    notif: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        notif["params"] = params
    return json.dumps(notif)

# ------------------------------------------------------------
# MCP client class
# ------------------------------------------------------------
class MCPClient:
    def __init__(self, mcp_server_config: MCPServerConfig, logger: logging.Logger | None = None):
        self.name = mcp_server_config.name
        self.config = mcp_server_config
        self.command = [mcp_server_config.command, *mcp_server_config.args]
        self.env = {**os.environ, **mcp_server_config.env}
        self.process: asyncio.subprocess.Process | None = None
        self.request_id = 0
        self.pending_requests: dict[int, asyncio.Future] = {}
        self.state = 'inactive'
        self._initial_tools: list[dict] = []
        self._logger = logger or logging.getLogger(f"mcp.{self.name}")
        self._background_tasks: list[asyncio.Task] = []

    def _log(self, msg: str, level: str = "info", context: dict | None = None):
        log_func = getattr(self._logger, level, self._logger.info)
        log_func(msg, extra={"context": context or {}})

    async def start(self):
        """Start MCP server subprocess and begin reading messages"""
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env
        )
        self._background_tasks.append(asyncio.create_task(self._read_stdout()))
        self._background_tasks.append(asyncio.create_task(self._read_stderr()))

    async def _read_stdout(self):
        """Continuously read server stdout, parse JSON-RPC messages"""
        if not self.process or not self.process.stdout:
            return

        buffer = b""
        while True:
            try:
                chunk = await self.process.stdout.read(4096)
                if not chunk:
                    break

                buffer += chunk

                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    line = line.decode('utf-8').strip()

                    if not line:
                        continue

                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        self._log(f"Invalid JSON: {line}", level="warning")
                        continue

                    if "id" in msg and msg["id"] in self.pending_requests:
                        future = self.pending_requests.pop(msg["id"])
                        if "error" in msg:
                            future.set_exception(Exception(msg["error"].get("message", "Unknown error")))
                        else:
                            future.set_result(msg.get("result"))
                    elif "method" in msg:
                        await self._handle_notification(msg)
                    else:
                        self._log(f"Unhandled message: {msg}", level="debug")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log(f"Error reading stdout: {e}", level="error")
                break

    async def _read_stderr(self):
        """Print server stderr output to console (for debugging)"""
        if not self.process or not self.process.stderr:
            return
        async for line in self.process.stderr:
            self._log(f"[MCPServer {self.name}] {line.decode('utf-8').rstrip()}", level="debug")

    async def _handle_notification(self, msg: dict):
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "notifications/progress":
            progress = params.get("progress")
            total = params.get("total")
            self._log(f"Progress: {progress}/{total}", level="debug")
        else:
            self._log(f"Received notification: {method} {params}", level="debug")

    async def send_request(self, method: str, params: dict | None = None) -> Any:
        """Send JSON-RPC request and wait for response"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started or stdin closed")

        self.request_id += 1
        req_id = self.request_id
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[req_id] = future

        req_str = make_request(req_id, method, params)
        self.process.stdin.write((req_str + "\n").encode())
        await self.process.stdin.drain()

        # wait for response (with timeout)
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {method} timed out") from None

    async def send_notification(self, method: str, params: dict | None = None):
        """Send notification (without waiting for response)"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started or stdin closed")

        notif_str = make_notification(method, params)
        self.process.stdin.write((notif_str + "\n").encode())
        await self.process.stdin.drain()

    async def initialize(self):
        """Perform MCP initialization handshake"""
        # 1. send initialize request
        server_info = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},  # client capabilities (empty in this case)
            "clientInfo": {
                "name": self.name,
                "version": "0.1.0"
            }
        })

        # ⭐ 2. server may proactively push tool list, register Future to wait
        # MCP protocol allows server to proactively push after initialization
        tools_future = asyncio.get_event_loop().create_future()
        self.pending_requests[2] = tools_future  # register id=2

        # 3. send initialized notification (handshake complete)
        await self.send_notification("notifications/initialized")

        # ⭐ 4. wait for server-pushed tool list (up to 3 seconds)
        try:
            tools_result = await asyncio.wait_for(tools_future, timeout=3.0)
            if tools_result:
                self._log(f"Server pushed tools: {len(tools_result.get('tools', []))} tools", level="info")
                self._initial_tools = tools_result.get("tools", [])
        except asyncio.TimeoutError:
            self._log("No tools pushed by server during init", level="info")
            self._initial_tools = []

        self.state = 'active'
        return server_info

    async def list_tools(self) -> list[dict]:
        """Get the list of tools provided by the server"""
        # ⭐ if server already pushed tools during init, return directly
        if self._initial_tools:
            return self._initial_tools

        # otherwise send request to fetch
        result = await self.send_request("tools/list")
        if not isinstance(result, dict):
            return []
        return cast(list[dict], result.get("tools", []))

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call the specified tool"""
        result = await self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return result

    async def create_tools(self) -> list["MCPTool"]:
        """Get tool list and wrap as MCPTool objects"""
        tools_data = await self.list_tools()
        return [MCPTool(self, t) for t in tools_data]

    async def close(self):
        """Close subprocess"""
        if self.process:
            for task in self._background_tasks:
                task.cancel()
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

            if self.process.stdin and not self.process.stdin.is_closing():
                self.process.stdin.close()

            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.state = 'inactive'
            self.process = None

class MCPTool(Tool):
    def __init__(self, mcp_client: MCPClient, config: dict[str, Any]):
        self.mcp_server_name = mcp_client.name
        self.raw_name = config["name"]
        func = self.create_tool_from_config(mcp_client, config)
        super().__init__(
            func,
            source="mcp",
        )

    @staticmethod
    def create_tool_from_config(mcp_client: MCPClient, config: dict[str, Any]) -> Callable[..., Any]:
        """
        Generate a callable function from a tool config dict.
        Config format example:
        {
            "name": "text_to_image",
            "description": "Generate a image from a prompt...",
            "inputSchema": {
                "properties": {
                    "model": {"type": "string", "default": "image-01"},
                    "prompt": {"type": "string", "default": ""},
                    "aspect_ratio": {"type": "string", "default": "1:1"},
                    "n": {"type": "integer", "default": 1},
                    "prompt_optimizer": {"type": "boolean", "default": True},
                    "output_directory": {"type": "string"}
                },
                "required": ["output_directory"]  # optional, but we can infer from default
            }
        }
        The returned function has:
            - __name__ == config["name"]
            - __doc__ == config["description"]
            - parameter signature matches inputSchema, with correct default values
        """
        func_name = make_safe_mcp_runtime_name(mcp_client.name, config["name"])
        func_doc = config["description"]
        schema = config["inputSchema"]
        properties = schema.get("properties", {})

        # store default value mapping
        defaults = {}
        # store parameter type annotation mapping (optional, for readability)
        annotations = {}

        type_mapping = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "number": float,
        }

        for param_name, param_info in properties.items():
            param_type_str = param_info.get("type", "string")
            param_type = type_mapping.get(param_type_str, str)
            annotations[param_name] = param_type

            # handle default values
            if "default" in param_info:
                default_val = param_info["default"]
                defaults[param_name] = default_val
                # params with defaults are represented as param=default in signature
            else:
                # no default value, required parameter
                defaults[param_name] = inspect.Parameter.empty

        # build inspect.Parameter objects
        parameters = []
        for param_name, param_type in annotations.items():
            default = defaults.get(param_name, inspect.Parameter.empty)
            # if param has default, kind is POSITIONAL_OR_KEYWORD, otherwise also
            # note: we only support positional or keyword params, simple handling
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
            param = inspect.Parameter(
                name=param_name,
                kind=kind,
                default=default,
                annotation=param_type
            )
            parameters.append(param)

        # create function signature
        sig = inspect.Signature(parameters=parameters)

        async def tool_func(*args, **kwargs):
            # bind parameters, apply defaults
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments

            result = await mcp_client.call_tool(config["name"], arguments)
            return json.dumps(result)

        # set function metadata
        tool_func.__name__ = func_name
        tool_func.__doc__ = func_doc
        cast(Any, tool_func).__signature__ = sig
        tool_func.__annotations__ = annotations

        return tool_func

_config_logger = logging.getLogger("mcp.config")


def parse_config_dict(data: dict, default_name: str = "") -> list[MCPServerConfig]:
    """Parse a JSON dict into MCPServerConfig list.

    Supported formats:
      - Single server: {name, command, args?, env?}
      - Multi-server:  {mcpServers: {name: {command, args?, env?}, ...}}
      - List:          {mcpServers: [{name, command, ...}, ...]}

    Args:
        data: Parsed JSON dict.
        default_name: Fallback name when an entry lacks one (used by importers).
    """
    configs: list[MCPServerConfig] = []

    if "mcpServers" in data:
        servers = data["mcpServers"]
        if isinstance(servers, list):
            for entry in servers:
                if not isinstance(entry, dict) or "command" not in entry:
                    continue
                configs.append(MCPServerConfig(
                    name=entry.get("name", default_name),
                    command=entry.get("command", ""),
                    args=entry.get("args", []),
                    env=entry.get("env", {}),
                ))
        elif isinstance(servers, dict):
            for name, server_data in servers.items():
                if not isinstance(server_data, dict) or "command" not in server_data:
                    continue
                configs.append(MCPServerConfig(
                    name=name,
                    command=server_data.get("command", ""),
                    args=server_data.get("args", []),
                    env=server_data.get("env", {}),
                ))
    elif "name" in data and "command" in data:
        configs.append(MCPServerConfig(
            name=data.get("name", default_name),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
        ))

    return configs


def parse_config_file(file_path: str) -> list[MCPServerConfig]:
    """Parse a single JSON config file. Delegates to parse_config_dict."""
    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _config_logger.warning(f"Failed to parse {file_path}: {e}")
        return []
    return parse_config_dict(data)


def load_configs(config_dir: str) -> dict[str, MCPServerConfig]:
    """Scan all JSON files in directory, load MCP configs matching the format

    Returns:
        Dict[str, MCPServerConfig]: config dict keyed by name
    """
    result: dict[str, MCPServerConfig] = {}
    if not os.path.isdir(config_dir):
        _config_logger.warning(f"Config directory not found: {config_dir}")
        return result

    count = 0
    for filename in sorted(os.listdir(config_dir)):
        if not filename.endswith(".json"):
            continue
        file_path = os.path.join(config_dir, filename)
        configs = parse_config_file(file_path)
        for cfg in configs:
            if cfg.name and cfg.command:
                result[cfg.name] = cfg
                count += 1
    _config_logger.info(f"Loaded {count} MCP server config(s) from {config_dir}")
    return result
