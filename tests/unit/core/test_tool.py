import pytest
from pydantic import BaseModel

from bbagent.core.tool import Tool


class SearchInput(BaseModel):
    query: str
    limit: int = 5


def test_tool_schema_marks_only_required_parameters():
    def sample(path: str, limit: int = 10, recursive: bool = False) -> str:
        return path

    tool = Tool(sample)

    assert tool.input_schema["type"] == "object"
    assert tool.input_schema["required"] == ["path"]
    assert tool.input_schema["properties"]["path"]["type"] == "string"
    assert tool.input_schema["properties"]["limit"]["type"] == "integer"
    assert tool.input_schema["properties"]["recursive"]["type"] == "boolean"


def test_tool_invoke_validates_and_coerces_arguments():
    def add(left: int, right: int = 1) -> int:
        return left + right

    tool = Tool(add)

    assert tool.invoke({"left": "2", "right": "3"}) == 5
    assert tool.invoke({"left": 2}) == 3


def test_tool_invoke_validates_pydantic_model_parameter():
    def search(input: SearchInput) -> str:
        return f"{input.query}:{input.limit}"

    tool = Tool(search)

    assert tool.invoke({"input": {"query": "agent", "limit": "7"}}) == "agent:7"


def test_tool_invoke_rejects_missing_required_argument():
    def echo(text: str) -> str:
        return text

    with pytest.raises(ValueError, match="Missing required parameter"):
        Tool(echo).invoke({})


@pytest.mark.asyncio
async def test_async_tool_requires_async_invoke():
    async def echo(text: str) -> str:
        return text

    tool = Tool(echo)

    with pytest.raises(RuntimeError, match="async function"):
        tool.invoke({"text": "hello"})
    assert await tool.async_invoke({"text": "hello"}) == "hello"
