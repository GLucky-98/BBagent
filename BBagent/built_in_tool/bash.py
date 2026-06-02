"""
Bash tool - Execute shell commands.
"""
import asyncio
import os
import subprocess
from typing import Optional

from ..core.tool import Tool
from .policy import Policy


DEFAULT_TIMEOUT = 60
DEFAULT_MAX_OUTPUT_LINES = 1000


async def _exec_bash_command(
    command: str,
    cwd: str,
    timeout: Optional[int] = None,
    env: Optional[dict[str, str]] = None,
) -> tuple[int, str, str]:
    process_env = dict(os.environ)
    if env:
        process_env.update(env)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=process_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            stdout = stdout.decode("utf-8", errors="replace")
            stderr = stderr.decode("utf-8", errors="replace")
            return proc.returncode, stdout, stderr
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


async def create_bash_tool(
    policy_or_config: Policy | dict | None = None,
) -> Tool:
    if isinstance(policy_or_config, Policy):
        policy = policy_or_config
    elif isinstance(policy_or_config, dict):
        policy = Policy(**policy_or_config.get("policy", {})) if policy_or_config.get("policy") else None
    else:
        policy = None

    if policy is not None:
        cwd = policy.cwd
        max_output_lines = policy.bash_max_output_lines
        default_timeout = policy.bash_default_timeout
    else:
        cwd = "."
        max_output_lines = DEFAULT_MAX_OUTPUT_LINES
        default_timeout = DEFAULT_TIMEOUT

    async def bash_func(command: str, timeout: Optional[int] = None) -> str:
        if not os.path.exists(cwd):
            return f"Error: Working directory does not exist: {cwd}"

        timeout = timeout or default_timeout

        try:
            exit_code, stdout, stderr = await _exec_bash_command(
                command=command,
                cwd=cwd,
                timeout=timeout,
            )

            truncated = False
            stdout_lines = stdout.split("\n")
            stderr_lines = stderr.split("\n")

            if len(stdout_lines) > max_output_lines:
                stdout = "\n".join(stdout_lines[:max_output_lines])
                truncated = True

            if len(stderr_lines) > max_output_lines:
                stderr = "\n".join(stderr_lines[:max_output_lines])
                truncated = True

            output_parts = []
            if stdout:
                output_parts.append(f"[stdout]\n{stdout}")
            if stderr:
                output_parts.append(f"[stderr]\n{stderr}")
            if exit_code != 0:
                output_parts.append(f"\n[exit code: {exit_code}]")

            if truncated:
                output_parts.append("\n[output truncated]")

            output = "\n".join(output_parts)
            return output

        except Exception as e:
            return f"Error executing command: {str(e)}"

    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash command to execute",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (optional)",
            },
        },
        "required": ["command"],
    }

    return Tool(
        bash_func,
        name="Bash",
        description="Execute a bash command. Returns the stdout and stderr output.",
        input_schema=input_schema,
        source="built_in",
    )
