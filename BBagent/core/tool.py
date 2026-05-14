import inspect
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, get_type_hints, Union
from pydantic import BaseModel, TypeAdapter
from typing import Callable, Dict, List
import copy

from .errors import ERROR_INFERENCE_RULES


@dataclass
class ToolResult:
    content: Union[List['ContentBlock'], str] # type: ignore
    success: bool = True
    error_type: str = ""
    suggestion: str = ""


def format_for_model(tool_result: ToolResult) -> str:
    if tool_result.success:
        return tool_result.content

    parts = [
        "Tool execution failed.",
        f"Error type: {tool_result.error_type or 'unknown'}",
        f"Message: {tool_result.content}",
        f"Suggestion: {tool_result.suggestion or 'Check the error message and try again.'}",
    ]
    return "\n".join(parts)


def infer_tool_error(error_str: str) -> ToolResult:
    for rule in ERROR_INFERENCE_RULES:
        if re.search(rule.pattern, error_str):
            return ToolResult(
                content=error_str,
                success=False,
                error_type=rule.error_type,
                suggestion=rule.suggestion,
            )
    return ToolResult(
        content=error_str,
        success=False,
        error_type="unknown",
        suggestion="Check the error details and try again with corrected parameters.",
    )

# ------------------------------------------------------------
# pydantic 输入参数类型解析辅助函数
# ------------------------------------------------------------
def inline_refs(schema: dict) -> dict:
    """
    将 JSON Schema 中的 $defs 内联到所有 $ref 位置，并删除 $defs 键。
    """
    schema = copy.deepcopy(schema)          # 避免修改原数据
    defs = schema.pop("$defs", {})           # 取出 $defs 并删除

    def _resolve_ref(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                # 只处理 #/$defs/xxx 形式的引用
                if ref_path.startswith("#/$defs/"):
                    ref_name = ref_path.split("/")[-1]
                    if ref_name in defs:
                        # 递归展开定义（定义内部可能还有 $ref）
                        resolved = _resolve_ref(defs[ref_name])
                        # 替换当前对象为展开后的定义
                        obj.clear()
                        obj.update(resolved)
                # 其他外部引用保留原样（可根据需求处理）
            else:
                for key, value in obj.items():
                    obj[key] = _resolve_ref(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = _resolve_ref(item)
        return obj

    return _resolve_ref(schema)


# ------------------------------------------------------------
# Tool类
# ------------------------------------------------------------
class Tool():
    """
        tool:
            name
            description
            inputschema
            function
            invoke (同步调用)
            async_invoke (异步调用)
    """
    def __init__(self, func:Callable, name:str = None, description:str = None, input_schema:dict = None, has_state:bool | None = None) :
        self.name = name if name else func.__name__ 
        self.description = description if description else func.__doc__
        if input_schema:
            self.input_schema = input_schema
        else:
            self.input_schema = self.generate_input_schema_from_func(func)

        self.schema = {
                "name": self.name,
                "description": self.description,
                "input_schema": self.input_schema
            }
        
        self.func = func
        self.is_async = inspect.iscoroutinefunction(func)
        self.has_state = has_state if has_state is not None else (not inspect.isfunction(func))

    def invoke(self,input_dict:dict):
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)  
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name not in input_dict:
                if param.default != inspect.Parameter.empty:
                    continue   
                raise ValueError(f"Missing required parameter: '{param_name}'")

            value = input_dict[param_name]
            param_type = type_hints.get(param_name, Any)

            if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                kwargs[param_name] = param_type.model_validate(value)
            else:
                adapter = TypeAdapter(param_type)
                kwargs[param_name] = adapter.validate_python(value)

        if self.is_async:
            raise RuntimeError(
                f"Tool '{self.name}' is an async function. "
                f"Please use 'async_invoke' method instead of 'invoke'."
            )
        return self.func(**kwargs)
    
    async def async_invoke(self, input_dict: dict):
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)  
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name not in input_dict:
                if param.default != inspect.Parameter.empty:
                    continue   
                raise ValueError(f"Missing required parameter: '{param_name}'")

            value = input_dict[param_name]
            param_type = type_hints.get(param_name, Any)

            if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                kwargs[param_name] = param_type.model_validate(value)
            else:
                adapter = TypeAdapter(param_type)
                kwargs[param_name] = adapter.validate_python(value)

        return await self.func(**kwargs)

    @staticmethod
    def generate_input_schema_from_func(func: Any) -> dict:
        """
        Generate a JSON Schema based on the function's signature and type annotations
        """
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        param_type_hints = {}
        for param_name, _ in sig.parameters.items():
            if param_name in ['self','cls']:
                continue
            param_type = type_hints.get(param_name, Any)
            param_type_hints[param_name] = param_type
        
        properties = {}
        required = []
        for param_name, param_type in param_type_hints.items():
            param_adapter = TypeAdapter(param_type)
            param_schema = inline_refs(param_adapter.json_schema())
            properties[param_name] = param_schema
            if param_name in sig.parameters and sig.parameters[param_name].default == inspect.Parameter.empty:
                required.append(param_name)

        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        return input_schema
      
        
# ------------------------------------------------------------
# Tool装饰器
# ------------------------------------------------------------
def tool(func:Callable):
    
    return Tool(func)


# ------------------------------------------------------------
# ToolManager
# ------------------------------------------------------------
class ToolManager:
    _default: 'ToolManager | None' = None

    def __init__(self):
        self._blueprints: Dict[str, Tool] = {}
        self._shared: Dict[str, Tool] = {}
        self._agent_tools: Dict[str, Dict[str, Tool]] = {}
        self._logger = logging.getLogger("tool.manager")

    def _register(self, tools: List[Tool] | Tool):
        if isinstance(tools, Tool):
            tools = [tools]
        for t in tools:
            self._blueprints[t.name] = t

    def _distribute(self, agent_id: str, tool_names: List[str]) -> List[Tool]:
        agent_dict = self._agent_tools.setdefault(agent_id, {})
        result = []
        for name in tool_names:
            bp = self._blueprints.get(name)
            if not bp:
                continue
            if bp.has_state:
                tool = copy.deepcopy(bp)
            else:
                tool = self._shared.setdefault(name, bp)
            agent_dict[name] = tool
            result.append(tool)
        return result

    def _get_agent_tools(self, agent_id: str) -> List[Tool]:
        return list(self._agent_tools.get(agent_id, {}).values())

    def _list_all(self) -> List[Tool]:
        return list(self._blueprints.values())

    def _unregister_agent(self, agent_id: str):
        self._agent_tools.pop(agent_id, None)

    def _clear(self):
        self._blueprints.clear()
        self._shared.clear()
        self._agent_tools.clear()

    @classmethod
    def default(cls) -> 'ToolManager':
        if cls._default is None:
            cls._default = cls()
        return cls._default

    @classmethod
    def register(cls, tools: List[Tool] | Tool):
        cls.default()._register(tools)

    @classmethod
    def distribute(cls, agent_id: str, tool_names: List[str]) -> List[Tool]:
        return cls.default()._distribute(agent_id, tool_names)

    @classmethod
    def get_agent_tools(cls, agent_id: str) -> List[Tool]:
        return cls.default()._get_agent_tools(agent_id)

    @classmethod
    def list_all(cls) -> List[Tool]:
        return cls.default()._list_all()

    @classmethod
    def unregister_agent(cls, agent_id: str):
        cls.default()._unregister_agent(agent_id)

    @classmethod
    def reset(cls):
        cls._default = None
