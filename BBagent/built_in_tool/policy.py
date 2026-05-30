"""
Policy module - Centralized configuration for all built-in tools.
Aggregates every tool's closure parameters (cwd, limits, security rules)
into a single Policy dataclass. Each tool extracts what it needs.
"""
import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


NETWORK_COMMANDS = frozenset({
    "curl", "wget", "nc", "netcat", "telnet", "ssh", "scp", "sftp",
    "ftp", "ping", "nslookup", "dig", "nmap", "traceroute", "tracepath",
    "httpie", "http", "wscat", "amqp", "mqtt", "socat", "aria2c",
    "axel", "rsync", "iperf", "iperf3",
})


@dataclass
class Policy:
    cwd: str = "."

    # ── 文件路径安全限制（作用于 read/write/edit/ls/find/grep）──
    allowed_dirs: Optional[list[Path]] = None
    blocked_paths: Optional[list[str]] = None
    blocked_extensions: Optional[list[str]] = None

    # ── 读写限制 ──
    max_read_size: int = 500_000
    max_read_lines: int = 10_000
    max_write_size: int = 5 * 1024 * 1024
    write_create_directories: bool = True

    # ── Bash 限制 ──
    bash_allowed_commands: Optional[list[str]] = None
    bash_blocked_commands: Optional[list[str]] = None
    bash_allow_network: bool = True
    bash_max_output_lines: int = 1000
    bash_default_timeout: int = 60

    # ── SubAgent 配置 ──
    sub_agent_model: Optional[dict] = None
    sub_agent_blocked_tools: Optional[list[str]] = None

    def __post_init__(self):
        if self.allowed_dirs is None:
            self.allowed_dirs = [Path(self.cwd)]


def resolve_and_check_path(path_str: str, policy: Policy) -> tuple[Optional[str], Optional[str]]:
    """Resolve a user-supplied path and validate it against the policy.

    Returns:
        (resolved_absolute_path, error_message)
        - On success: (absolute_path, None)
        - On failure: (None, error_description)
    """
    if not path_str:
        return None, None

    p = Path(path_str)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (Path(policy.cwd) / p).resolve()

    allowed_dirs = policy.allowed_dirs
    if allowed_dirs is not None:
        resolved_allowed = []
        for d in allowed_dirs:
            ad = Path(d)
            resolved_allowed.append(ad if ad.is_absolute() else (Path(policy.cwd) / ad).resolve())

        in_allowed = False
        for ad in resolved_allowed:
            if resolved == ad or ad in resolved.parents:
                in_allowed = True
                break
        if not in_allowed:
            return None, f"'{path_str}' is outside the allowed directories"

    if policy.blocked_paths:
        path_str_matched = str(resolved)
        for pattern in policy.blocked_paths:
            if fnmatch.fnmatch(path_str_matched, pattern) or fnmatch.fnmatch(resolved.name, pattern):
                return None, f"'{path_str}' matches a blocked path pattern '{pattern}'"

    if policy.blocked_extensions:
        if resolved.suffix.lower() in [ext.lower() for ext in policy.blocked_extensions]:
            return None, f"file extension '{resolved.suffix}' is not allowed for '{path_str}'"

    return str(resolved), None


def check_bash_command(command: str, policy: Policy) -> tuple[bool, Optional[str]]:
    """Check whether a bash command is allowed by the policy.

    Returns:
        (allowed, error_message)
    """
    if not command.strip():
        return True, None

    base_cmds = _extract_commands(command)

    for cmd in base_cmds:
        if policy.bash_allowed_commands is not None:
            if cmd not in policy.bash_allowed_commands:
                return False, f"command '{cmd}' is not in the allowed commands list"

        if policy.bash_blocked_commands is not None:
            if cmd in policy.bash_blocked_commands:
                return False, f"command '{cmd}' is blocked"

        if not policy.bash_allow_network and cmd in NETWORK_COMMANDS:
            return False, f"network command '{cmd}' is not allowed"

    return True, None


def _extract_commands(command: str) -> list[str]:
    """Extract base command names from a bash command string.

    Handles chaining (&&, ||, ;, |) and common prefixes (sudo, nohup, time, \\).
    Returns list of base commands like ["cd", "ls", "python"].
    """
    segments = re.split(r'&&|\|\||;|\||\n', command)
    prefixes = {"sudo", "nohup", "time"}

    result = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        tokens = seg.split()
        if not tokens:
            continue

        first = tokens[0]
        while first in prefixes or first == "\\":
            tokens = tokens[1:]
            if not tokens:
                break
            first = tokens[0]
        if first:
            result.append(first)

    return result
