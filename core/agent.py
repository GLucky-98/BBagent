import asyncio
import os
import json
import termios
import sys

from pathlib import Path
from typing import  List

from .model import Model
from .tool import Tool
from .message import *
from .mcp import MCPClient,MCPManager
from .skill import SkillManager

class ToolManager():
    def __init__(self, session:Session, tools:List[Tool] = []):
        self.tools = {}
        self.session = session
        if tools:
            self.add_tools(tools)
    
    def add_tools(self, tools:List[Tool]):
        self.session.add_tools(tools)
        for t in tools:
            self.tools[t.name] = t
        print(f"Added tools: {[tool.name for tool in tools]}")
    
    def del_tools(self, tools:List[Tool]):
        self.session.del_tools(tools)
        for t in tools:
            if t.name in self.tools:
                del self.tools[t.name]
        print(f"Deleted tools: {[tool.name for tool in tools]}")
    
    def tool_execute(self, tool_call:ToolUseBlock) -> ToolResultMessage:
        id = tool_call.id
        name = tool_call.name
        input = tool_call.input
        tool=self.tools.get(name)

        if tool:
            try:
                result = tool.invoke(input)
                if isinstance(result, str):
                    content = result
                else:
                    content = json.dumps(result, ensure_ascii=False)              
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unknown tool:{name}'
            
        return ToolResultMessage(id, name, content)
    
    async def async_tool_execute(self, tool_call:ToolUseBlock) -> ToolResultMessage:
        id = tool_call.id
        name = tool_call.name
        input = tool_call.input
        tool = self.tools.get(name)

        if tool:
            try:
                if tool.is_async:
                    result = await tool.async_invoke(input)
                else:
                    result = tool.invoke(input)
                if isinstance(result, str):
                    content = result
                else:
                    content = json.dumps(result, ensure_ascii=False)                 
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unknown tool:{name}'
            
        return ToolResultMessage(id, name, content)


class Agent:
    def __init__(self, 
                 model:Model, 
                 base_dir:Path | str = None, 
                 system_prompt:str = None, 
                 session:Session = None, 
                 tools:List[Tool] = None, 
                 mcp_clients:List[MCPClient] = None, 
                 skill_dir:Path | str = None):
        
        self.model = model
        self.base_dir = base_dir if base_dir else os.getcwd()
        self.session = session if session else Session(system_prompt=system_prompt)        
        self.tool_manager = ToolManager(self.session, tools)
        self.mcp_manager = MCPManager(mcp_clients)
        self.skill_manager = SkillManager(self.base_dir, skill_dir)
            
    def add_mcp_clients(self, mcp_clients:List[MCPClient]):
        self.mcp_manager.add_mcp_clients(mcp_clients)
    
    async def activate_mcp_clients(self, mcp_clients:List[MCPClient], is_all:bool = False):
        tools = await self.mcp_manager.activate_mcp_clients(mcp_clients, is_all)
        self.tool_manager.add_tools(tools)
        
    async def del_mcp_client(self, clients_name:List[str]):
        tools = await self.mcp_manager.del_mcp_clients(clients_name)
        self.tool_manager.del_tools(tools)      
    
    def add_skills(self, skill_dir:Path | str):
        self.skill_manager.add_skills(skill_dir)
    
    def show_skills(self):
        return self.skill_manager.show_skills()
        
    
    async def stream_tool_loop(self):
        """改进版：工具调用不阻塞流式输出"""
        while True:
            tool_tasks = []  # 存储待执行的工具任务
            tool_call_map = {}  # 映射 task -> tool_call 用于调试
            
            # 使用异步流式调用
            async for chunk in self.model.async_stream_invoke(self.session):
                chunk_type = chunk.get('type')
                content = chunk.get('content', '')

                if chunk_type == 'need_print':
                    # 实时打印，同时可以显示工具执行状态
                    print(content, end='', flush=True)

                elif chunk_type == 'completed_tool_use':
                    tool_call = content
                    # 创建后台任务，不等待立即执行
                    task = asyncio.create_task(
                        self.tool_manager.async_tool_execute(tool_call)
                    )
                    tool_tasks.append(task)
                    tool_call_map[task] = tool_call
                    print(f"[执行工具: {tool_call.name}]")
                    # 可以在这里打印提示：

                elif chunk_type == 'completed_message':
                    stop_reason = content.stop_reason
                    self.session.add_message(content)
                    break
            
            if stop_reason in ['tool_use']:
                # 等待所有工具任务完成
                tool_results = await asyncio.gather(*tool_tasks)
                self.session.add_message(tool_results)
            elif stop_reason in ['end_turn']:
                print('\n', flush=True)
                break
            else:
                raise ValueError(f"Stop reason: {stop_reason}")
                 
    async def run(self):
        # 激活所有 MCP 客户端
        if len(self.mcp_manager.clients) > 0:
            tools = await self.mcp_manager.activate_mcp_clients(is_all=True)
            if tools:
                self.tool_manager.add_tools(tools)       
        # 显示所有技能
        if len(self.skill_manager.skills) > 0:
            load_skill_tool=Tool(self.skill_manager.show_skill_detail)
            self.tool_manager.add_tools([load_skill_tool])
            self.session.add_system_prompt(self.skill_manager.show_skills())
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        while True:
            try:                
                query = input("\033[36ms02 >> \033[0m")              
            except (EOFError, KeyboardInterrupt):
                break
            if query.strip().lower() in ("q", "exit", ""):
                self.session.save()
                break

            self.session.add_message(HumanMessage(content=query))
            await self.stream_tool_loop()

 
             
        






