import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from BBagent.core.agent import Agent, AgentConfig as CoreAgentConfig, AgentState
from BBagent.core.team import AgentTeam, TeamConfig as CoreTeamConfig
from BBagent.core.model import Model
from BBagent.core.skill import Skill, scan_skills
from BBagent.core.mcp import MCPClient, MCPServerConfig as CoreMCPServerConfig

from backend.schemas import (
    ModelConfig,
    MCPServerConfig,
    PromptConfig,
    SkillConfig,
    AgentConfig,
    TeamConfig,
    UIState,
)
from backend.dispatcher import AgentOutputDispatcher
from backend.logging import get_backend_logger, log_operation
from backend.errors import (
    AppError, ErrorCode,
    NotFoundError, ConflictError, InternalError,
)

# camelCase (frontend) -> snake_case (core Policy)
_POLICY_FIELD_MAP = {
    "maxReadSize": "max_read_size",
    "maxReadLines": "max_read_lines",
    "maxWriteSize": "max_write_size",
    "writeCreateDirectories": "write_create_directories",
    "bashMaxOutputLines": "bash_max_output_lines",
    "bashDefaultTimeout": "bash_default_timeout",
}


def _policy_to_snake(policy: dict) -> dict:
    return {_POLICY_FIELD_MAP.get(k, k): v for k, v in policy.items()}


# Reverse: snake_case -> camelCase for frontend consumption
_POLICY_FIELD_MAP_REV = {v: k for k, v in _POLICY_FIELD_MAP.items()}


def _policy_to_camel(policy: dict) -> dict:
    """Convert a Policy dict from snake_case (core) to camelCase (frontend)."""
    if not policy:
        return {}
    return {_POLICY_FIELD_MAP_REV.get(k, k): v for k, v in policy.items()}


logger = get_backend_logger("state")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

