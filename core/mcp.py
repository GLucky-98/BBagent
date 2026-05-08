import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
import inspect
from dataclasses import dataclass, field, asdict

from .tool import Tool

@dataclass
class MCPServerConfig:
    name: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

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
        with open(file_path, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def to_json_file(self, file_path: str, indent: int = 2) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json(indent))

# ------------------------------------------------------------
# MCP JSON-RPC 消息构造辅助函数
# ------------------------------------------------------------
def make_request(id: int, method: str, params: Optional[Dict] = None) -> str:
    req = {
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
    }
    if params is not None:
        req["params"] = params
    return json.dumps(req)

def make_notification(method: str, params: Optional[Dict] = None) -> str:
    notif = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        notif["params"] = params
    return json.dumps(notif)
    
# ------------------------------------------------------------
# MCP 客户端类
# ------------------------------------------------------------
class MCPClient:
    def __init__(self, MCPserver_config:MCPServerConfig, client_name: str):
        self.name = MCPserver_config.name
        self.client_name = client_name
        self.command = [MCPserver_config.command] + MCPserver_config.args
        self.env = {**os.environ, **MCPserver_config.env}   
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.state = 'inactive'
        self._initial_tools: List[Dict] = []  # ⭐ 存储初始化时服务器推送的工具

    async def start(self):
        """启动 MCP 服务器子进程并开始读取消息"""
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env
        )
        # 启动后台任务读取 stdout 消息
        asyncio.create_task(self._read_stdout())
        # 可选：打印 stderr 用于调试
        asyncio.create_task(self._read_stderr())

    async def _read_stdout(self):
        """持续读取服务器 stdout，解析 JSON-RPC 消息"""
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
                        print(f"Invalid JSON: {line}", file=sys.stderr)
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
                        print(f"Unhandled message: {msg}", file=sys.stderr)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error reading stdout: {e}", file=sys.stderr)
                break

    async def _read_stderr(self):
        """将服务器 stderr 输出打印到控制台（便于调试）"""
        if not self.process or not self.process.stderr:
            return
        async for line in self.process.stderr:
            print(f"[SERVER STDERR] {line.decode('utf-8').rstrip()}", file=sys.stderr)

    async def _handle_notification(self, msg: Dict):
        """处理服务器通知（例如进度更新）"""
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "notifications/progress":
            progress = params.get("progress")
            total = params.get("total")
            print(f"Progress: {progress}/{total}")
        else:
            print(f"Received notification: {method} {params}")

    async def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        """发送 JSON-RPC 请求并等待响应"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started or stdin closed")

        self.request_id += 1
        req_id = self.request_id
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[req_id] = future

        req_str = make_request(req_id, method, params)
        self.process.stdin.write((req_str + "\n").encode())
        await self.process.stdin.drain()

        # 等待响应（带超时）
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {method} timed out")

    async def send_notification(self, method: str, params: Optional[Dict] = None):
        """发送通知（不等待响应）"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started or stdin closed")
        
        notif_str = make_notification(method, params)
        self.process.stdin.write((notif_str + "\n").encode())
        await self.process.stdin.drain()

    async def initialize(self):
        """执行 MCP 初始化握手"""
        # 1. 发送 initialize 请求
        server_info = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},  # 客户端能力（本例为空）
            "clientInfo": {
                "name": self.client_name,
                "version": "0.1.0"
            }
        })
        
        # ⭐ 2. 服务器可能主动推送工具列表，注册 Future 等待
        # MCP 协议允许服务器在初始化后主动推送
        tools_future = asyncio.get_event_loop().create_future()
        self.pending_requests[2] = tools_future  # 注册 id=2
        
        # 3. 发送 initialized 通知（握手完成）
        await self.send_notification("notifications/initialized")
        
        # ⭐ 4. 等待服务器主动推送的工具列表（最多等3秒）
        try:
            tools_result = await asyncio.wait_for(tools_future, timeout=3.0)
            if tools_result:
                print(f"Server pushed tools: {len(tools_result.get('tools', []))} tools")
                self._initial_tools = tools_result.get("tools", [])
        except asyncio.TimeoutError:
            print("No tools pushed by server during init")
            self._initial_tools = []
        
        self.state = 'active'
        return server_info

    async def list_tools(self) -> List[Dict]:
        """获取服务器提供的工具列表"""
        # ⭐ 如果初始化时服务器已经推送了工具，直接返回
        if self._initial_tools:
            return self._initial_tools
        
        # 否则发送请求获取
        result = await self.send_request("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """调用指定工具"""
        result = await self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return result

    async def close(self):
        """关闭子进程"""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.state = 'inactive'
            self.process = None
            
class MCPTool(Tool):
    def __init__(self, mcp_client: MCPClient, config: Dict[str, Any]) :
        func = self.create_tool_from_config(mcp_client, config)
        super().__init__(func, has_state=True)
        
    @staticmethod
    def create_tool_from_config(mcp_client: MCPClient, config: Dict[str, Any]):
        """
        根据工具配置字典生成一个可调用函数。
        配置格式示例:
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
                "required": ["output_directory"]  # 可选，但我们可以从 default 判断
            }
        }
        返回的函数具有:
            - __name__ == config["name"]
            - __doc__ == config["description"]
            - 参数签名与 inputSchema 一致，并包含正确的默认值
        """
        func_name = mcp_client.name + "_" + config["name"]
        func_doc = config["description"]
        schema = config["inputSchema"]
        properties = schema.get("properties", {})

        # 存储默认值映射
        defaults = {}
        # 存储参数类型注解映射（可选，用于增强可读性）
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

            # 处理默认值
            if "default" in param_info:
                default_val = param_info["default"]
                defaults[param_name] = default_val
                # 有默认值的参数在签名中表示为 param=default
            else:
                # 无默认值，必填参数
                defaults[param_name] = inspect.Parameter.empty

        # 构建 inspect.Parameter 对象
        parameters = []
        for param_name, param_type in annotations.items():
            default = defaults.get(param_name, inspect.Parameter.empty)
            # 如果参数有默认值，kind 为 POSITIONAL_OR_KEYWORD，否则也是
            # 注意：我们仅支持位置或关键字参数，简单处理
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
            param = inspect.Parameter(
                name=param_name,
                kind=kind,
                default=default,
                annotation=param_type
            )
            parameters.append(param)

        # 创建函数签名
        sig = inspect.Signature(parameters=parameters)

        async def tool_func(*args, **kwargs):
            # 绑定参数，应用默认值
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments

            result = await mcp_client.call_tool(config["name"], arguments)
            return json.dumps(result)

        # 设置函数元信息
        tool_func.__name__ = func_name
        tool_func.__doc__ = func_doc
        tool_func.__signature__ = sig
        tool_func.__annotations__ = annotations

        return tool_func
    
class MCPManager:
    def __init__(self, config_dir: str = ""):
        self.config_dir: str = config_dir
        self.configs: Dict[str, MCPServerConfig] = {}
        self.clients: Dict[str, MCPClient] = {}
        self.client_tools: Dict[str, List[MCPTool]] = {}
        if config_dir:
            self._load_configs(config_dir)

    def _parse_config_file(self, file_path: str) -> List[MCPServerConfig]:
        """解析单个 JSON 配置文件，支持两种格式

        格式一（单服务器）：顶层含 name + command 字段
        格式二（多服务器）：顶层含 mcpServers 字段，key 为 name
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to parse {file_path}: {e}")
            return []

        configs: List[MCPServerConfig] = []

        if "mcpServers" in data and isinstance(data["mcpServers"], dict):
            for name, server_data in data["mcpServers"].items():
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
                name=data.get("name", ""),
                command=data.get("command", ""),
                args=data.get("args", []),
                env=data.get("env", {}),
            ))

        return configs

    def _load_configs(self, config_dir: str) -> None:
        """扫描目录下所有 JSON 文件，加载符合格式的配置"""
        if not os.path.isdir(config_dir):
            print(f"Warning: config directory not found: {config_dir}")
            return

        count = 0
        for filename in sorted(os.listdir(config_dir)):
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(config_dir, filename)
            configs = self._parse_config_file(file_path)
            for cfg in configs:
                if cfg.name and cfg.command:
                    self.configs[cfg.name] = cfg
                    count += 1
        print(f"Loaded {count} MCP server config(s) from {config_dir}")

    def add_config(self, config: MCPServerConfig) -> None:
        """运行时手动添加单个配置"""
        if config.name and config.command:
            self.configs[config.name] = config

    def create_client(self, name: str) -> Optional[MCPClient]:
        """根据配置实例化 MCPClient（仅创建，不启动进程）"""
        if name not in self.configs:
            print(f"Warning: config '{name}' not found")
            return None
        if name in self.clients:
            return self.clients[name]
        config = self.configs[name]
        client = MCPClient(config, client_name=name)
        self.clients[name] = client
        return client

    def create_all_clients(self) -> List[MCPClient]:
        """为所有已加载配置创建客户端实例"""
        created = []
        for name in self.configs:
            client = self.create_client(name)
            if client:
                created.append(client)
        return created

    async def activate_client(self, name: str) -> List[MCPTool]:
        """激活指定客户端：自动创建（如未创建）→ 启动进程 → 握手 → 获取工具"""
        if name not in self.clients:
            self.create_client(name)
        client = self.clients.get(name)
        if not client:
            return []
        if client.state == 'active':
            return self.client_tools.get(name, [])
        return await self._activate(client)

    async def activate_all(self) -> List[MCPTool]:
        """激活所有未激活的客户端"""
        self.create_all_clients()
        all_tools: List[MCPTool] = []
        for name, client in self.clients.items():
            if client.state == 'inactive':
                tools = await self._activate(client)
                all_tools.extend(tools)
        return all_tools

    async def _activate(self, client: MCPClient) -> List[MCPTool]:
        await client.start()
        await client.initialize()
        tools_data = await client.list_tools()
        if tools_data:
            tools = [MCPTool(client, t) for t in tools_data]
            self.client_tools[client.name] = tools
            print(f"Activated mcp client: {client.name} ({len(tools)} tool(s))")
            return tools
        print(f"Activated mcp client: {client.name} (0 tools)")
        return []

    async def deactivate_client(self, name: str) -> List[MCPTool]:
        """停止单个客户端：关闭进程，清理 client 和 tools（配置保留）"""
        tools: List[MCPTool] = []
        client = self.clients.pop(name, None)
        if client:
            await client.close()
            tools = self.client_tools.pop(name, [])
            print(f"Deactivated mcp client: {name}")
        return tools

    async def deactivate_all(self) -> List[MCPTool]:
        """停止所有客户端"""
        all_tools: List[MCPTool] = []
        for name in list(self.clients.keys()):
            tools = await self.deactivate_client(name)
            all_tools.extend(tools)
        return all_tools

