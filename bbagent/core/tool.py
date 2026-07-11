import copy
import inspect
from collections.abc import Callable
from typing import Any, Literal, cast, get_type_hints

from pydantic import BaseModel, TypeAdapter

ToolSource = Literal["built_in", "hook", "mcp", "team"]

# ------------------------------------------------------------
# pydantic input parameter type parsing helper function
# ------------------------------------------------------------
def inline_refs(schema: dict) -> dict:
    """
    Inline $defs in JSON Schema into all $ref positions, and remove the $defs key.
    """
    schema = copy.deepcopy(schema)          # avoid modifying original data
    defs = schema.pop("$defs", {})           # extract $defs and remove it

    def _resolve_ref(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                # only handle #/$defs/xxx style references
                if ref_path.startswith("#/$defs/"):
                    ref_name = ref_path.split("/")[-1]
                    if ref_name in defs:
                        # recursively expand definition (may contain nested $ref)
                        resolved = _resolve_ref(defs[ref_name])
                        # replace current object with expanded definition
                        obj.clear()
                        obj.update(resolved)
                # other external references kept as-is (handle as needed)
            else:
                for key, value in obj.items():
                    obj[key] = _resolve_ref(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = _resolve_ref(item)
        return obj

    return cast(dict, _resolve_ref(schema))


# ------------------------------------------------------------
# Tool class
# ------------------------------------------------------------
class Tool:
    """
        tool:
            name
            description
            inputschema
            function
            invoke (sync call)
            async_invoke (async call)
    """
    def __init__(self, func:Callable, name:str | None = None, description:str | None = None, input_schema:dict | None = None,
                 source: ToolSource | None = None):
        self.name = name if name else func.__name__
        self.description = description if description else func.__doc__
        if input_schema:
            self.input_schema = input_schema
        else:
            self.input_schema = self.generate_input_schema_from_func(func)

        self.func = func
        self.is_async = inspect.iscoroutinefunction(func)
        self.source: ToolSource | None = source

    @property
    def schema(self) -> dict:
        """LLM-facing tool schema: {name, description, input_schema}."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

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
# Tool decorator
# ------------------------------------------------------------
def tool(func:Callable):

    return Tool(func)


