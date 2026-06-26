"""
Bash tool - Execute shell commands.
"""
import asyncio
import os

from ..core.tool import Tool
from .policy import Policy

DEFAULT_TIMEOUT = 60
DEFAULT_MAX_OUTPUT_SIZE = 50_000


async def _exec_bash_command(
    command: str,
    cwd: str,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
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
        max_output_size = policy.bash_max_output_size
        default_timeout = policy.bash_default_timeout
    else:
        cwd = "."
        max_output_size = DEFAULT_MAX_OUTPUT_SIZE
        default_timeout = DEFAULT_TIMEOUT

    async def bash_func(command: str, timeout: int | None = None) -> str:
        if not command or not command.strip():
            return "Error: command is required"
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

            if len(stdout) > max_output_size:
                stdout = stdout[:max_output_size]
                truncated = True

            if len(stderr) > max_output_size:
                stderr = stderr[:max_output_size]
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
            return f"Error executing command: {e!s}"

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
        name="bash",
        description="Execute a bash command. Returns the stdout and stderr output.",
        input_schema=input_schema,
        source="built_in",
    )
