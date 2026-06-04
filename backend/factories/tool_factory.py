"""ToolFactory — manages ToolConfig registry and Tool instance construction.

Builtin tools are registered at init time with deterministic uuid5 IDs.
MCP tools are registered/removed by MCPFactory notifications.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

from BBagent.built_in_tool import TOOL_CREATOR
from BBagent.core.tool import Tool

from backend.schemas import ToolConfig
from backend.factories import _builtin_tool_id, _mcp_tool_id, _safe_filename


class ToolFactory:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._configs: dict[str, ToolConfig] = {}   # tool_id -> ToolConfig
        self._logger = logging.getLogger("state.tool_factory")

    def _tools_dir(self) -> Path:
        return self._data_dir / "tools"

    def _file_path(self, tool_id: str) -> Path:
        return self._tools_dir() / f"{_safe_filename(tool_id)}.json"

    def _save_file(self, config: ToolConfig):
        self._tools_dir().mkdir(parents=True, exist_ok=True)
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    # --- load ---

    def load(self):
        """Load persisted ToolConfigs, then register builtins."""
        tools_dir = self._tools_dir()
        if tools_dir.exists():
            for item in sorted(tools_dir.iterdir()):
                if not item.is_file() or item.suffix != ".json":
                    continue
                try:
                    data = json.loads(item.read_text(encoding="utf-8"))
                    config = ToolConfig(**data)
                    # MCP tools are registered by MCPFactory.load() via
                    # on_mcp_added/on_mcp_updated; skip them here to avoid
                    # double-registration and potential stale data.
                    if config.source == "mcp":
                        continue
                    self._configs[config.id] = config
                except Exception as e:
                    self._logger.warning(f"Failed to load tool config from {item}: {e}")
        self.load_builtins()

    def load_builtins(self):
        """Register builtin tool configs with deterministic IDs.

        Only creates entries for builtins not already in the registry.
        Builtin tools change very infrequently; existing persisted configs
        are reused directly.
        """
        for short_name in TOOL_CREATOR:
            tool_id = _builtin_tool_id(short_name)
            if tool_id in self._configs:
                continue
            config = ToolConfig(
                id=tool_id,
                name=short_name,
                source="built_in",
                description="",
            )
            self._configs[tool_id] = config
            self._save_file(config)

    # --- accessors ---

    def get(self, tool_id: str) -> Optional[ToolConfig]:
        return self._configs.get(tool_id)

    def list_all(self) -> list[ToolConfig]:
        return list(self._configs.values())

    def list_by_source(self, source: str) -> list[ToolConfig]:
        return [c for c in self._configs.values() if c.source == source]

    # --- MCP notification handlers ---

    def on_mcp_added(self, mcp_id: str, tools: list[ToolConfig]):
        """MCPFactory notification: register MCP ToolConfigs."""
        for t in tools:
            expected_id = _mcp_tool_id(mcp_id, t.name)
            assert t.id == expected_id, (
                f"ToolConfig id mismatch: got {t.id}, expected {expected_id} "
                f"for mcp={mcp_id} tool={t.name}"
            )
            self._configs[t.id] = ToolConfig(
                id=t.id,
                name=t.name,
                source="mcp",
                description=t.description,
                mcpServerId=mcp_id,
            )

    def on_mcp_removed(self, mcp_id: str):
        """MCPFactory notification: remove all ToolConfigs for this MCP."""
        to_remove = [
            tid for tid, t in self._configs.items()
            if t.source == "mcp" and t.mcpServerId == mcp_id
        ]
        for tid in to_remove:
            self._configs.pop(tid, None)

    def on_mcp_updated(self, mcp_id: str, tools: list[ToolConfig]):
        """MCPFactory notification: refresh MCP ToolConfigs."""
        self.on_mcp_removed(mcp_id)
        self.on_mcp_added(mcp_id, tools)

    # --- Tool instance construction ---

    async def build_tool(
        self,
        tool_id: str,
        policy=None,
        mcp_client_getter=None,
    ) -> Tool:
        """Build a Tool instance from a ToolConfig.

        Args:
            tool_id: ToolConfig id (UUID).
            policy: Policy object for builtin tools.
            mcp_client_getter: async callable(mcp_server_id) -> MCPClient.
                Required for MCP tools; ignored for builtin tools.
        """
        config = self._configs.get(tool_id)
        if config is None:
            raise ValueError(f"ToolConfig not found: {tool_id}")

        if config.source == "built_in":
            creator = TOOL_CREATOR.get(config.name)
            if creator is None:
                raise ValueError(f"No creator for builtin tool '{config.name}'")
            if asyncio.iscoroutinefunction(creator):
                tool = await creator(policy)
            else:
                tool = creator(policy)
            return tool

        if config.source == "mcp":
            if mcp_client_getter is None:
                raise ValueError(
                    f"mcp_client_getter is required for MCP tool '{tool_id}'"
                )
            client = await mcp_client_getter(config.mcpServerId or "")
            # Use client.create_tools() to get tools with real inputSchema,
            # then match by name. This ensures proper function signatures.
            mcp_tools = await client.create_tools()
            for tool in mcp_tools:
                if tool.raw_name == config.name:
                    return tool
            raise ValueError(
                f"MCP tool '{config.name}' not found on server "
                f"'{config.mcpServerId}'"
            )

        raise ValueError(f"Tool source '{config.source}' not supported")