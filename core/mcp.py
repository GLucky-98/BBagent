import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
import inspect

from .tool import Tool

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
    def __init__(self, name:str, command: List[str], env: Dict[str, str] = {}):
        self.name = name
        self.command = command
        self.env = {**os.environ, **env}
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.state = 'inactive'

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
                "name": "minimax-mcp-client",
                "version": "0.1.0"
            }
        })
        print(f"Server initialized: {server_info}")

        # 2. 发送 initialized 通知（握手完成）
        await self.send_notification("notifications/initialized")
        self.state = 'active'
        return server_info

    async def list_tools(self) -> List[Dict]:
        """获取服务器提供的工具列表"""
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
            await self.process.wait()
            self.state = 'inactive'
            self.process = None
class MCPTool(Tool):
    def __init__(self, mcp_client: MCPClient, config: Dict[str, Any]) :
        func = self.create_tool_from_config(mcp_client, config)
        super().__init__(func)
        
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
    def __init__(self, mcp_clients:List[MCPClient] = None):
        self.clients = {}
        self.client_tools = {}
        if mcp_clients:
            self.add_mcp_clients(mcp_clients)
        
    def add_mcp_clients(self, mcp_clients:List[MCPClient] = None):
        """添加 MCP 客户端"""
        for client in mcp_clients:
            if client.name not in self.clients:
                self.clients[client.name] = client
        print(f"Added mcp clients: {[client.name for client in mcp_clients]}")
    
    async def activate_mcp_clients(self, mcp_clients:List[MCPClient] = None, is_all:bool = False) -> List[MCPTool]:
        """激活 MCP 客户端"""
        async def activate_client(client:MCPClient) -> List[MCPTool]:
            await client.start()
            await client.initialize()
            tools = await client.list_tools()
            if tools:
                tools = [MCPTool(client, tool) for tool in tools]
                self.client_tools[client.name] = tools
                return tools
            return []
        
        if mcp_clients:
            self.add_mcp_clients(mcp_clients)      
        
        all_tools = []

        if is_all:
            for _,client in self.clients.items():
                if client.state == 'inactive':
                    tools = await activate_client(client)
                    all_tools.extend(tools)
                    print(f"Activated mcp client: {client.name}")
        
        else:
            for client in mcp_clients:
                tools = await activate_client(client)
                all_tools.extend(tools)
                print(f"Activated mcp client: {client.name}")

        return all_tools        

    async def del_mcp_clients(self, clients_name:List[str]) -> List[MCPTool]:
        """删除指定 MCP 客户端"""
        all_del_tools = []
        for client_name in clients_name:
            if client_name in self.clients:
                client = self.clients.pop(client_name)
                await client.close()
                tools = self.client_tools.pop(client_name, None)
                if tools:
                    all_del_tools.extend(tools)
                    
        print(f"Deleted mcp clients: {clients_name}")
        return all_del_tools

