import asyncio
from typing import List
import json

from .model import Model
from .tool import Tool,MCPTool
from .message import Message,ToolMessage
from .mcp import MCPClient

class ModelToolLoop:
    def __init__(self, model:Model, tools:List[Tool] = [], mcp_client:MCPClient = None) -> None:
        self.model = model
        self.tools = {}
        if tools:
            self.bind_tools(tools)
        if mcp_client:
            self.bind_mcp_client(mcp_client)
    
    @classmethod
    async def create_async(cls, model:Model, tools:List[Tool] = [], mcp_client:MCPClient = None):
        """异步方式创建 ModelToolLoop 实例"""
        instance = cls.__new__(cls)
        instance.model = model
        instance.tools = {}
        
        if tools:
            instance.bind_tools(tools)
        
        if mcp_client:
            await instance.async_bind_mcp_client(mcp_client)
        
        return instance
         
    def bind_tools(self, tools:List[Tool]):
        self.model.bind_tools(tools)
        for t in tools:
            self.tools[t.name] = t
    
    def bind_mcp_client(self, mcp_client:MCPClient):
        async def mcp_bind():
            await mcp_client.start()
            await mcp_client.initialize()
            tools = await mcp_client.list_tools()
            return tools
        tools = asyncio.run(mcp_bind())
        if tools:
            tools = [MCPTool(mcp_client, tool) for tool in tools]
            self.bind_tools(tools)
        return
    
    async def async_bind_mcp_client(self, mcp_client:MCPClient):
        """异步版本的 bind_mcp_client 方法"""
        await mcp_client.start()
        await mcp_client.initialize()
        tools = await mcp_client.list_tools()
        if tools:
            tools = [MCPTool(mcp_client, tool) for tool in tools]
            self.bind_tools(tools)
        return

    def run(self,messages:List[Message]) -> List[Message]:       
        while True:
            response=self.model.invoke(messages)
            messages.append(response)
            
            if response.stop_reason not in ['tool_use', 'tool_calls']:
                return
            
            for tool_call in response.tool_calls:
                result = self.tool_execute(tool_call)
                messages.append(result)

    async def async_run(self,messages:List[Message]) -> List[Message]:       
        while True:
            response = await self.model.async_invoke(messages)
            messages.append(response)
            
            if response.stop_reason not in ['tool_use', 'tool_calls']:
                return
            
            for tool_call in response.tool_calls:
                result = await self.async_tool_execute(tool_call)
                messages.append(result)                  

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
        

    