class StateManager:
    _instance: Optional["StateManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.models: List[ModelConfig] = []
        self.mcp_servers: List[MCPServerConfig] = []
        self.prompts: List[PromptConfig] = []
        self.skills: Dict[str, Skill] = {}
        self.skill_dirs: List[str] = []
        self.agents: Dict[str, Agent] = {}
        self.teams: Dict[str, AgentTeam] = {}
        self.ui_state: UIState = UIState()

        self._agent_dispatchers: Dict[str, AgentOutputDispatcher] = {}
        self._agent_tasks: Dict[str, asyncio.Task] = {}
        self._agent_model_ids: Dict[str, str] = {}

        self._agent_started: set[str] = set()
        self._agent_tool_metas: dict[str, list[dict]] = {}
        self._agent_mcp_metas: dict[str, list[dict]] = {}
        self._agent_skill_metas: dict[str, list[dict]] = {}
        self._agent_hook_metas: dict[str, list[dict]] = {}
        self._agent_timer_metas: dict[str, list[dict]] = {}

        self._ensure_data_dir()
        self._loaded = False

    # ------------------------------------------------------------------
    # 路径 helpers
    # ------------------------------------------------------------------
    def _ensure_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "agents").mkdir(exist_ok=True)
        (DATA_DIR / "teams").mkdir(exist_ok=True)
        (DATA_DIR / "models").mkdir(exist_ok=True)
        (DATA_DIR / "mcps").mkdir(exist_ok=True)
        (DATA_DIR / "prompts").mkdir(exist_ok=True)
        (DATA_DIR / "skills").mkdir(exist_ok=True)

    def _models_dir(self) -> Path:
        return DATA_DIR / "models"

    def _mcps_dir(self) -> Path:
        return DATA_DIR / "mcps"

    def _prompts_dir(self) -> Path:
        return DATA_DIR / "prompts"

    def _skill_dirs_path(self) -> Path:
        return DATA_DIR / "skills" / "skills.json"

    def _store_path(self) -> Path:
        return DATA_DIR / "store.json"

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    async def load_all(self):
        if self._loaded:
            return
        self._load_models()
        self._load_mcps()
        self._load_prompts()
        self._load_skills()
        await self._load_agents()
        await self._load_teams()
        self._load_ui_state()
        self._loaded = True
        logger.info("StateManager loaded all data")

    def _load_models(self):
        models_dir = self._models_dir()
        self.models = []
        seen_ids: set = set()

        for item in sorted(models_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                config = ModelConfig(**data)
                if config.id not in seen_ids:
                    self.models.append(config)
                    seen_ids.add(config.id)
            except Exception as e:
                logger.warning(f"Failed to load model from {item}: {e}")

    def _load_mcps(self):
        mcps_dir = self._mcps_dir()
        self.mcp_servers = []
        seen_names: set = set()

        for item in sorted(mcps_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                entries = self._extract_mcp_entries(data, item.stem)
                for entry in entries:
                    config = MCPServerConfig(**entry)
                    if config.name not in seen_names:
                        self.mcp_servers.append(config)
                        seen_names.add(config.name)
                        self._save_mcp_file(config)
            except Exception as e:
                logger.warning(f"Failed to load MCP from {item}: {e}")

    def _load_prompts(self):
        prompts_dir = self._prompts_dir()
        self.prompts = []
        seen_ids: set = set()

        for item in sorted(prompts_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                config = PromptConfig(**data)
                if config.id not in seen_ids:
                    self.prompts.append(config)
                    seen_ids.add(config.id)
            except Exception as e:
                logger.warning(f"Failed to load prompt from {item}: {e}")

    def _load_skills(self):
        dirs_path = self._skill_dirs_path()

        if dirs_path.exists():
            try:
                self.skill_dirs = json.loads(dirs_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load skill dirs: {e}")
                self.skill_dirs = []
        else:
            self.skill_dirs = []

        self.skills = {}
        for d in self.skill_dirs:
            dir_path = Path(d)
            if not dir_path.exists():
                continue
            try:
                scanned = scan_skills(dir_path)
                for name, skill in scanned.items():
                    if name not in self.skills:
                        self.skills[name] = skill
            except Exception as e:
                logger.warning(f"Failed to load skills from {d}: {e}")

    async def _load_agents(self):
        agents_dir = DATA_DIR / "agents"
        if not agents_dir.exists():
            return
        dirs = sorted(
            d for d in agents_dir.iterdir()
            if d.is_dir() and (d / "agent_config.yaml").exists()
        )
        if not dirs:
            return

        results = await asyncio.gather(
            *[asyncio.to_thread(self._load_one_agent, d) for d in dirs],
            return_exceptions=True,
        )
        loaded, failed = 0, 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                logger.error("Failed to load agent from '%s': %s",
                             dirs[i].name, result, exc_info=True)
            else:
                loaded += 1
        logger.info("Agent loading: %d loaded, %d failed", loaded, failed)

    def _load_one_agent(self, agent_dir: Path):
        config_path = agent_dir / "agent_config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f) or {}

        name = config_dict.get("name", agent_dir.name)

        tool_cfgs = config_dict.get("tools", [])
        self._agent_tool_metas[name] = [t for t in tool_cfgs if t.get("source") != "mcp"]
        self._agent_mcp_metas[name] = [t for t in tool_cfgs if t.get("source") == "mcp"]
        self._agent_skill_metas[name] = config_dict.get("skills", [])
        self._agent_hook_metas[name] = config_dict.get("hooks", [])
        self._agent_timer_metas[name] = config_dict.get("timers", [])

        model_id = config_dict.get("model_id", "")
        if not model_id:
            model_data = config_dict.get("model", {})
            if isinstance(model_data, dict):
                model_id = model_data.get("model_id", "")
        # Fallback: match by provider + model name against registered models
        if not model_id:
            model_data = config_dict.get("model", {})
            if isinstance(model_data, dict):
                provider = model_data.get("provider", "")
                model_name = model_data.get("model", "")
                for m in self.models:
                    if m.provider == provider and m.modelName == model_name:
                        model_id = m.id
                        break
        if model_id:
            self._agent_model_ids[name] = model_id
        else:
            self._agent_model_ids[name] = ""

        # Extract policy before stripping tools (backward compat with old YAML
        # that stored policy inside each tool's config rather than at top level)
        policy = config_dict.get("policy", None)
        if not policy:
            for tool_cfg in config_dict.get("tools", []):
                tool_policy = tool_cfg.get("config", {}).get("policy", None)
                if tool_policy:
                    policy = tool_policy
                    break

        deferred_keys = {"tools", "skills", "hooks", "timers"}
        stripped = {k: v for k, v in config_dict.items() if k not in deferred_keys}
        if policy:
            stripped["policy"] = policy

        try:
            agent = asyncio.run(Agent.from_config_dict(stripped, base_dir=agent_dir))
            # Sync working_dir from policy cwd
            if agent.policy and agent.policy.get("cwd"):
                agent.working_dir = agent.policy["cwd"]
            self.agents[name] = agent
            if model_id:
                self._save_agent_model_id(name, model_id)
            agent.logger.set_console_level(logging.CRITICAL + 1)
            self._agent_dispatchers[name] = AgentOutputDispatcher()
            logger.info("Loaded agent '%s' from '%s'", name, agent_dir.name)
        except Exception:
            for cache in (self._agent_tool_metas, self._agent_mcp_metas,
                          self._agent_skill_metas, self._agent_hook_metas,
                          self._agent_timer_metas):
                cache.pop(name, None)
            self._agent_model_ids.pop(name, None)
            raise

    async def _load_teams(self):
        teams_dir = DATA_DIR / "teams"
        if not teams_dir.exists():
            return
        dirs = sorted(
            d for d in teams_dir.iterdir()
            if d.is_dir() and (d / "team_config.yaml").exists()
        )
        if not dirs:
            return

        results = await asyncio.gather(
            *[self._load_one_team(d) for d in dirs],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Failed to load team from '%s': %s", dirs[i].name, result)

    async def _load_one_team(self, team_dir: Path):
        team = await AgentTeam.load(team_dir)
        self.teams[team.name] = team

    def _load_ui_state(self):
        path = self._store_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.ui_state = UIState(**data)
            except Exception as e:
                logger.warning(f"Failed to load ui state: {e}")
                self.ui_state = UIState()

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def _model_file_path(self, model_id: str) -> Path:
        safe_id = "".join(c for c in model_id if c.isalnum() or c in "._-")
        return self._models_dir() / f"{safe_id}.json"

    def _save_model_file(self, config: ModelConfig):
        path = self._model_file_path(config.id)
        path.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _delete_model_file(self, model_id: str):
        path = self._model_file_path(model_id)
        if path.exists():
            path.unlink()

    def save_models(self):
        existing_ids = {m.id for m in self.models}
        for item in sorted(self._models_dir().iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            model_id = item.stem
            if model_id not in existing_ids:
                try:
                    item.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove stale model file {item}: {e}")
        for config in self.models:
            self._save_model_file(config)

    def _mcp_file_path(self, name: str) -> Path:
        safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
        return self._mcps_dir() / f"{safe_name}.json"

    @staticmethod
    def _extract_mcp_entries(data: dict, default_name: str) -> list[dict]:
        if "mcpServers" in data:
            servers = data["mcpServers"]
            if isinstance(servers, list):
                entries = [{"name": e.pop("name", default_name), **e} for e in servers if isinstance(e, dict)]
            elif isinstance(servers, dict):
                entries = [{"name": name, **cfg} for name, cfg in servers.items() if isinstance(cfg, dict)]
            else:
                entries = []
        elif isinstance(data, dict) and "name" in data and "command" in data:
            entries = [data]
        else:
            entries = []
        return entries

    def _save_mcp_file(self, config: MCPServerConfig):
        path = self._mcp_file_path(config.name)
        path.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _delete_mcp_file(self, name: str):
        path = self._mcp_file_path(name)
        if path.exists():
            path.unlink()

    def save_mcps(self):
        existing_names = {m.name for m in self.mcp_servers}
        for item in sorted(self._mcps_dir().iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            name = item.stem
            if name not in existing_names:
                try:
                    item.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove stale MCP file {item}: {e}")
        for config in self.mcp_servers:
            self._save_mcp_file(config)

    def _prompt_file_path(self, prompt_id: str) -> Path:
        safe_id = "".join(c for c in prompt_id if c.isalnum() or c in "._-")
        return self._prompts_dir() / f"{safe_id}.json"

    def _save_prompt_file(self, config: PromptConfig):
        path = self._prompt_file_path(config.id)
        path.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _delete_prompt_file(self, prompt_id: str):
        path = self._prompt_file_path(prompt_id)
        if path.exists():
            path.unlink()

    def save_prompts(self):
        existing_ids = {p.id for p in self.prompts}
        for item in sorted(self._prompts_dir().iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            prompt_id = item.stem
            if prompt_id not in existing_ids:
                try:
                    item.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove stale prompt file {item}: {e}")
        for config in self.prompts:
            self._save_prompt_file(config)

    def save_ui_state(self):
        path = self._store_path()
        path.write_text(
            self.ui_state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Model CRUD
    # ------------------------------------------------------------------
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def add_model(self, config: ModelConfig) -> ModelConfig:
        self.models.append(config)
        self._save_model_file(config)
        return config

    def update_model(self, model_id: str, updates: dict) -> Optional[ModelConfig]:
        for i, m in enumerate(self.models):
            if m.id == model_id:
                old_id = m.id
                data = m.model_dump()
                data.update(updates)
                self.models[i] = ModelConfig(**data)
                new_config = self.models[i]
                if new_config.id != old_id:
                    self._delete_model_file(old_id)
                self._save_model_file(new_config)
                return new_config
        return None

    def delete_model(self, model_id: str) -> bool:
        for i, m in enumerate(self.models):
            if m.id == model_id:
                self.models.pop(i)
                self._delete_model_file(model_id)
                return True
        return False

    # ------------------------------------------------------------------
    # MCP CRUD
    # ------------------------------------------------------------------
    def get_mcp(self, name: str) -> Optional[MCPServerConfig]:
        for m in self.mcp_servers:
            if m.name == name:
                return m
        return None

    async def add_mcp(self, config: MCPServerConfig) -> MCPServerConfig:
        self.mcp_servers.append(config)
        self._save_mcp_file(config)
        try:
            await self._discover_mcp_tools(config.name)
        except Exception as e:
            logger.warning(f"Failed to discover tools for MCP '{config.name}': {e}")
        return config

    async def update_mcp(self, name: str, updates: dict) -> Optional[MCPServerConfig]:
        for i, m in enumerate(self.mcp_servers):
            if m.name == name:
                old_name = m.name
                data = m.model_dump()
                data.update(updates)
                self.mcp_servers[i] = MCPServerConfig(**data)
                new_config = self.mcp_servers[i]
                if new_config.name != old_name:
                    self._delete_mcp_file(old_name)
                self._save_mcp_file(new_config)
                if any(k in updates for k in ("command", "args", "env")):
                    try:
                        await self._discover_mcp_tools(new_config.name)
                    except Exception as e:
                        logger.warning(f"Failed to re-discover tools for MCP '{new_config.name}': {e}")
                return new_config
        return None

    def delete_mcp(self, name: str) -> bool:
        for i, m in enumerate(self.mcp_servers):
            if m.name == name:
                self.mcp_servers.pop(i)
                self._delete_mcp_file(name)
                return True
        return False

    # ------------------------------------------------------------------
    # Prompt CRUD
    # ------------------------------------------------------------------
    def get_prompt(self, prompt_id: str) -> Optional[PromptConfig]:
        for p in self.prompts:
            if p.id == prompt_id:
                return p
        return None

    def add_prompt(self, config: PromptConfig) -> PromptConfig:
        self.prompts.append(config)
        self._save_prompt_file(config)
        return config

    def update_prompt(self, prompt_id: str, updates: dict) -> Optional[PromptConfig]:
        for i, p in enumerate(self.prompts):
            if p.id == prompt_id:
                old_id = p.id
                data = p.model_dump()
                data.update(updates)
                self.prompts[i] = PromptConfig(**data)
                new_config = self.prompts[i]
                if new_config.id != old_id:
                    self._delete_prompt_file(old_id)
                self._save_prompt_file(new_config)
                return new_config
        return None

    def delete_prompt(self, prompt_id: str) -> bool:
        for i, p in enumerate(self.prompts):
            if p.id == prompt_id:
                self.prompts.pop(i)
                self._delete_prompt_file(prompt_id)
                return True
        return False

    # ------------------------------------------------------------------
    # Skill
    # ------------------------------------------------------------------
    def list_skills(self) -> List[SkillConfig]:
        result = []
        for skill in self.skills.values():
            skill_path = str(skill.path.resolve()) if skill.path else ""
            result.append(
                SkillConfig(
                    name=skill.name,
                    description=skill.description,
                    path=skill_path,
                    body=skill.body,
                    metadata=skill.metadata.to_dict() if skill.metadata else {},
                )
            )
        return result

    def _save_skill_dirs(self):
        path = self._skill_dirs_path()
        path.write_text(
            json.dumps(self.skill_dirs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_imported_skills_dirs(self, dir_path: Path):
        path_str = str(dir_path.resolve())
        if path_str not in self.skill_dirs:
            self.skill_dirs.append(path_str)
        self._save_skill_dirs()

    # ------------------------------------------------------------------
    # Agent CRUD
    # ------------------------------------------------------------------
    def get_agent_config(self, name: str) -> Optional[AgentConfig]:
        agent = self.agents.get(name)
        if not agent:
            return None

        if agent.tools:
            tool_names = []
            for t in agent.tools.values():
                src = getattr(t, "source", "")
                if src.startswith("built_in."):
                    tool_names.append(src[len("built_in."):])
                elif src:
                    tool_names.append(src)
        else:
            builtin = []
            for t in self._agent_tool_metas.get(name, []):
                src = t.get("source", "")
                # Normalize to short source name (strip "built_in." prefix)
                # to match frontend tool identifiers from GET /api/tools
                if src.startswith("built_in."):
                    builtin.append(src[len("built_in."):])
                elif src:
                    builtin.append(src)
            mcp = [t.get("tool_name", t.get("name", ""))
                   for t in self._agent_mcp_metas.get(name, [])]
            tool_names = [n for n in (*builtin, *mcp) if n]

        if agent.skills:
            skill_names = list(agent.skills.keys())
        else:
            skill_names = [s.get("name", "")
                           for s in self._agent_skill_metas.get(name, [])]

        return AgentConfig(
            name=agent.name,
            modelId=self._agent_model_ids.get(name, ""),
            systemPrompt=agent.system_prompt,
            toolNames=tool_names,
            skillNames=skill_names,
            hookEnabled=bool(agent.hook and agent.hook._enabled),
            basePath=str(agent.base_dir),
            workingDir=(getattr(agent, "policy", {}) or {}).get("cwd", ""),
            policy=_policy_to_camel(getattr(agent, "policy", {}) or {}),
        )

    async def create_agent(self, config: AgentConfig) -> Agent:
        model_cfg = self.get_model(config.modelId)
        if not model_cfg:
            raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, f"Model '{config.modelId}' not found")

        model = Model.from_config_dict({
            "provider": model_cfg.provider,
            "model": model_cfg.modelName,
            "api_key": model_cfg.apiKey,
            "base_url": model_cfg.baseUrl,
            "max_completion_tokens": model_cfg.maxCompletionTokens,
            "max_context_tokens": model_cfg.maxContextTokens,
            "temperature": model_cfg.temperature,
            "top_p": model_cfg.topP,
            "thinking": model_cfg.thinking,
        })

        with log_operation(logger, "create_agent", agent_name=config.name):
            core_kwargs = {
                "model": model,
                "base_dir": DATA_DIR / "agents",
                "system_prompt": config.systemPrompt,
            }
            if config.name and config.name.strip():
                core_kwargs["name"] = config.name.strip()

            try:
                core_config = CoreAgentConfig(**core_kwargs)
                agent = Agent(core_config)
                agent.save()
            except Exception:
                agent_dir = DATA_DIR / "agents" / core_kwargs.get("name", "")
                if agent_dir and agent_dir.exists():
                    import shutil
                    shutil.rmtree(agent_dir, ignore_errors=True)
                raise

            actual_name = agent.name

            policy_snake = _policy_to_snake(config.policy) if config.policy else {}
            if policy_snake and not policy_snake.get("cwd"):
                policy_snake["cwd"] = str(agent.base_dir)
            agent.policy = policy_snake

            builtin_metas = [
                {"source": tn, "config": {}}
                for tn in config.toolNames if not tn.startswith("mcp:")
            ]
            mcp_metas = [
                {
                    "source": "mcp",
                    "config": {
                        "mcp_server_name": tn[4:],
                        "tool_name": tn[4:],
                    },
                }
                for tn in config.toolNames if tn.startswith("mcp:")
            ]
            skill_metas = [{"name": sn, "path": ""} for sn in config.skillNames]

            self._agent_tool_metas[actual_name] = builtin_metas
            self._agent_mcp_metas[actual_name] = mcp_metas
            self._agent_skill_metas[actual_name] = skill_metas
            self._agent_hook_metas[actual_name] = []
            self._agent_timer_metas[actual_name] = []
            self._agent_model_ids[actual_name] = config.modelId

            self.agents[actual_name] = agent
            agent.logger.set_console_level(logging.CRITICAL + 1)
            self._agent_dispatchers[actual_name] = AgentOutputDispatcher()
            self._save_agent_model_id(actual_name, config.modelId)
            await self.start_agent(actual_name)
            return agent

    async def start_agent(self, name: str):
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        if agent._running:
            logger.info("Agent '%s' already running, skipped", name)
            return

        if name not in self._agent_started:
            await self._lazy_init_agent(name)
            self._agent_started.add(name)

        dispatcher = self._agent_dispatchers.get(name)
        if not dispatcher:
            dispatcher = AgentOutputDispatcher()
            self._agent_dispatchers[name] = dispatcher

        agent.on_output(dispatcher.on_chunk)

        async def _run():
            try:
                await agent.start()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("Agent '%s' event loop crashed: %s", name, e, exc_info=True)

        with log_operation(logger, "start_agent", agent_name=name):
            task = asyncio.create_task(_run())
            self._agent_tasks[name] = task
            await asyncio.sleep(0)

    # ------------------------------------------------------------------
    # Lazy agent initialization (deferred from load time to start time)
    # ------------------------------------------------------------------
    async def _lazy_init_agent(self, name: str):
        agent = self.agents[name]
        policy_raw = getattr(agent, "policy", {}) or {}
        from BBagent.built_in_tool.policy import Policy
        if policy_raw:
            policy_snake = _policy_to_snake(policy_raw)
            if not policy_snake.get("cwd"):
                policy_snake["cwd"] = str(agent.base_dir)
            policy_obj = Policy(**policy_snake)
        else:
            policy_obj = None

        tool_metas = self._agent_tool_metas.get(name, [])
        mcp_metas = self._agent_mcp_metas.get(name, [])

        # Normalize cwd in stored tool metas for existing agents
        # that were created before cwd normalization was introduced
        for cfg in tool_metas:
            policy_in_cfg = cfg.get("config", {}).get("policy", {})
            if policy_in_cfg and not policy_in_cfg.get("cwd"):
                policy_in_cfg["cwd"] = str(agent.base_dir)

        builtin_tasks = [
            asyncio.to_thread(self._build_one_builtin_tool, cfg, policy_obj)
            for cfg in tool_metas
        ]
        mcp_tasks = [
            self._build_one_mcp(cfg) for cfg in mcp_metas
        ]

        all_results = await asyncio.gather(
            *(builtin_tasks + mcp_tasks), return_exceptions=True,
        )

        tools, mcp_clients = [], {}
        for result in all_results:
            if isinstance(result, Exception):
                logger.warning("Tool build failed for agent '%s': %s", name, result)
                continue
            t, mcp_map = result
            if isinstance(t, list):
                tools.extend(t)
            elif t is not None:
                tools.append(t)
            mcp_clients.update(mcp_map)

        if tools:
            agent.add_tools(tools)
        if mcp_clients:
            agent.register_mcp_clients(mcp_clients)

        for skill_cfg in self._agent_skill_metas.get(name, []):
            skill_name = skill_cfg.get("name", "")
            skill = self.skills.get(skill_name)
            if skill:
                agent.add_skills([skill])

        from BBagent.built_in_hook import HOOK_CREATOR
        for hc in self._agent_hook_metas.get(name, []):
            source = hc.get("source")
            hook_config = hc.get("config", {})
            if source and source in HOOK_CREATOR:
                HOOK_CREATOR[source](agent, hook_config)

        for tc in self._agent_timer_metas.get(name, []):
            agent.input.every(
                seconds=tc.get("seconds", 60),
                name=tc.get("name", ""),
                hint=tc.get("hint", ""),
            )

    def _build_one_builtin_tool(self, cfg: dict, policy_obj) -> tuple:
        from BBagent.built_in_tool import TOOL_CREATOR
        source = cfg.get("source", "")
        tool_cfg_data = cfg.get("config", {})

        builder = TOOL_CREATOR.get(source)
        if builder is None:
            builder = TOOL_CREATOR.get(f"built_in.{source}")
        if builder is None:
            raise ValueError(f"Unknown tool source: {source}")

        policy_sources = {"bash", "read", "write", "edit", "ls", "find", "grep",
                          "built_in.bash", "built_in.read", "built_in.write",
                          "built_in.edit", "built_in.ls", "built_in.find", "built_in.grep"}
        arg = policy_obj if (source in policy_sources and policy_obj is not None) else tool_cfg_data

        if asyncio.iscoroutinefunction(builder):
            tool = asyncio.run(builder(arg))
        else:
            tool = builder(arg)
        return (tool, {})

    async def _build_one_mcp(self, cfg: dict) -> tuple:
        config_data = cfg.get("config", {})
        server_name = config_data.get("mcp_server_name", "")
        tool_name = config_data.get("tool_name", "")
        if not server_name or not tool_name:
            raise ValueError(f"Invalid MCP config: missing server_name or tool_name")

        mcp_cfg = self.get_mcp(server_name)
        if not mcp_cfg:
            raise ValueError(f"MCP server '{server_name}' not found in registry")

        core_cfg = CoreMCPServerConfig(
            name=mcp_cfg.name, command=mcp_cfg.command,
            args=mcp_cfg.args, env=mcp_cfg.env,
        )
        client = MCPClient(core_cfg)
        try:
            await asyncio.wait_for(client.start(), timeout=15.0)
            await asyncio.wait_for(client.initialize(), timeout=15.0)
            all_tools = await client.create_tools()
        except asyncio.TimeoutError:
            await client.close()
            raise TimeoutError(f"MCP server '{server_name}' connection timed out")
        except Exception:
            await client.close()
            raise

        matched = [t for t in all_tools if getattr(t, '_mcp_tool_name', '') == tool_name]
        return (matched, {server_name: client})

    async def stop_agent(self, name: str):
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        with log_operation(logger, "stop_agent", agent_name=name):
            await agent.stop()

            task = self._agent_tasks.pop(name, None)
            if task and not task.done():
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Agent '%s' task did not stop within 5s, cancelling", name)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            dispatcher = self._agent_dispatchers.get(name)
            if dispatcher:
                await dispatcher.broadcast_system(f"Agent '{name}' has been stopped")

    async def start_all_agents(self):
        total = len(self.agents)
        started = 0
        failed = 0
        for name in list(self.agents.keys()):
            try:
                await self.start_agent(name)
                started += 1
            except Exception as e:
                failed += 1
                logger.error("Auto-start failed for '%s': %s", name, e)
        if total > 0:
            logger.info("Auto-start: %d/%d started, %d failed", started, total, failed)

    async def delete_agent(self, name: str) -> bool:
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        with log_operation(logger, "delete_agent", agent_name=name):
            try:
                await self.stop_agent(name)
            except Exception as e:
                logger.warning("Error stopping agent '%s' before delete: %s", name, e)

            task = self._agent_tasks.pop(name, None)
            if task and not task.done():
                task.cancel()

            del self.agents[name]
            self._agent_dispatchers.pop(name, None)
            self._agent_model_ids.pop(name, None)
            self._agent_started.discard(name)
            self._agent_tool_metas.pop(name, None)
            self._agent_mcp_metas.pop(name, None)
            self._agent_skill_metas.pop(name, None)
            self._agent_hook_metas.pop(name, None)
            self._agent_timer_metas.pop(name, None)

            agent_dir = DATA_DIR / "agents" / name
            if agent_dir.exists():
                import shutil
                shutil.rmtree(agent_dir)
            return True

    async def update_agent(self, name: str, updates: dict) -> Optional[Agent]:
        agent = self.agents.get(name)
        if not agent:
            logger.warning("Update requested for non-existent agent '%s'", name)
            return None

        changed_fields = list(updates.keys())
        logger.info("Updating agent '%s': fields=%s", name, changed_fields)

        if "systemPrompt" in updates:
            agent.change_system_prompt(updates["systemPrompt"])

        if "modelId" in updates:
            model_cfg = self.get_model(updates["modelId"])
            if model_cfg:
                model = Model.from_config_dict({
                    "provider": model_cfg.provider,
                    "model": model_cfg.modelName,
                    "api_key": model_cfg.apiKey,
                    "base_url": model_cfg.baseUrl,
                    "max_completion_tokens": model_cfg.maxCompletionTokens,
                    "max_context_tokens": model_cfg.maxContextTokens,
                    "temperature": model_cfg.temperature,
                    "top_p": model_cfg.topP,
                    "thinking": model_cfg.thinking,
                })
                agent.change_model(model)
                logger.info("Agent '%s': model changed to '%s'", name, updates["modelId"])
                self._agent_model_ids[name] = updates["modelId"]
                self._save_agent_model_id(name, updates["modelId"])
            else:
                logger.warning("Agent '%s': model '%s' not found, keeping current", name, updates["modelId"])

        if "policy" in updates:
            from BBagent.built_in_tool import TOOL_CREATOR
            from BBagent.built_in_tool.policy import Policy

            policy_raw = updates["policy"]
            if policy_raw:
                policy_snake = _policy_to_snake(policy_raw)
                if not policy_snake.get("cwd"):
                    policy_snake["cwd"] = str(agent.base_dir)
                agent.policy = policy_snake
                policy_obj = Policy(**policy_snake)
            else:
                policy_obj = None
            for tool_name, tool in list(agent.tools.items()):
                source = getattr(tool, 'source', None)
                if not source or source not in TOOL_CREATOR:
                    continue
                del agent.tools[tool_name]
                builder = TOOL_CREATOR[source]
                if asyncio.iscoroutinefunction(builder):
                    new_tool = await builder(policy_obj)
                else:
                    new_tool = builder(policy_obj)
                agent.tools[new_tool.name] = new_tool

        if "toolNames" in updates:
            policy_snake = getattr(agent, "policy", {}) or {}
            if not policy_snake and "policy" in updates:
                policy_snake = _policy_to_snake(updates["policy"])
            if policy_snake and not policy_snake.get("cwd"):
                policy_snake["cwd"] = str(agent.base_dir)

            builtin_metas = [
                {"source": tn, "config": {}}
                for tn in updates["toolNames"] if not tn.startswith("mcp:")
            ]
            mcp_metas = [
                {
                    "source": "mcp",
                    "config": {
                        "mcp_server_name": tn[4:],
                        "tool_name": tn[4:],
                    },
                }
                for tn in updates["toolNames"] if tn.startswith("mcp:")
            ]
            self._agent_tool_metas[name] = builtin_metas
            self._agent_mcp_metas[name] = mcp_metas
            self._agent_started.discard(name)

            existing_names = set(agent.tools.keys())
            new_tool_names = [n for n in updates["toolNames"] if n not in existing_names]
            if new_tool_names:
                logger.info("Agent '%s': adding tools %s", name, new_tool_names)
                new_tools, mcp_clients = await self._build_tools_and_mcp_clients(
                    new_tool_names, updates.get("policy"), default_cwd=str(agent.base_dir)
                )
                agent.add_tools(new_tools)
                if mcp_clients:
                    agent.register_mcp_clients(mcp_clients)

        if "skillNames" in updates:
            self._agent_skill_metas[name] = [{"name": sn, "path": ""} for sn in updates["skillNames"]]
            self._agent_started.discard(name)

            existing_names = set(agent.skills.keys())
            new_skill_names = [n for n in updates["skillNames"] if n not in existing_names]
            new_skills = [self.skills[n] for n in new_skill_names if n in self.skills]
            if new_skills:
                logger.info("Agent '%s': adding skills %s", name, [s.name for s in new_skills])
                agent.add_skills(new_skills)

        agent.save()
        logger.info("Agent '%s' updated successfully", name)
        return agent

    # ------------------------------------------------------------------
    # Agent model_id persistence
    # ------------------------------------------------------------------
    def _save_agent_model_id(self, name: str, model_id: str):
        agent = self.agents.get(name)
        if not agent:
            return
        config_path = agent.base_dir / "agent_config.yaml"
        if not config_path.exists():
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw = yaml.safe_load(f) or {}
            raw["model_id"] = model_id
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.warning("Failed to save model_id for agent '%s': %s", name, e)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def get_agent_state(self, name: str) -> dict:
        agent = self.agents.get(name)
        if not agent:
            return {"state": "unknown", "session_id": ""}
        raw_state = str(agent.state) if agent.state else "Ready"
        return {
            "state": raw_state.lower(),
            "session_id": agent.session.id if agent.session else "",
        }

    def get_agent_sessions(self, name: str) -> list[dict]:
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        session_dir = agent.session_dir
        if not session_dir.exists():
            return []

        sessions = []
        for sdir in sorted(session_dir.iterdir(), reverse=True):
            if not sdir.is_dir():
                continue
            jsonl = sdir / f"{sdir.name}.jsonl"
            if not jsonl.exists():
                continue
            timestamp = ""
            turn_count = 0
            md = sdir / f"{sdir.name}.md"
            if md.exists():
                try:
                    meta = self._parse_session_metadata(md)
                    timestamp = meta.get("timestamp", "")
                    turn_count = int(meta.get("turn_count", 0))
                except Exception:
                    pass
            sessions.append({
                "id": sdir.name,
                "timestamp": timestamp,
                "turnCount": turn_count,
                "isActive": agent.session.id == sdir.name,
            })
        return sessions

    @staticmethod
    def _parse_session_metadata(md_path) -> dict:
        text = md_path.read_text(encoding="utf-8")
        result = {}
        for line in text.split("\n"):
            stripped = line.strip()
            if ":" in stripped and not stripped.startswith("#") and not stripped.startswith("##"):
                key, _, value = stripped.partition(":")
                result[key.strip()] = value.strip()
        return result

    async def switch_agent_session(self, name: str, session_id: str):
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        session_path = agent.session_dir / session_id / f"{session_id}.jsonl"
        if not session_path.exists():
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, f"Session '{session_id}' not found")

        with log_operation(logger, "switch_session", agent_name=name):
            await agent.load_session(session_path)

    async def new_agent_session(self, name: str):
        agent = self.agents.get(name)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{name}' not found")

        with log_operation(logger, "new_session", agent_name=name):
            await agent.new_session()

    def get_agent_messages(self, name: str) -> list[dict]:
        agent = self.agents.get(name)
        if not agent or not agent.session:
            return []

        result = []
        for turn in agent.session.turns:
            for msg in turn.messages:
                msg_dict = msg.to_dict()
                ts = msg_dict.get("timestamp", 0)

                # thinking: emit as separate system entry BEFORE model text
                # (matches WS format: {type:"thinking", content:"..."})
                thinking = msg_dict.get("thinking", "")
                if thinking:
                    result.append({
                        "role": "system",
                        "content": thinking,
                        "chunkType": "thinking",
                        "source_agent": name,
                        "timestamp": ts,
                    })

                content = msg_dict.get("content", "")
                # Tool messages are handled separately below with chunkType.
                if msg_dict.get("role") == "tool":
                    pass
                elif isinstance(content, str):
                    if content.strip():
                        result.append({
                            "role": msg_dict.get("role", ""),
                            "content": content,
                            "source_agent": name,
                            "timestamp": ts,
                        })
                elif isinstance(content, list):
                    # Anthropic-style content blocks — emit one entry per block
                    for block in content:
                        bt = block.get("type", "")
                        if bt == "text":
                            text = block.get("text", "")
                            if text.strip():
                                result.append({
                                    "role": msg_dict.get("role", ""),
                                    "content": text,
                                    "source_agent": name,
                                    "timestamp": ts,
                                })
                        elif bt in ("tool_use", "tooluse"):
                            tool_input = block.get("input", {})
                            result.append({
                                "role": "system",
                                "chunkType": "tool_use",
                                "toolName": block.get("name", ""),
                                "toolInput": tool_input,
                                "content": json.dumps(
                                    tool_input, indent=2, ensure_ascii=False,
                                ),
                                "source_agent": name,
                                "timestamp": ts,
                            })

                # Tool calls stored in ModelMessage.tool_calls (separate from content)
                for tc in msg_dict.get("tool_calls", []):
                    tc_input = tc.get("input", {})
                    result.append({
                        "role": "system",
                        "chunkType": "tool_use",
                        "toolName": tc.get("name", ""),
                        "toolInput": tc_input,
                        "content": json.dumps(
                            tc_input, indent=2, ensure_ascii=False,
                        ),
                        "source_agent": name,
                        "timestamp": ts,
                    })

                # Tool result messages (role == "tool")
                if msg_dict.get("role") == "tool":
                    result.append({
                        "role": "system",
                        "chunkType": "tool_result",
                        "toolName": msg_dict.get("name", ""),
                        "content": (
                            f"[{msg_dict.get('name', '')}]\n"
                            f"{str(msg_dict.get('content', ''))[:500]}"
                        ),
                        "source_agent": name,
                        "timestamp": ts,
                    })

        return result

    def get_agent_dispatcher(self, name: str) -> AgentOutputDispatcher | None:
        return self._agent_dispatchers.get(name)

    # ------------------------------------------------------------------
    # Team CRUD
    # ------------------------------------------------------------------
    def get_team_config(self, name: str) -> Optional[TeamConfig]:
        team = self.teams.get(name)
        if not team:
            return None
        return TeamConfig(
            name=team.name,
            teamDescription=team.team_description,
            agentNames=list(team.agents.keys()),
            contacts={k: list(v) for k, v in team._contacts.items()},
        )

    def create_team(self, config: TeamConfig) -> AgentTeam:
        agents = {}
        for agent_name in config.agentNames:
            agent = self.agents.get(agent_name)
            if agent:
                agents[agent_name] = agent

        contacts = {}
        for agent_name, contact_list in config.contacts.items():
            contacts[agent_name] = {c: "" for c in contact_list}

        core_config = CoreTeamConfig(
            name=config.name,
            team_description=config.teamDescription,
            agents=agents,
            contacts=contacts,
        )
        team = AgentTeam.create(core_config)
        team.save(DATA_DIR / "teams" / config.name)
        self.teams[config.name] = team
        return team

    def update_team(self, name: str, updates: dict) -> Optional[AgentTeam]:
        team = self.teams.get(name)
        if not team:
            return None
        if "teamDescription" in updates:
            team.team_description = updates["teamDescription"]
        team.save(DATA_DIR / "teams" / name)
        return team

    def delete_team(self, name: str) -> bool:
        if name in self.teams:
            del self.teams[name]
            team_dir = DATA_DIR / "teams" / name
            if team_dir.exists():
                import shutil
                shutil.rmtree(team_dir)
            return True
        return False

    # ------------------------------------------------------------------
    # MCP discover & per-Agent client creation
    # ------------------------------------------------------------------
    async def _discover_mcp_tools(self, name: str) -> list:
        mcp_cfg = self.get_mcp(name)
        if not mcp_cfg:
            raise ValueError(f"MCP server '{name}' not found")

        core_cfg = CoreMCPServerConfig(
            name=mcp_cfg.name,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
        )
        client = MCPClient(core_cfg)
        try:
            await client.start()
            await client.initialize()
            tools_data = await client.list_tools()
        finally:
            await client.close()

        from backend.schemas import ToolConfig
        tool_configs = [
            ToolConfig(
                id=f"{name}.{t['name']}",
                name=t["name"],
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {}),
                isMcp=True,
                mcpServerName=name,
            )
            for t in tools_data
        ]
        mcp_cfg.tools = tool_configs
        self._save_mcp_file(mcp_cfg)
        logger.info(f"Discovered {len(tool_configs)} tool(s) from MCP server '{name}'")
        return tool_configs

    async def _create_mcp_client_for_agent(self, server_name: str) -> tuple:
        mcp_cfg = self.get_mcp(server_name)
        if not mcp_cfg:
            raise ValueError(f"MCP server '{server_name}' not found")

        core_cfg = CoreMCPServerConfig(
            name=mcp_cfg.name,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
        )
        client = MCPClient(core_cfg)
        await client.start()
        await client.initialize()
        tools = await client.create_tools()
        return tools, client

    async def _build_tools_and_mcp_clients(
        self, tool_names: list[str], policy: dict = None, default_cwd: str = None
    ) -> tuple:
        from BBagent.built_in_tool import TOOL_CREATOR
        from BBagent.built_in_tool.policy import Policy

        tools = []
        mcp_clients = {}

        if not tool_names:
            return tools, mcp_clients

        if policy:
            policy_snake = _policy_to_snake(policy)
            if not policy_snake.get("cwd") and default_cwd:
                policy_snake["cwd"] = default_cwd
            policy_obj = Policy(**policy_snake)
        else:
            policy_obj = None

        for name in tool_names:
            if name.startswith("mcp:"):
                mcp_name = name[4:]
                try:
                    mcp_tools, client = await self._create_mcp_client_for_agent(mcp_name)
                    tools.extend(mcp_tools)
                    mcp_clients[mcp_name] = client
                except Exception as e:
                    logger.warning(f"Failed to connect MCP '{mcp_name}' for agent: {e}")
            elif name in TOOL_CREATOR:
                builder = TOOL_CREATOR[name]
                if asyncio.iscoroutinefunction(builder):
                    tool = await builder(policy_obj)
                else:
                    tool = builder(policy_obj)
                tools.append(tool)
            elif f"built_in.{name}" in TOOL_CREATOR:
                builder = TOOL_CREATOR[f"built_in.{name}"]
                if asyncio.iscoroutinefunction(builder):
                    tool = await builder(policy_obj)
                else:
                    tool = builder(policy_obj)
                tools.append(tool)
            else:
                logger.warning(f"Unknown tool source '{name}', skipping")

        return tools, mcp_clients


# 全局单例
state_manager = StateManager()
