"""State — coordinator that initializes and delegates to factories.

The State class is a singleton that owns all factory instances and
provides the public surface used by the API layer. It initializes
factories in dependency order and injects cross-factory references.

All per-resource CRUD and runtime logic lives in the individual factories.
State only coordinates cross-cutting concerns (e.g. model invalidation
affecting agents, MCP removal affecting tools).
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from backend.schemas import UIState
from backend.logging import get_backend_logger
from backend.dispatcher import AgentOutputDispatcher
from backend.errors import NotFoundError, ErrorCode

from backend.factories.model_factory import ModelFactory
from backend.factories.prompt_factory import PromptFactory
from backend.factories.skill_factory import SkillFactory
from backend.factories.tool_factory import ToolFactory
from backend.factories.mcp_factory import MCPFactory
from backend.factories.agent_factory import AgentFactory
from backend.factories.team_factory import TeamFactory
from backend.factories.session_factory import SessionManager

logger = get_backend_logger("state")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class State:
    """Coordinator singleton. Delegates to factories."""

    _instance: Optional["State"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Ensure data directories exist
        self._ensure_data_dir()

        # --- Instantiate factories (dependency order) ---
        self.model_factory = ModelFactory(DATA_DIR)
        self.prompt_factory = PromptFactory(DATA_DIR)
        self.skill_factory = SkillFactory(DATA_DIR)
        self.tool_factory = ToolFactory(DATA_DIR)
        self.mcp_factory = MCPFactory(DATA_DIR, self.tool_factory)
        self.agent_factory = AgentFactory(
            DATA_DIR, self.model_factory, self.tool_factory,
            self.skill_factory, self.mcp_factory,
        )
        self.team_factory = TeamFactory(DATA_DIR, self.agent_factory)

        # Global dispatcher for cross-agent state events.
        # Chat WS subscribes once and receives agent_state for all agents.
        self.global_dispatcher = AgentOutputDispatcher(replay_buffer=False)
        self.agent_factory.global_dispatcher = self.global_dispatcher
        self.agent_factory.team_factory = self.team_factory

        # UI state (not factory-managed)
        self.ui_state: UIState = UIState()

        # Session manager (initialized after agents are loaded)
        self.session_manager: SessionManager | None = None

        self._loaded = False

    def _ensure_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for subdir in ("agents", "teams", "models", "mcps", "prompts", "skills", "tools"):
            (DATA_DIR / subdir).mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Load all
    # ------------------------------------------------------------------

    async def load_all(self):
        if self._loaded:
            return

        # 1. No-dependency factories — run in parallel via thread pool
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            loop.run_in_executor(None, self.model_factory.load),
            loop.run_in_executor(None, self.prompt_factory.load),
            loop.run_in_executor(None, self.skill_factory.load),
            loop.run_in_executor(None, self.tool_factory.load),
        )

        # 2. MCPFactory + AgentFactory in parallel
        #    - mcp_factory depends on tool_factory (calls on_mcp_added) ✓ done
        #    - agent_factory.load() only reads configs + acquire model ✓ done
        #    - agent_factory does NOT touch MCP during load (only during start)
        await asyncio.gather(
            self.mcp_factory.load(),
            self.agent_factory.load(),
        )

        # 3. Start persisted agents + load teams in parallel
        #    - start_persisted_agents needs mcp_factory (lazy_init → _get_mcp_client) ✓ done
        #    - team_factory.load only reads team configs (no dependency on agent start)
        await asyncio.gather(
            self.agent_factory.start_persisted_agents(),
            self.team_factory.load(),
        )

        # 4. Build global session index after all agents are loaded
        self.session_manager = SessionManager(self.agent_factory)
        self.session_manager.build_index()

        # 5. UI state
        self._load_ui_state()

        self._loaded = True
        logger.info("State loaded all data")

    # ------------------------------------------------------------------
    # UI state persistence
    # ------------------------------------------------------------------

    def _load_ui_state(self):
        path = DATA_DIR / "store.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.ui_state = UIState(**data)
            except Exception as e:
                logger.warning(f"Failed to load ui state: {e}")
                self.ui_state = UIState()

    def save_ui_state(self):
        path = DATA_DIR / "store.json"
        path.write_text(
            self.ui_state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Model delegation (with cross-cutting invalidation)
    # ------------------------------------------------------------------

    def get_model(self, model_id: str):
        return self.model_factory.get(model_id)

    def add_model(self, config):
        return self.model_factory.add(config)

    def update_model(self, model_id: str, updates: dict):
        return self.model_factory.update(model_id, updates)

    async def update_model_and_invalidate(self, model_id: str, updates: dict):
        new_config = self.model_factory.update(model_id, updates)
        if new_config is None:
            return None, []
        affected = await self.invalidate_model(model_id)
        return new_config, affected

    def delete_model(self, model_id: str) -> bool:
        return self.model_factory.delete(model_id)

    async def delete_model_and_invalidate(self, model_id: str):
        # Collect affected agents before deletion
        affected = [
            agent_id for agent_id, mid in self.agent_factory._model_ids.items()
            if mid == model_id
        ]
        # Stop affected agents first
        for agent_id in affected:
            try:
                await self.agent_factory.stop(agent_id)
            except Exception:
                pass
        # Now delete the model config and invalidate cache
        ok = self.model_factory.delete(model_id)
        if not ok:
            return False, []
        await self.model_factory.invalidate(model_id)
        return True, affected

    async def invalidate_model(self, model_id: str) -> list[str]:
        """Invalidate cached Model instance and hot-swap for running agents.

        After invalidating the cached Model, acquires a fresh Model instance
        from the (already updated) ModelConfig and calls change_model on
        each affected agent so they pick up the new config immediately.
        """
        await self.model_factory.invalidate(model_id)
        affected = [
            agent_id for agent_id, mid in self.agent_factory._model_ids.items()
            if mid == model_id
        ]
        for agent_id in affected:
            agent = self.agent_factory.agents.get(agent_id)
            if agent is None:
                continue
            try:
                new_model = self.model_factory.acquire(model_id)
                agent.change_model(new_model)
            except Exception:
                pass
        return affected

    # ------------------------------------------------------------------
    # MCP delegation
    # ------------------------------------------------------------------

    def get_mcp(self, mcp_id: str):
        return self.mcp_factory.get(mcp_id)

    async def add_mcp(self, config):
        return await self.mcp_factory.add(config)

    async def update_mcp(self, mcp_id: str, updates: dict):
        return await self.mcp_factory.update(mcp_id, updates)

    def delete_mcp(self, mcp_id: str) -> bool:
        return self.mcp_factory.delete(mcp_id)

    async def discover_mcp_tools(self, mcp_id: str):
        return await self.mcp_factory.discover_tools_by_id(mcp_id)

    # ------------------------------------------------------------------
    # Prompt delegation
    # ------------------------------------------------------------------

    def get_prompt(self, prompt_id: str):
        return self.prompt_factory.get(prompt_id)

    def add_prompt(self, config):
        return self.prompt_factory.add(config)

    def update_prompt(self, prompt_id: str, updates: dict):
        return self.prompt_factory.update(prompt_id, updates)

    def delete_prompt(self, prompt_id: str) -> bool:
        return self.prompt_factory.delete(prompt_id)

    # ------------------------------------------------------------------
    # Skill delegation
    # ------------------------------------------------------------------

    def list_skills(self):
        return self.skill_factory.list_all()

    def import_skills_from_dir(self, dir_path: Path) -> tuple[list, list[str]]:
        return self.skill_factory.import_dir(dir_path)

    def delete_skill(self, skill_id: str) -> bool:
        return self.skill_factory.delete(skill_id)

    def refresh_skill(self, skill_id: str):
        return self.skill_factory.refresh(skill_id)

    # ------------------------------------------------------------------
    # Agent delegation
    # ------------------------------------------------------------------

    def get_agent_config(self, agent_id: str):
        return self.agent_factory.get_agent_config(agent_id)

    async def create_agent(self, config):
        return await self.agent_factory.create(config)

    async def update_agent(self, agent_id: str, updates: dict):
        return await self.agent_factory.update(agent_id, updates)

    async def delete_agent(self, agent_id: str):
        return await self.agent_factory.delete(agent_id)

    async def start_agent(self, agent_id: str):
        return await self.agent_factory.start(agent_id)

    async def stop_agent(self, agent_id: str):
        return await self.agent_factory.stop(agent_id)

    def get_agent_state(self, agent_id: str) -> dict:
        return self.agent_factory.get_state(agent_id)

    def get_agent_sessions(self, agent_id: str) -> list[dict]:
        return self.agent_factory.get_sessions(agent_id)

    def _assert_agent_session_mutation_allowed(self, agent_id: str):
        for team in self.team_factory.teams.values():
            self.team_factory.conversations.assert_member_session_switch_allowed(team, agent_id)

    async def switch_agent_session(self, agent_id: str, session_id: str):
        self._assert_agent_session_mutation_allowed(agent_id)
        return await self.agent_factory.switch_session(agent_id, session_id)

    async def new_agent_session(self, agent_id: str):
        self._assert_agent_session_mutation_allowed(agent_id)
        return await self.agent_factory.new_session(agent_id)

    def get_agent_messages(self, agent_id: str) -> list[dict]:
        return self.agent_factory.get_messages(agent_id)

    def get_agent_dispatcher(self, agent_id: str):
        return self.agent_factory.get_dispatcher(agent_id)

    # ------------------------------------------------------------------
    # Session delegation (global)
    # ------------------------------------------------------------------

    def list_all_sessions(self, agent_id: str = None) -> list[dict]:
        if not self.session_manager:
            return []
        return self.session_manager.list_sessions(agent_id)

    async def get_session_detail(self, session_id: str) -> dict:
        if not self.session_manager:
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, "Session manager not initialized")
        return await self.session_manager.get_session_detail(session_id)

    async def fork_session_at_turn(self, session_id: str, turn_index: int,
                                   target_agent_id: str = None) -> dict:
        if not self.session_manager:
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, "Session manager not initialized")
        return await self.session_manager.fork_at_turn(session_id, turn_index, target_agent_id)

    def reindex_sessions(self) -> None:
        if self.session_manager:
            self.session_manager.build_index()

    def delete_session(self, session_id: str) -> bool:
        if not self.session_manager:
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, "Session manager not initialized")
        return self.session_manager.delete_session(session_id)

    # ------------------------------------------------------------------
    # Team delegation
    # ------------------------------------------------------------------

    def get_team_config(self, team_id: str):
        return self.team_factory.get_config(team_id)

    async def create_team(self, config, member_configs=None):
        return await self.team_factory.create(config, member_configs=member_configs)

    async def update_team(self, team_id: str, updates: dict):
        return await self.team_factory.update(team_id, updates)

    async def delete_team(self, team_id: str) -> bool:
        return await self.team_factory.delete(team_id)

    # ------------------------------------------------------------------
    # Tool listing (for API)
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """Return all tool configs as dicts for the API."""
        tools = []
        for tid, tpl in self.tool_factory._configs.items():
            entry = {
                "id": tpl.id,
                "name": tpl.name,
                "source": tpl.source,
                "description": tpl.description,
            }
            if tpl.source == "mcp" and tpl.mcpServerId:
                mcp_cfg = self.mcp_factory.get(tpl.mcpServerId)
                entry["mcpServerId"] = tpl.mcpServerId
                entry["mcpServerName"] = mcp_cfg.name if mcp_cfg else tpl.mcpServerId
            tools.append(entry)

        # Undiscovered MCP servers
        for mcp_cfg in self.mcp_factory.list_all():
            if not mcp_cfg.tools:
                tools.append({
                    "id": f"mcp-server:{mcp_cfg.id}",
                    "name": mcp_cfg.name,
                    "source": "mcp",
                    "description": f"MCP Server: {mcp_cfg.name} (no tools discovered)",
                    "mcpServerId": mcp_cfg.id,
                    "mcpServerName": mcp_cfg.name,
                })

        return tools


# Global singleton
state_manager = State()
