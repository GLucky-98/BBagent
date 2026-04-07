from cgitb import reset
import re
from model import Model
from tool import Tool
from message import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from typing import List

class ModelToolLoop:
    def __init__(self,model:Model, tool:List[Tool]) -> None:
        self.model=model
        self.tool={}
        tool_prompt={}
        for t in tool:
            self.tool[t.name] = t
            tool_prompt[t.name]={'description':t.description,'input_schema':t.inputschema}

        self.tool_prompt=HumanMessage(content=f'You have tools:{tool_prompt}, 如果你要进行工具调用，那么你的finish_reason应该是tool_calls')
        
    
    def run(self,messages:List[AnyMessage]) -> List[AnyMessage]:       
        while True:
            response=self.model.invoke(messages)
            messages.append(response)
            
            if response.finish_reason != 'tool_calls':
                return
            
            for tool_call in response.tool_calls:
                id = tool_call['id']
                name = tool_call['function']['name']
                input = tool_call['function']['arguments']
                result=self.tool_execute(id, name, input)
                messages.append(result)
            
            return
            

    def tool_execute(self, id:str, name:str, input:dict) -> ToolMessage:
        tool=self.tool.get(name)
        content={}
        content['tool_use_id']=id
        
        if tool:
            try:
                result = tool.invoke(input)
                content['tool_result']=result              
            except Exception as e:
                content['tool_result'] = f'Tool invocation error {e}'
        else:
            content['tool_result'] = f'Unkonw tool:{name}'
            
        return ToolMessage(content=content)
        

    






