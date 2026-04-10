from typing import List
import json

from .model import Model
from .tool import Tool
from .message import Message,ToolMessage

class ModelToolLoop:
    def __init__(self,model:Model, tools:List[Tool]) -> None:
        self.model=model
        self.model.bind_tools(tools)

        self.tools={}
        for t in tools:
            self.tools[t.name] = t
         
    def run(self,messages:List[Message]) -> List[Message]:       
        while True:
            response=self.model.invoke(messages)
            messages.append(response)
            
            if response.stop_reason not in ['tool_use', 'tool_calls']:
                return
            
            for tool_call in response.tool_calls:
                id = tool_call['id']
                name = tool_call['name']
                input = tool_call['input']
                result=self.tool_execute(id, name, input)
                messages.append(result)                  

    def tool_execute(self, id:str, name:str, input:str) -> ToolMessage:
        tool=self.tools.get(name)

        if tool:
            try:
                result = tool.invoke(input)
                content=result              
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unkonw tool:{name}'
            
        return ToolMessage(name=name,id=id,content=content)
        

    






