"""MCPFactory — manages MCPServerConfig CRUD and MCP tool discovery.

Does NOT hold MCPClient instances (those are per-agent, managed by
AgentFactory). Notifies ToolFactory when MCP servers are added/removed/updated.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from BBagent.core.mcp import (
    MCPClient,
    MCPServerConfig as CoreMCPServerConfig,
    parse_config_dict as _parse_mcp_dict,
)

from backend.schemas import MCPServerConfig, ToolConfig
from backend.factories import _next_id, _mcp_tool_id, _safe_filename

if TYPE_CHECKING:
    from backend.factories.tool_factory import ToolFactory


class MCPFactory:
    def __init__(self, data_dir: Path, tool_factory: "ToolFactory"):
        self._data_dir = data_dir
        self._configs: dict[str, MCPServerConfig] = {}  # mcp_id -> MCPServerConfig
        self._tool_factory = tool_factory
        self._logger = logging.getLogger("state.mcp_factory")

    def _mcps_dir(self) -> Path:
        return self._data_dir / "mcps"

    def _file_path(self, mcp_id: str) -> Path:
        return self._mcps_dir() / f"{_safe_filename(mcp_id)}.json"

    def _save_file(self, config: MCPServerConfig):
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    def _delete_file(self, mcp_id: str):
        p = self._file_path(mcp_id)
        if p.exists():
            p.unlink()

    # --- load ---

    async def load(self):
        mcps_dir = self._mcps_dir()
        self._configs = {}

        for item in sorted(mcps_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                core_configs = _parse_mcp_dict(data, default_name=item.stem)
                for core_cfg in core_configs:
                    config = MCPServerConfig(
                        id=data["id"],
                        name=core_cfg.name,
                        command=core_cfg.command,
                        args=core_cfg.args,
                        env=core_cfg.env,
                        tools=[ToolConfig(**t) for t in (data.get("tools") or [])],
                    )
                    if config.id in self._configs:
                        continue
                    self._configs[config.id] = config
                    self._tool_factory.on_mcp_added(config.id, config.tools)
            except Exception as e:
                self._logger.warning(f"Failed to load MCP from {item}: {e}")

        # Re-discover tools for MCPs whose tools field is empty — in parallel
        empty_configs = [c for c in self._configs.values() if not c.tools]
        if empty_configs:
            results = await asyncio.gather(
                *[self._discover_tools(c) for c in empty_configs],
                return_exceptions=True,
            )
            for config, result in zip(empty_configs, results):
                if isinstance(result, Exception):
                    self._logger.warning(
                        f"Failed to discover tools for MCP '{config.name}' during load: {result}"
                    )

    # --- CRUD ---

    def get(self, mcp_id: str) -> Optional[MCPServerConfig]:
        return self._configs.get(mcp_id)

    def list_all(self) -> list[MCPServerConfig]:
        return list(self._configs.values())

    async def add(self, config: MCPServerConfig) -> MCPServerConfig:
        if not config.id:
            config = config.model_copy(update={"id": _next_id()})
        self._configs[config.id] = config
        self._save_file(config)
        self._tool_factory.on_mcp_added(config.id, config.tools)
        try:
            await self._discover_tools(config)
        except Exception as e:
            self._logger.warning(f"Failed to discover tools for MCP '{config.name}': {e}")
        return config

    async def update(self, mcp_id: str, updates: dict) -> Optional[MCPServerConfig]:
        config = self._configs.get(mcp_id)
        if not config:
            return None
        data = config.model_dump()
        data.update(updates)
        new_config = MCPServerConfig(**data)
        new_config.id = mcp_id  # id is immutable
        self._configs[mcp_id] = new_config
        self._save_file(new_config)
        self._tool_factory.on_mcp_updated(mcp_id, new_config.tools)
        if any(k in updates for k in ("command", "args", "env")):
            try:
                await self._discover_tools(new_config)
            except Exception as e:
                self._logger.warning(
                    f"Failed to re-discover tools for MCP '{new_config.name}': {e}"
                )
        return new_config

    def delete(self, mcp_id: str) -> bool:
        config = self._configs.pop(mcp_id, None)
        if not config:
            return False
        self._delete_file(mcp_id)
        self._tool_factory.on_mcp_removed(mcp_id)
        return True

    # --- MCP client creation (for ToolFactory / AgentFactory) ---

    def create_client(self, mcp_id: str) -> MCPClient:
        """Create a new MCPClient instance for the given server."""
        config = self._configs.get(mcp_id)
        if not config:
            raise ValueError(f"MCP server '{mcp_id}' not found")
        core_cfg = CoreMCPServerConfig(
            name=config.name,
            command=config.command,
            args=config.args,
            env=config.env,
        )
        return MCPClient(core_cfg)

    # --- tool discovery ---

    async def _discover_tools(self, config: MCPServerConfig) -> list[ToolConfig]:
        """Discover tools from an MCP server and update config + ToolFactory."""
        core_cfg = CoreMCPServerConfig(
            name=config.name,
            command=config.command,
            args=config.args,
            env=config.env,
        )
        client = MCPClient(core_cfg)
        try:
            await client.start()
            await client.initialize()
            tools_data = await client.list_tools()
        finally:
            await client.close()

        tool_configs = [
            ToolConfig(
                id=_mcp_tool_id(config.id, t["name"]),
                name=t["name"],
                source="mcp",
                description=t.get("description", ""),
                mcpServerId=config.id,
            )
            for t in tools_data
        ]
        config.tools = tool_configs
        self._save_file(config)
        self._tool_factory.on_mcp_updated(config.id, tool_configs)
        self._logger.info(f"Discovered {len(tool_configs)} tool(s) from MCP server '{config.name}'")
        return tool_configs

    async def discover_tools_by_id(self, mcp_id: str) -> list[ToolConfig]:
        """Public discover endpoint — discover tools for an MCP by id."""
        config = self._configs.get(mcp_id)
        if not config:
            raise ValueError(f"MCP server '{mcp_id}' not found")
        return await self._discover_tools(config)
