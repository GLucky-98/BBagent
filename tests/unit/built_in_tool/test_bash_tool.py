"""Baseline tests for built_in_tool bash — command execution and policy binding."""

import pytest

from bbagent.built_in_tool.bash import create_bash_tool
from bbagent.built_in_tool.policy import Policy


@pytest.mark.asyncio
async def test_bash_echo_prints_output(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path)))

    result = await tool.async_invoke({"command": "echo hello world"})

    assert "hello world" in result
    assert "[stdout]" in result


@pytest.mark.asyncio
async def test_bash_stderr_is_captured(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path)))

    result = await tool.async_invoke({"command": "echo STDERR 1>&2"})

    assert "[stderr]" in result
    assert "STDERR" in result


@pytest.mark.asyncio
async def test_bash_exit_code_is_reported(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path)))

    result = await tool.async_invoke({"command": "exit 42"})

    assert "[exit code: 42]" in result


@pytest.mark.asyncio
async def test_bash_uses_policy_cwd(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "marker.txt").write_text("found", encoding="utf-8")

    tool = await create_bash_tool(Policy(cwd=str(tmp_path / "sub")))

    result = await tool.async_invoke({"command": "cat marker.txt"})

    assert "found" in result


@pytest.mark.asyncio
async def test_bash_empty_command_returns_error(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path)))

    result = await tool.async_invoke({"command": ""})

    assert result == "Error: command is required"


@pytest.mark.asyncio
async def test_bash_nonexistent_cwd_reports_error(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path / "nonexistent")))

    result = await tool.async_invoke({"command": "echo test"})

    assert "Error: Working directory does not exist" in result


@pytest.mark.asyncio
async def test_bash_timeout_may_shorten_command(tmp_path):
    tool = await create_bash_tool(Policy(cwd=str(tmp_path)))

    result = await tool.async_invoke({"command": "sleep 10", "timeout": 1})

    assert "Command timed out" in result


@pytest.mark.asyncio
async def test_bash_input_schema_requires_command():
    tool = await create_bash_tool(Policy())

    schema = tool.input_schema

    assert schema["type"] == "object"
    assert "command" in schema["required"]
    assert schema["properties"]["command"]["type"] == "string"
