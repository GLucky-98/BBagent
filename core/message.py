from typing import List

class AnyMessage():
    # this class is used to represent any message
    def __init__(self, role: str, content):
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
        if hasattr(self, 'tool_calls') and self.tool_calls:
            parts.append(f"tool_calls: {self.tool_calls}")
        if hasattr(self, 'finish_reason') and self.finish_reason:
            parts.append(f"finish_reason: {self.finish_reason}")
        if hasattr(self, 'usage_data') and self.usage_data and self.usage_data.get('total_tokens')!=0:
            parts.append(f"usage: {self.usage_data}")
        return "\n".join(parts)



class HumanMessage(AnyMessage):
    def __init__(self, content: str):
        super().__init__("user", content)


class AIMessage(AnyMessage):
    
    """The message replied by the model"""
    
    def __init__(self,
                content: str,
                reasoning_content: str,
                id:str,
                finish_reason:str,
                tool_calls:List[dict],
                usage_data:dict
                ):
        super().__init__("assistant", content)
        self.reasoning_content=reasoning_content
        self.id=id
        self.finish_reason=finish_reason
        self.tool_calls=tool_calls
        self.usage_data=usage_data


class SystemMessage(AnyMessage):
    def __init__(self, content: str):
        super().__init__("system", content)

class ToolMessage(AnyMessage):
    def __init__(self, id:str, content):
        super().__init__("tool", content)