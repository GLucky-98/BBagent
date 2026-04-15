import asyncio
import os
import json
import termios
import sys

from pathlib import Path
from typing import  List

from .model import Model
from .tool import Tool
from .message import Message,ToolMessage,SystemMessage,HumanMessage
from .mcp import MCPClient,MCPManager
from .skill import SkillManager

class ToolManager():
    def __init__(self, model:Model, tools:List[Tool] = []):
        self.tools = {}
        self.model = model
        if tools:
            self.add_tools(tools)
    
    def add_tools(self, tools:List[Tool]):
        self.model.add_tools(tools)
        for t in tools:
            self.tools[t.name] = t
        print(f"Added tools: {[tool.name for tool in tools]}")
    
    def del_tools(self, tools:List[Tool]):
        self.model.del_tools(tools)
        for t in tools:
            if t.name in self.tools:
                del self.tools[t.name]
        print(f"Deleted tools: {[tool.name for tool in tools]}")
    
    def tool_execute(self, tool_call:dict) -> ToolMessage:
        id = tool_call['id']
        name = tool_call['name']
        input = tool_call['input']
        tool=self.tools.get(name)

        if tool:
            try:
                result = tool.invoke(input)
                content = json.dumps(result, ensure_ascii=False)              
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unkonw tool:{name}'
            
        return ToolMessage(name=name, id=id, content=content)
    
    async def async_tool_execute(self, tool_call:dict) -> ToolMessage:
        id = tool_call['id']
        name = tool_call['name']
        input = tool_call['input']
        tool=self.tools.get(name)

        if tool:
            try:
                if tool.is_async:
                    result = await tool.async_invoke(input)
                else:
                    result = tool.invoke(input)
                content = json.dumps(result, ensure_ascii=False)              
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unkonw tool:{name}'
            
        return ToolMessage(name=name, id=id, content=content)


class Agent:
    def __init__(self, model:Model, base_dir:Path | str = None, system_prompt:str = "", tools:List[Tool] = [], mcp_clients:List[MCPClient] = None, skill_dir:Path | str = None) -> None:
        self.model = model
        self.base_dir = base_dir if base_dir else os.getcwd()
        self.prompt = SystemMessage(system_prompt) if system_prompt else None
        self.tool_manger = ToolManager(model, tools)
        self.mcp_manager = MCPManager(mcp_clients)
        self.skill_manager = SkillManager(self.base_dir, skill_dir)
            
    def add_mcp_clients(self, mcp_clients:List[MCPClient]):
        self.mcp_manager.add_mcp_clients(mcp_clients)
    
    async def activate_mcp_clients(self, mcp_clients:List[MCPClient], is_all:bool = False):
        tools = await self.mcp_manager.activate_mcp_clients(mcp_clients, is_all)
        self.tool_manger.add_tools(tools)
        
    async def del_mcp_client(self, clients_name:List[str]):
        tools = await self.mcp_manager.del_mcp_clients(clients_name)
        self.tool_manger.del_tools(tools)      
    
    def add_skills(self, skill_dir:Path | str):
        self.skill_manager.add_skills(skill_dir)
    
    def show_skills(self):
        return self.skill_manager.show_skills()
        
    async def tool_loop(self, messages:List[Message]):
        while True:
            response = await self.model.async_invoke(messages)
            messages.append(response)
            
            if response.stop_reason not in ['tool_use', 'tool_calls']:
                return
            
            for tool_call in response.tool_calls:
                result = await self.tool_manger.async_tool_execute(tool_call)
                messages.append(result)       

    async def run(self) -> List[Message]:
        messages = [self.prompt] if self.prompt else []
        # 激活所有 MCP 客户端
        if len(self.mcp_manager.clients) > 0:
            tools = await self.mcp_manager.activate_mcp_clients(is_all=True)
            if tools:
                self.tool_manger.add_tools(tools)       
        # 显示所有技能
        if len(self.skill_manager.skills) > 0:
            load_skill_tool=Tool(self.skill_manager.show_skill_detail)
            self.tool_manger.add_tools([load_skill_tool])
            messages.append(SystemMessage(content=self.skill_manager.show_skills()))
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        while True:
            try:                
                query = input("\033[36ms02 >> \033[0m")              
            except (EOFError, KeyboardInterrupt):
                break
                print(messages)
            if query.strip().lower() in ("q", "exit", ""):
                break

            messages.append(HumanMessage(content=query))
            await self.tool_loop(messages)
            response_content = messages[-1]
            print(response_content.text)
             
        






