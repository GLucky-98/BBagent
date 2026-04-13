import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

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
            self.process = None