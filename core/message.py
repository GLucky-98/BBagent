from os import name
from typing import List

class Message():
    # this class is used to represent any message
    def __init__(self, role: str, content: str|dict ):
        self.role = role
        self.content = content

    def __str__(self) -> str:
        parts = [f"role: {self.role}"]
        if hasattr(self, 'id') and self.id:
            parts.append(f"id: {self.id}")
        if self.content:
            parts.append(f"content: {self.content}")
        if hasattr(self, 'reasoning_content') and self.reasoning_content:
            parts.append(f"reasoning: {self.reasoning_content}")
        if hasattr(self, 'text') and self.text:
            parts.append(f"text: {self.text}")
        if hasattr(self, 'tool_calls') and self.tool_calls:
            parts.append(f"tool_calls: {self.tool_calls}")
        if hasattr(self, 'finish_reason') and self.finish_reason:
            parts.append(f"finish_reason: {self.finish_reason}")
        if hasattr(self, 'usage_data') and self.usage_data and self.usage_data.get('total_tokens')!=0:
            parts.append(f"usage: {self.usage_data}")
        return "\n".join(parts)

class HumanMessage(Message):
    def __init__(self, content):
        super().__init__("user", content)

class SystemMessage(Message):
    def __init__(self, content):
        super().__init__("system", content)

class ToolMessage(Message):
    def __init__(self, content, name: str, id: str):
        super().__init__("tool", content)
        self.name = name
        self.id = id

class AIMessage(Message):
    
    """The message replied by the model"""
    
    def __init__(self,
                content: str|dict,
                text: str,
                thinking: str,
                id:str,
                stop_reason:str,
                tool_calls:List[dict],
                usage_data:dict
                ):
        super().__init__("assistant", content)
        self.content = content  # The raw output of the model !!!
        
        self.id = id
        self.text = text           # the model output text
        self.thinking = thinking   # the model thinking text
        
        self.stop_reason = stop_reason
        self.tool_calls = tool_calls # [{'id':,'name':,'input':}]
        self.usage_data = usage_data




