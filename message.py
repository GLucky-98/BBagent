from typing import List


class AnyMessage():
    # this class is used to represent any message
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content



class HumanMessage(AnyMessage):
    def __init__(self, content: str):
        super().__init__("user", content)


class AIMessage(AnyMessage):
    
    """The message replied by the model"""
    
    def __init__(self,
                content: str,
                id:str,
                finish_reason:str,
                tool_calls:List[dict],
                usage_data:dict,
                base_resp:dict
                ):
        super().__init__("assistant", content)
        self.id=id
        self.finish_reason=finish_reason
        self.tool_calls=tool_calls
        self.usage_data=usage_data
        self.base_resp=base_resp



class SystemMessage(AnyMessage):
    def __init__(self, content: str):
        super().__init__("system", content)

class ToolMessage(AnyMessage):
    def __init__(self, content: str):
        super().__init__("tool", content)