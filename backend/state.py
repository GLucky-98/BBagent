import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from BBagent.core.agent import Agent, AgentConfig as CoreAgentConfig
from BBagent.core.team import AgentTeam, TeamConfig as CoreTeamConfig
from BBagent.core.model import Model
from BBagent.core.skill import Skill, scan_skills
from BBagent.core.mcp import MCPClient, MCPTool, MCPServerConfig as CoreMCPServerConfig

from backend.schemas import (
    ModelConfig,
    MCPServerConfig,
    PromptConfig,
    SkillConfig,
    AgentConfig,
    TeamConfig,
    UIState,
)

logger = logging.getLogger("bbagent.state")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

IMPORTED_SKILLS_DIRS_FILE = DATA_DIR / "imported_skills_dirs.json"


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
        self.imported_skills_dirs: List[str] = []
        self.agents: Dict[str, Agent] = {}
        self.teams: Dict[str, AgentTeam] = {}
        self.ui_state: UIState = UIState()

        self._mcp_clients: Dict[str, MCPClient] = {}
        self._mcp_tools: Dict[str, List[MCPTool]] = {}
        self._ensure_data_dir()
        self.load_all()

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

    def _models_path(self) -> Path:
        return DATA_DIR / "models" / "models.json"

    def _mcps_path(self) -> Path:
        return DATA_DIR / "mcps" / "servers.json"

    def _prompts_path(self) -> Path:
        return DATA_DIR / "prompts" / "prompts.json"

    def _store_path(self) -> Path:
        return DATA_DIR / "store.json"

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load_all(self):
        self._load_models()
        self._load_mcps()
        self._load_prompts()
        self._load_skills()
        self._load_agents()
        self._load_teams()
        self._load_ui_state()
        logger.info("StateManager loaded all data")

    def _load_models(self):
        path = self._models_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.models = [ModelConfig(**m) for m in data]
            except Exception as e:
                logger.warning(f"Failed to load models: {e}")
                self.models = []
        else:
            self.models = []

    def _load_mcps(self):
        path = self._mcps_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.mcp_servers = [MCPServerConfig(**m) for m in data]
            except Exception as e:
                logger.warning(f"Failed to load mcps: {e}")
                self.mcp_servers = []
        else:
            self.mcp_servers = []

    def _load_prompts(self):
        path = self._prompts_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.prompts = [PromptConfig(**p) for p in data]
            except Exception as e:
                logger.warning(f"Failed to load prompts: {e}")
                self.prompts = []
        else:
            self.prompts = []

    def _load_skills(self):
        skills_dir = PROJECT_ROOT / "skills"
        if skills_dir.exists():
            try:
                self.skills = scan_skills(skills_dir)
            except Exception as e:
                logger.warning(f"Failed to load skills: {e}")
                self.skills = {}
        else:
            self.skills = {}
        self._load_imported_skills_dirs()

    def _load_agents(self):
        agents_dir = DATA_DIR / "agents"
        if not agents_dir.exists():
            return
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            config_path = agent_dir / "agent_config.yaml"
            if not config_path.exists():
                continue
            try:
                agent = Agent.load(agent_dir)
                self.agents[agent.name] = agent
            except Exception as e:
                logger.warning(f"Failed to load agent from {agent_dir}: {e}")

    def _load_teams(self):
        teams_dir = DATA_DIR / "teams"
        if not teams_dir.exists():
            return
        for team_dir in teams_dir.iterdir():
            if not team_dir.is_dir():
                continue
            config_path = team_dir / "team_config.yaml"
            if not config_path.exists():
                continue
            try:
                team = AgentTeam.load(team_dir)
                self.teams[team.name] = team
            except Exception as e:
                logger.warning(f"Failed to load team from {team_dir}: {e}")

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
    def save_models(self):
        path = self._models_path()
        data = [m.model_dump(mode="json") for m in self.models]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_mcps(self):
        path = self._mcps_path()
        data = [m.model_dump(mode="json") for m in self.mcp_servers]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_prompts(self):
        path = self._prompts_path()
        data = [p.model_dump(mode="json") for p in self.prompts]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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
        self.save_models()
        return config

    def update_model(self, model_id: str, updates: dict) -> Optional[ModelConfig]:
        for i, m in enumerate(self.models):
            if m.id == model_id:
                data = m.model_dump()
                data.update(updates)
                self.models[i] = ModelConfig(**data)
                self.save_models()
                return self.models[i]
        return None

    def delete_model(self, model_id: str) -> bool:
        for i, m in enumerate(self.models):
            if m.id == model_id:
                self.models.pop(i)
                self.save_models()
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

    def add_mcp(self, config: MCPServerConfig) -> MCPServerConfig:
        self.mcp_servers.append(config)
        self.save_mcps()
        return config

    def update_mcp(self, name: str, updates: dict) -> Optional[MCPServerConfig]:
        for i, m in enumerate(self.mcp_servers):
            if m.name == name:
                data = m.model_dump()
                data.update(updates)
                self.mcp_servers[i] = MCPServerConfig(**data)
                self.save_mcps()
                return self.mcp_servers[i]
        return None

    def delete_mcp(self, name: str) -> bool:
        for i, m in enumerate(self.mcp_servers):
            if m.name == name:
                self.mcp_servers.pop(i)
                self.save_mcps()
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
        self.save_prompts()
        return config

    def update_prompt(self, prompt_id: str, updates: dict) -> Optional[PromptConfig]:
        for i, p in enumerate(self.prompts):
            if p.id == prompt_id:
                data = p.model_dump()
                data.update(updates)
                self.prompts[i] = PromptConfig(**data)
                self.save_prompts()
                return self.prompts[i]
        return None

    def delete_prompt(self, prompt_id: str) -> bool:
        for i, p in enumerate(self.prompts):
            if p.id == prompt_id:
                self.prompts.pop(i)
                self.save_prompts()
                return True
        return False

    # ------------------------------------------------------------------
    # Skill
    # ------------------------------------------------------------------
    def list_skills(self) -> List[SkillConfig]:
        result = []
        default_path = str((PROJECT_ROOT / "skills").resolve())
        for skill in self.skills.values():
            skill_path = str(skill.path.resolve()) if skill.path else ""
            source = "default" if skill_path.startswith(default_path) else "imported"
            result.append(
                SkillConfig(
                    name=skill.name,
                    description=skill.description,
                    path=skill_path,
                    body=skill.body,
                    metadata=skill.metadata.to_dict() if skill.metadata else {},
                    source=source,
                )
            )
        return result

    def _load_imported_skills_dirs(self):
        if IMPORTED_SKILLS_DIRS_FILE.exists():
            try:
                dirs = json.loads(IMPORTED_SKILLS_DIRS_FILE.read_text(encoding="utf-8"))
                for d in dirs:
                    try:
                        imported_skills = scan_skills(Path(d))
                        for name, skill in imported_skills.items():
                            if name not in self.skills:
                                self.skills[name] = skill
                    except Exception as e:
                        logger.warning(f"Failed to load imported skills from {d}: {e}")
                self.imported_skills_dirs = dirs
            except Exception as e:
                logger.warning(f"Failed to load imported skills dirs: {e}")
                self.imported_skills_dirs = []

    def save_imported_skills_dirs(self, dir_path: Path):
        path_str = str(dir_path.resolve())
        if path_str not in self.imported_skills_dirs:
            self.imported_skills_dirs.append(path_str)
        IMPORTED_SKILLS_DIRS_FILE.write_text(
            json.dumps(self.imported_skills_dirs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Agent CRUD
    # ------------------------------------------------------------------
    def get_agent_config(self, name: str) -> Optional[AgentConfig]:
        agent = self.agents.get(name)
        if not agent:
            return None
        return AgentConfig(
            name=agent.name,
            modelId=agent.model.to_config_dict().get("provider", ""),
            systemPrompt=agent.system_prompt,
            toolNames=list(agent.tools.keys()),
            skillNames=list(agent.skills.keys()),
            hookEnabled=bool(agent.hook and agent.hook._enabled),
            basePath=str(agent.base_dir),
            workingDir=getattr(agent, "working_dir", ""),
            policy=getattr(agent, "policy", {}) or {},
        )

    def create_agent(self, config: AgentConfig) -> Agent:
        model_cfg = self.get_model(config.modelId)
        if not model_cfg:
            raise ValueError(f"Model not found: {config.modelId}")

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

        tools = []
        if config.toolNames:
            tools = []

        skills = []
        for skill_name in config.skillNames:
            skill = self.skills.get(skill_name)
            if skill:
                skills.append(skill)

        core_kwargs = {
            "model": model,
            "base_dir": DATA_DIR / "agents",
            "system_prompt": config.systemPrompt,
            "tools": tools,
            "skills": skills,
        }
        if config.name and config.name.strip():
            core_kwargs["name"] = config.name.strip()
        core_config = CoreAgentConfig(**core_kwargs)
        agent = Agent(core_config)
        agent.save()
        self.agents[agent.name] = agent
        return agent

    def update_agent(self, name: str, updates: dict) -> Optional[Agent]:
        agent = self.agents.get(name)
        if not agent:
            return None
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
        agent.save()
        return agent

    def delete_agent(self, name: str) -> bool:
        if name in self.agents:
            del self.agents[name]
            agent_dir = DATA_DIR / "agents" / name
            if agent_dir.exists():
                import shutil
                shutil.rmtree(agent_dir)
            return True
        return False

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
    # MCP 连接管理
    # ------------------------------------------------------------------
    def _get_mcp_core_config(self, name: str) -> Optional[CoreMCPServerConfig]:
        cfg = self.get_mcp(name)
        if not cfg:
            return None
        return CoreMCPServerConfig(
            name=cfg.name,
            command=cfg.command,
            args=cfg.args,
            env=cfg.env,
        )

    async def activate_mcp(self, name: str) -> List[MCPTool]:
        if name in self._mcp_clients and self._mcp_clients[name].state == 'active':
            return self._mcp_tools.get(name, [])

        core_cfg = self._get_mcp_core_config(name)
        if not core_cfg:
            raise ValueError(f"MCP server '{name}' not found")

        client = MCPClient(core_cfg)
        await client.start()
        await client.initialize()
        tools = await client.create_tools()
        self._mcp_clients[name] = client
        self._mcp_tools[name] = tools
        logger.info(f"Activated MCP client: {name} ({len(tools)} tool(s))")
        return tools

    async def deactivate_mcp(self, name: str) -> List[MCPTool]:
        client = self._mcp_clients.pop(name, None)
        if client:
            await client.close()
            tools = self._mcp_tools.pop(name, [])
            logger.info(f"Deactivated MCP client: {name}")
            return tools
        return []


# 全局单例
state_manager = StateManager()
