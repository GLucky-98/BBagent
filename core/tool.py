# Example:
# import subprocess
# import os

# for ordinary function

# @tool
# def run_bash(command: str) -> str:
#     dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
#     if any(d in command for d in dangerous):
#         return "Error: Dangerous command blocked"
#     try:
#         r = subprocess.run(command, shell=True, cwd=os.getcwd(),
#                            capture_output=True, text=True, timeout=120)
#         out = (r.stdout + r.stderr).strip()
#         return out[:50000] if out else "(no output)"
#     except subprocess.TimeoutExpired:
#         return "Error: Timeout (120s)"

# print(run_bash.invoke({'command':'ls'}))

# for instance method

# class MyService:
#     def greet(self, name: str, age: int = 18) -> str:
#         """Greet someone"""
#         return f"Hello {name}, age {age}"

# service = MyService()
# greet=Tool(service.greet)
# print(greet.invoke({'name':'gl','age': 18}))    

import inspect
from typing import Any, get_type_hints
from pydantic import BaseModel, TypeAdapter
from typing import Callable
import copy

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
    def __init__(self, func:Callable, name:str = None, description:str = None, input_shcema:dict = None) :
        self.name = name if name else func.__name__ 
        self.description = description if description else func.__doc__
        self.input_schema = input_shcema if input_shcema else self.generate_input_schema_from_func(func)

        self.schema = {
                "name": self.name,
                "description": self.description,
                "input_schema": self.input_schema
            }
        
        self.func = func
        self.is_async = inspect.iscoroutinefunction(func)
    
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

        if not self.is_async:
            raise RuntimeError(
                f"Tool '{self.name}' is a sync function. "
                f"Please use 'invoke' method instead of 'async_invoke'."
            )
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
