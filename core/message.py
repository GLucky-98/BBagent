import json
from typing import List
from dataclasses import dataclass, asdict, fields
from datetime import datetime

from .tool import Tool

__all__ = [
    'Session',
    'Message', 
    'HumanMessage', 
    'SystemMessage', 
    'AssistantMessage', 
    'ToolResultMessage',
    'ContentBlock',
    'TextBlock',
    'ImageBlock',
    'ToolUseBlock',
    'ThinkingBlock'
]


class ContentBlock:
    """
    内容块基类 - 提供统一的序列化/反序列化方法
    
    所有子类直接复用基类的 to_dict() 方法，无需覆盖
    """
    
    def to_dict(self) -> dict:
        """
        通用序列化方法 - 使用 dataclasses.asdict()
        所有子类复用此方法，无需覆盖
        """
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'ContentBlock':
        """工厂方法 - 根据 type 字段创建对应的子类实例"""
        block_type = data.get('type', 'text')
        type_mapping = {
            'text': TextBlock,
            'image': ImageBlock,
            'thinking': ThinkingBlock,
            'tooluse': ToolUseBlock,
        }
        block_class = type_mapping.get(block_type, TextBlock)
        return block_class(**data)


@dataclass
class TextBlock(ContentBlock):
    text: str
    type: str = "text"


@dataclass
class ImageBlock(ContentBlock):
    data: str
    image_type: str 
    type: str = "image" 


@dataclass
class ThinkingBlock(ContentBlock):
    thinking: str
    signature: str
    type: str = "thinking"


@dataclass
class ToolUseBlock(ContentBlock):
    id: str
    name: str
    input: dict
    type: str = "tooluse"



class Message:
    """消息基类 - 提供统一的序列化/反序列化方法"""
    
    def to_dict(self) -> dict:
        """
        通用序列化方法 - 所有子类复用此方法
        
        规则：
        1. ContentBlock 及其子类：递归调用 to_dict()
        2. list 中元素是 ContentBlock 子类：递归调用 to_dict()
        3. 其他：直接返回
        """
        if not hasattr(self, '__dataclass_fields__'):
            return {}
        
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            result[f.name] = self._serialize_value(value)
        return result
    
    def _serialize_value(self, value):
        """递归序列化值"""
        if isinstance(value, ContentBlock):
            return value.to_dict()
        elif isinstance(value, list) and len(value) > 0:
            return [self._serialize_item(item) for item in value]
        else:
            return value
    
    def _serialize_item(self, item):
        """序列化列表中的单个元素"""
        if isinstance(item, ContentBlock):
            return item.to_dict()
        return item
    
    @staticmethod
    def from_dict(data: dict) -> 'Message':
        """工厂方法 - 根据 role 字段创建对应的子类实例"""
        msg_type = data.get('role', 'user')
        content = data.get('content')
        
        if isinstance(content, list):
            content = [ContentBlock.from_dict(c) if isinstance(c, dict) else c for c in content]
        elif isinstance(content, dict):
            content = ContentBlock.from_dict(content)
        
        if msg_type == 'user':
            return HumanMessage(content=content)
        elif msg_type == 'system':
            return SystemMessage(content=content)
        elif msg_type == 'assistant':
            tool_calls = data.get('tool_calls', [])
            if isinstance(tool_calls, list):
                tool_calls = [ToolUseBlock(**tc) if isinstance(tc, dict) else tc for tc in tool_calls]
            return AssistantMessage(
                content=content,
                id=data.get('id', ''),
                stop_reason=data.get('stop_reason', ''),
                tool_calls=tool_calls,
                usage_data=data.get('usage_data', {})
            )
        elif msg_type == 'tool':
            return ToolResultMessage(
                id=data.get('id', ''),
                name=data.get('name', ''),
                content=content
            )
        else:
            return HumanMessage(content=content)


@dataclass
class HumanMessage(Message):
    content: List[ContentBlock] | str 
    role: str = "user"


@dataclass
class SystemMessage(Message):
    content: str 
    role: str = "system"


@dataclass
class ToolResultMessage(Message):
    id: str
    name: str
    content: List[ContentBlock] | str 
    role: str = "tool"


@dataclass
class AssistantMessage(Message):
    id: str
    content: List[ContentBlock] | str
    stop_reason: str
    tool_calls: List[ToolUseBlock]
    usage_data: dict
    role: str = "assistant"


class Session:
    def __init__(self, id: str = None, system_prompt: str = None, tools: List[Tool] = None, context: List[Message] = None):
        self.id = id if id else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.tools = tools if tools else []
        self.context = context if context else []
        self.system_prompt = ''
        if system_prompt:
            self.add_system_prompt(system_prompt)          
        self.usage_data = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
    
    def add_system_prompt(self, system_prompt: str):
        if self.system_prompt:
            self.system_prompt += system_prompt
            self.context[0].content = self.system_prompt
        else:
            self.system_prompt = system_prompt
            self.context.insert(0, SystemMessage(content=system_prompt))

    def add_tools(self, tools: List[Tool]):
        existing_names = {t.name for t in self.tools}
        new_tools = [t for t in tools if t.name not in existing_names]
        self.tools.extend(new_tools)
    
    def del_tools(self, tools: List[Tool]):
        self.tools = [t for t in self.tools if t.name not in [t.name for t in tools]]

    def add_message(self, message: List[Message] | Message):
        if isinstance(message, List):
            self.context.extend(message)
        else:
            self.context.append(message)
        if isinstance(self.context[-1], AssistantMessage):
            self.usage_data.update(self.context[-1].usage_data)
            self.usage_data['total_tokens'] = self.usage_data['input_tokens'] + self.usage_data['output_tokens']

    def to_dict(self) -> dict:
        """将 Session 序列化为字典"""
        return {
            'id': self.id,
            'system_prompt': self.system_prompt,
            'tools': [t.schema for t in self.tools],
            'context': [msg.to_dict() for msg in self.context],
            'usage_data': self.usage_data
        }
    
    def to_json(self, indent: int = 4) -> str:
        """将 Session 序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    def save(self, filepath: str = None) -> str:
        """将 Session 保存到 JSON 文件"""
        if filepath is None:
            filepath = f"{self.id}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        
        return filepath
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """从字典反序列化为 Session"""
        session = cls(
            id=data.get('id'),
            system_prompt=data.get('system_prompt', '')
        )
        
        session.tools = []
        session.context = []
        
        for msg_data in data.get('context', []):
            msg = Message.from_dict(msg_data)
            session.context.append(msg)
        
        session.usage_data = data.get('usage_data', {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        })
        
        return session
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Session':
        """从 JSON 字符串反序列化为 Session"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def load(cls, filepath: str) -> 'Session':
        """从 JSON 文件加载 Session"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
