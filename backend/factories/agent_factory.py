"""AgentFactory — manages Agent CRUD, lifecycle, and per-agent runtime state.

Holds all per-agent in-memory state: dispatchers, tasks, tool instances,
MCP clients, hook configs, etc. Delegates model management to ModelFactory
and tool config lookups to ToolFactory.

Design decisions:
  - agent.policy is stored as camelCase dict (same as frontend/JSON).
    Conversion to snake_case only happens when constructing Policy objects.
  - Per-agent config is stored in _agent_configs (AgentConfig), eliminating
    redundant _tool_metas / _mcp_metas / _skill_metas intermediate layers.
  - Hook state stored as _hook_names + _shared_hook_config, eliminating
    _hook_metas intermediate layer.
  - _load_one / create use "commit on success" pattern: data is collected
    into local variables first, only written to caches after Agent is built.
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from BBagent.core.agent import Agent, AgentConfig as CoreAgentConfig
from BBagent.core.message import Session
from BBagent.core.mcp import MCPClient
from BBagent.core.tool import Tool
from BBagent.built_in_tool import TOOL_CREATOR
from BBagent.built_in_tool.policy import Policy
from BBagent.built_in_hook import HOOK_CREATOR, BuiltinHookConfig

from backend.schemas import AgentConfig, TimerConfig
from backend.dispatcher import AgentOutputDispatcher
from backend.errors import NotFoundError, ErrorCode, AppError
from backend.logging import get_backend_logger, log_operation
from backend.factories import _next_id

# camelCase -> snake_case for tool policy
# Used only when constructing Policy objects from camelCase dicts.
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


logger = get_backend_logger("state.agent_factory")


class AgentFactory:
    def __init__(self, data_dir: Path, model_factory, tool_factory, skill_factory, mcp_factory):
        self._data_dir = data_dir
        self._model_factory = model_factory
        self._tool_factory = tool_factory
        self._skill_factory = skill_factory
        self._mcp_factory = mcp_factory

        # Core agent instances
        self.agents: dict[str, Agent] = {}

        # Per-agent config (canonical source for toolIds, skillIds, etc.)
        self._agent_configs: dict[str, AgentConfig] = {}

        # Per-agent runtime state
        self._dispatchers: dict[str, AgentOutputDispatcher] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._model_ids: dict[str, str] = {}           # agent_id -> model_id
        self._started: set[str] = set()
        self._persisted_started: dict[str, bool] = {}

        # Per-agent hook state
        self._hook_names: dict[str, list[str]] = {}
        self._shared_hook_config: dict[str, BuiltinHookConfig] = {}

        # Per-agent runtime pools
        self._tool_instances: dict[str, dict[str, Tool]] = {}     # agent_id -> {tid: Tool}
        self._mcp_clients: dict[str, dict[str, MCPClient]] = {}  # agent_id -> {mcp_id: MCPClient}

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load(self):
        agents_dir = self._data_dir / "agents"
        if not agents_dir.exists():
            return

        # Look for JSON config files in agent subdirectories.
        # Agent.__post_init__ creates a name subdirectory under the UUID dir,
        # so config may be at UUID/name/agent_config.json (one level deeper).
        dirs = []
        for d in sorted(agents_dir.iterdir()):
            if not d.is_dir():
                continue
            config_path = d / "agent_config.json"
            if config_path.exists():
                dirs.append((d, config_path))
            else:
                for sd in sorted(d.iterdir()):
                    if not sd.is_dir():
                        continue
                    config_path = sd / "agent_config.json"
                    if config_path.exists():
                        dirs.append((sd, config_path))
                        break
        if not dirs:
            return

        results = await asyncio.gather(
            *[self._load_one(agent_dir, config_path)
              for agent_dir, config_path in dirs],
            return_exceptions=True,
        )
        loaded, failed = 0, 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                logger.error("Failed to load agent from '%s': %s",
                             dirs[i][0].name, result, exc_info=True)
            else:
                loaded += 1
        logger.info("Agent loading: %d loaded, %d failed", loaded, failed)

    async def _load_one(self, agent_dir: Path, config_path: Path | None = None):
        if config_path is None:
            config_path = agent_dir / "agent_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = json.loads(f.read()) or {}

        agent_id: str = config_dict["id"]
        name = config_dict.get("name", agent_dir.name)

        model_id = config_dict.get("modelId", "")
        if not model_id:
            raise ValueError(f"Agent '{name}' has no modelId")

        # Parse tool/skill/hook info
        tool_ids = config_dict.get("toolIds") or config_dict.get("toolNames") or []
        skill_ids = config_dict.get("skillIds") or config_dict.get("skillNames") or []
        hook_names = config_dict.get("hookNames") or []
        hook_config = config_dict.get("hookConfig") or {}
        timers_raw = config_dict.get("timers") or []
        timers = [TimerConfig(**t) for t in timers_raw]

        # Build policy (camelCase, same as JSON)
        policy = dict(config_dict.get("toolPolicy") or {})
        policy["cwd"] = policy.get("cwd") or (config_dict.get("workingDir") or "").strip() or str(agent_dir)

        # Resolve model instance (may raise — no caches written yet, nothing to clean up)
        try:
            model = self._model_factory.acquire(model_id)
        except NotFoundError:
            raise ValueError(f"Agent '{name}' references unknown modelId '{model_id}'")

        # Build core Agent (may raise — still no caches written)
        core_config = CoreAgentConfig(
            model=model,
            base_dir=agent_dir,
            system_prompt=config_dict.get("systemPrompt", ""),
            name=name,
        )
        agent = Agent(core_config)
        agent.policy = policy

        # Restore session: prefer lastSessionId, otherwise create new
        last_session_id = config_dict.get("lastSessionId")
        restored = False
        if last_session_id:
            session_jsonl = agent.session_dir / last_session_id / f"{last_session_id}.jsonl"
            if session_jsonl.exists():
                try:
                    agent.session = Session.load(last_session_id, agent.session_dir / last_session_id)
                    restored = True
                    logger.info("Restored last session '%s' for agent '%s'", last_session_id, name)
                except Exception as e:
                    logger.warning("Failed to restore session '%s' for agent '%s': %s", last_session_id, name, e)
        if not restored:
            agent.session = Session.create(agent.session_dir)

        # Build hook config (may raise — still no caches written)
        shared_hook_cfg = self._build_shared_hook_config(hook_config)

        # All succeeded — commit to caches
        self.agents[agent_id] = agent
        agent.logger.set_console_level(logging.CRITICAL + 1)
        self._dispatchers[agent_id] = AgentOutputDispatcher()
        self._model_ids[agent_id] = model_id
        self._persisted_started[agent_id] = bool(config_dict.get("started", False))
        self._hook_names[agent_id] = hook_names
        self._shared_hook_config[agent_id] = shared_hook_cfg
        self._agent_configs[agent_id] = AgentConfig(
            id=agent_id,
            name=name,
            modelId=model_id,
            systemPrompt=config_dict.get("systemPrompt", ""),
            workingDir=policy.get("cwd", ""),
            basePath=str(agent_dir),
            toolIds=list(tool_ids),
            skillIds=list(skill_ids),
            toolPolicy=dict(policy),
            hookNames=list(hook_names),
            hookConfig=dict(hook_config),
            timers=timers,
        )
        logger.info("Loaded agent '%s' (id=%s)", name, agent_id)

    # ------------------------------------------------------------------
    # Agent config (API-facing)
    # ------------------------------------------------------------------

    def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        cfg = self._agent_configs.get(agent_id)
        if not cfg:
            return None

        # Only supplement runtime-only field; config is already up-to-date
        agent = self.agents.get(agent_id)
        cfg.lastSessionId = agent.session.id if agent and getattr(agent, "session", None) else ""
        return cfg

    # ------------------------------------------------------------------
    # Create / Delete / Update
    # ------------------------------------------------------------------

    async def create(self, config: AgentConfig) -> Agent:
        with log_operation(logger, "create_agent", agent_name=config.name):
            try:
                model = self._model_factory.acquire(config.modelId)
            except NotFoundError:
                raise NotFoundError(
                    ErrorCode.MODEL_NOT_FOUND,
                    f"创建 Agent '{config.name}' 失败：模型 '{config.modelId}' 不存在",
                )

            agent: Agent | None = None
            agent_dir_to_cleanup: Path | None = None
            agent_id = config.id or _next_id()
            id_subdir = self._data_dir / "agents" / agent_id

            try:
                shared_hook_config = self._build_shared_hook_config(config.hookConfig)

                core_kwargs = {
                    "model": model,
                    "base_dir": id_subdir,
                    "system_prompt": config.systemPrompt,
                }
                if config.name and config.name.strip():
                    core_kwargs["name"] = config.name.strip()
                core_config = CoreAgentConfig(**core_kwargs)
                agent = Agent(core_config)
                agent_dir_to_cleanup = agent.base_dir

                # Build policy (camelCase)
                policy = dict(config.toolPolicy) if config.toolPolicy else {}
                policy["cwd"] = policy.get("cwd") or (config.workingDir or "").strip() or str(agent.base_dir)
                agent.policy = policy

                config.id = agent_id

                # All succeeded — commit to caches
                self.agents[agent_id] = agent
                agent.logger.set_console_level(logging.CRITICAL + 1)
                self._dispatchers[agent_id] = AgentOutputDispatcher()
                self._model_ids[agent_id] = config.modelId
                self._hook_names[agent_id] = list(config.hookNames)
                self._shared_hook_config[agent_id] = shared_hook_config
                self._agent_configs[agent_id] = AgentConfig(
                    id=agent_id,
                    name=config.name,
                    modelId=config.modelId,
                    systemPrompt=config.systemPrompt,
                    workingDir=policy.get("cwd", ""),
                    basePath=str(agent.base_dir),
                    toolIds=list(config.toolIds),
                    skillIds=list(config.skillIds),
                    toolPolicy=dict(policy),
                    hookNames=list(config.hookNames),
                    hookConfig=dict(config.hookConfig or {}),
                    timers=list(config.timers),
                )

                self._write_agent_json_full(agent_id, started=False)
                return agent

            except Exception:
                self.agents.pop(agent_id, None)
                self._agent_configs.pop(agent_id, None)
                self._hook_names.pop(agent_id, None)
                self._shared_hook_config.pop(agent_id, None)
                self._model_ids.pop(agent_id, None)
                self._dispatchers.pop(agent_id, None)
                if agent_dir_to_cleanup and agent_dir_to_cleanup.exists():
                    shutil.rmtree(agent_dir_to_cleanup, ignore_errors=True)
                    if id_subdir.exists() and not any(id_subdir.iterdir()):
                        try:
                            id_subdir.rmdir()
                        except Exception:
                            pass
                await self._model_factory.release(config.modelId)
                raise

    async def delete(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")

        with log_operation(logger, "delete_agent", agent_name=agent.name):
            try:
                await self.stop(agent_id)
            except Exception as e:
                logger.warning("Error stopping agent '%s' before delete: %s", agent.name, e)

            task = self._tasks.pop(agent_id, None)
            if task and not task.done():
                task.cancel()

            try:
                await self._close_runtime(agent_id)
            except Exception as e:
                logger.warning(f"Error closing runtime for agent '{agent.name}': {e}")

            base_dir: Path | None = getattr(agent, "base_dir", None)
            del self.agents[agent_id]
            self._dispatchers.pop(agent_id, None)
            self._started.discard(agent_id)
            self._agent_configs.pop(agent_id, None)
            self._hook_names.pop(agent_id, None)
            self._shared_hook_config.pop(agent_id, None)
            old_model_id = self._model_ids.pop(agent_id, None)
            if old_model_id:
                await self._model_factory.release(old_model_id)

            if base_dir is not None:
                bp = Path(str(base_dir)).expanduser().resolve()
                if bp.exists():
                    shutil.rmtree(bp)
                parent = bp.parent
                if (parent.exists()
                        and parent.parent == self._data_dir / "agents"
                        and parent != self._data_dir / "agents"
                        and not any(parent.iterdir())):
                    try:
                        parent.rmdir()
                    except Exception:
                        pass
            return True

    def _diff_updates(self, agent_id: str, updates: dict) -> dict:
        """Filter out fields whose values are identical to the stored config."""
        cfg = self._agent_configs.get(agent_id)
        if cfg is None:
            return updates

        scalar_fields = ("name", "modelId", "systemPrompt", "workingDir", "type")
        list_fields = ("toolIds", "skillIds", "hookNames")

        filtered = {}
        for k, v in updates.items():
            if k in scalar_fields:
                if v != getattr(cfg, k, None):
                    filtered[k] = v
            elif k in list_fields:
                stored = getattr(cfg, k, None) or []
                if sorted(v) != sorted(stored):
                    filtered[k] = v
            elif k == "toolPolicy":
                stored = getattr(cfg, k, None) or {}
                if v != stored:
                    filtered[k] = v
            elif k == "hookConfig":
                stored = getattr(cfg, k, None) or {}
                if v != stored:
                    filtered[k] = v
            else:
                filtered[k] = v
        return filtered

    async def update(self, agent_id: str, updates: dict) -> Optional[Agent]:
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        # Diff: skip fields whose value hasn't changed
        updates = self._diff_updates(agent_id, updates)
        if not updates:
            logger.info("Updating agent '%s': no changes detected, skipping", agent.name)
            return agent

        changed_fields = list(updates.keys())
        logger.info("Updating agent '%s': fields=%s", agent.name, changed_fields)

        cfg = self._agent_configs.get(agent_id)

        # Tool policy (camelCase internally)
        policy_changed = "toolPolicy" in updates or "workingDir" in updates
        if policy_changed:
            current_policy = dict(getattr(agent, "policy", {}) or {})
            if "toolPolicy" in updates and updates["toolPolicy"]:
                current_policy.update(updates["toolPolicy"])
            if "workingDir" in updates:
                current_policy["cwd"] = (updates["workingDir"] or "").strip() or current_policy.get("cwd") or str(agent.base_dir)
            agent.policy = current_policy
            if cfg:
                cfg.toolPolicy = dict(current_policy)
                cfg.workingDir = current_policy.get("cwd", "")
            policy_obj = Policy(**_policy_to_snake(current_policy))
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

        if "systemPrompt" in updates:
            agent.change_system_prompt(updates["systemPrompt"])
            if cfg:
                cfg.systemPrompt = updates["systemPrompt"]

        if "name" in updates:
            agent.name = updates["name"]
            if cfg:
                cfg.name = updates["name"]

        if "modelId" in updates:
            new_model_id = updates["modelId"]
            old_model_id = self._model_ids.get(agent_id, "")
            if new_model_id != old_model_id:
                try:
                    new_model = self._model_factory.acquire(new_model_id)
                except NotFoundError:
                    logger.warning("Agent '%s': model '%s' not found", agent.name, new_model_id)
                    new_model = None
                if new_model is not None:
                    agent.change_model(new_model)
                    self._model_ids[agent_id] = new_model_id
                    if old_model_id and old_model_id != new_model_id:
                        await self._model_factory.release(old_model_id)

        # toolIds
        if "toolIds" in updates:
            new_tool_ids = list(updates["toolIds"])
            if cfg:
                cfg.toolIds = new_tool_ids

            current_pool = self._tool_instances.setdefault(agent_id, {})
            added = [tid for tid in new_tool_ids if tid not in current_pool]
            removed_tids = [tid for tid in list(current_pool.keys()) if tid not in new_tool_ids]

            policy_for_build = dict(getattr(agent, "policy", {}) or {})
            policy_for_build.setdefault("cwd", str(agent.base_dir))
            policy_obj = Policy(**_policy_to_snake(policy_for_build))

            for tid in added:
                try:
                    tool = await self._build_tool(agent_id, tid, policy_obj)
                    agent.add_tools([tool])
                except Exception as e:
                    logger.warning(f"Agent '{agent.name}': failed to add tool '{tid}': {e}")

            removed_names = [current_pool.pop(tid).name for tid in removed_tids if tid in current_pool]
            if removed_names:
                try:
                    agent.remove_tools(removed_names)
                except Exception as e:
                    logger.warning(f"Agent '{agent.name}': failed to remove tools: {e}")

            # Close MCP clients whose tools have all been removed
            if removed_tids:
                removed_mcp_servers: set[str] = set()
                for tid in removed_tids:
                    tpl = self._tool_factory.get(tid)
                    if tpl and tpl.mcpServerId:
                        removed_mcp_servers.add(tpl.mcpServerId)
                if removed_mcp_servers:
                    remaining_server_ids: set[str] = set()
                    for tid in current_pool:
                        tpl = self._tool_factory.get(tid)
                        if tpl and tpl.mcpServerId:
                            remaining_server_ids.add(tpl.mcpServerId)
                    idle_servers = removed_mcp_servers - remaining_server_ids
                    if idle_servers:
                        mcp_bucket = self._mcp_clients.get(agent_id, {})
                        for server_id in idle_servers:
                            client = mcp_bucket.pop(server_id, None)
                            if client:
                                try:
                                    await client.close()
                                except Exception as e:
                                    logger.warning(
                                        "Failed to close MCP client for server '%s' after tool removal: %s",
                                        server_id, e,
                                    )

        # skillIds
        if "skillIds" in updates:
            new_skill_ids = list(updates["skillIds"])
            if cfg:
                cfg.skillIds = new_skill_ids

            # Determine added and removed skills
            new_skill_map = {}
            for sid in new_skill_ids:
                inst = self._skill_factory.get_instance(sid)
                if inst is not None:
                    new_skill_map[inst.name] = inst

            existing_names = set(agent.skills.keys())
            target_names = set(new_skill_map.keys())

            added_skills = [s for name, s in new_skill_map.items() if name not in existing_names]
            removed_names = list(existing_names - target_names)

            if added_skills:
                logger.info("Agent '%s': adding skills %s", agent.name, [s.name for s in added_skills])
                agent.add_skills(added_skills)
            if removed_names:
                logger.info("Agent '%s': removing skills %s", agent.name, removed_names)
                agent.remove_skills(removed_names)

        # Hooks
        if "hookNames" in updates or "hookConfig" in updates:
            agent.hook.clear()
            new_hook_cfg_dict = dict(updates.get("hookConfig") or {})
            new_hook_names = updates.get("hookNames")
            if new_hook_names is None:
                new_hook_names = list(self._hook_names.get(agent_id, []))
            shared_hook_cfg = self._build_shared_hook_config(new_hook_cfg_dict)
            self._shared_hook_config[agent_id] = shared_hook_cfg
            self._hook_names[agent_id] = list(new_hook_names)
            if cfg:
                cfg.hookNames = list(new_hook_names)
                cfg.hookConfig = new_hook_cfg_dict
            for src in new_hook_names:
                if src in HOOK_CREATOR:
                    HOOK_CREATOR[src](agent, shared_hook_cfg)
            agent.hook.set_context(agent)

        # Persist config changes to disk
        self._write_agent_json_full(agent_id, started=agent_id in self._started)

        return agent

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    async def start(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")

        if agent._running:
            logger.info("Agent '%s' already running, skipped", agent.name)
            return

        # Ghost-tool validation
        missing = self._collect_missing_tool_ids(agent_id)
        if missing:
            raise AppError(
                code=ErrorCode.TOOLCONFIG_NOT_FOUND,
                message=(
                    f"Agent '{agent.name}' references {len(missing)} "
                    f"unknown tool template(s); call update to remove them"
                ),
                status_code=400,
                detail={"missingTemplateIds": missing},
            )

        if agent_id not in self._started:
            await self._lazy_init(agent_id)
            self._started.add(agent_id)

        dispatcher = self._dispatchers.get(agent_id)
        if not dispatcher:
            dispatcher = AgentOutputDispatcher()
            self._dispatchers[agent_id] = dispatcher

        # Wrap output callback: per-agent dispatcher + global dispatcher for agent_state.
        # Global dispatcher allows all chat WS clients to receive state updates
        # for every agent, regardless of which agent they are currently viewing.
        global_disp = getattr(self, 'global_dispatcher', None)
        team_factory = getattr(self, 'team_factory', None)

        async def _wrapped_output(chunk):
            await dispatcher.on_chunk(chunk)
            if global_disp and chunk.get("type") == "agent_state":
                await global_disp.on_chunk({**chunk, "agent_id": agent_id})
                # Update team state when a member agent's state changes
                if team_factory:
                    for tid, team in team_factory.teams.items():
                        if agent.name in team.agents:
                            old_state = str(team.state).lower()
                            team.update_state()
                            new_state = str(team.state).lower()
                            if new_state != old_state:
                                await global_disp.on_chunk({
                                    "type": "agent_state",
                                    "agent_id": tid,
                                    "state": new_state,
                                })

        agent.on_output(_wrapped_output)

        async def _run():
            try:
                await agent.start()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("Agent '%s' event loop crashed: %s", agent.name, e, exc_info=True)

        with log_operation(logger, "start_agent", agent_name=agent.name):
            task = asyncio.create_task(_run())
            self._tasks[agent_id] = task

            # Register enabled timers
            cfg = self._agent_configs.get(agent_id)
            if cfg:
                for timer in cfg.timers:
                    if timer.enabled:
                        agent.add_timer(timer.seconds, timer.name, timer.hint)

            self._update_json_started(agent_id, started=True)
            await asyncio.sleep(0)

    async def stop(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")

        with log_operation(logger, "stop_agent", agent_name=agent.name):
            agent.clear_timers()
            await agent.stop()

            task = self._tasks.pop(agent_id, None)
            if task and not task.done():
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Agent '%s' task did not stop within 5s, cancelling", agent.name)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            dispatcher = self._dispatchers.get(agent_id)
            if dispatcher:
                await dispatcher.broadcast_system(f"Agent '{agent.name}' has been stopped")

            self._update_json_started(agent_id, started=False)

    async def start_persisted_agents(self) -> dict[str, str]:
        to_start = [
            agent_id for agent_id, started in self._persisted_started.items()
            if started and agent_id in self.agents
        ]
        if not to_start:
            return {}
        results = await asyncio.gather(
            *[self.start(agent_id) for agent_id in to_start],
            return_exceptions=True,
        )
        summary: dict[str, str] = {}
        for agent_id, result in zip(to_start, results):
            if isinstance(result, Exception):
                summary[agent_id] = f"failed: {result}"
            else:
                summary[agent_id] = "started"
        return summary

    # ------------------------------------------------------------------
    # State / Session helpers
    # ------------------------------------------------------------------

    def get_state(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"state": "unknown", "session_id": ""}
        raw_state = str(agent.state) if agent.state else "Ready"
        return {
            "state": raw_state.lower(),
            "session_id": agent.session.id if agent.session else "",
        }

    def get_sessions(self, agent_id: str) -> list[dict]:
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")
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

    async def switch_session(self, agent_id: str, session_id: str):
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")
        session_path = agent.session_dir / session_id / f"{session_id}.jsonl"
        if not session_path.exists():
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, f"Session '{session_id}' not found")
        with log_operation(logger, "switch_session", agent_name=agent.name):
            await agent.load_session(session_path)
        self._update_last_session_id(agent_id)

    async def new_session(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent:
            raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{agent_id}' not found")
        with log_operation(logger, "new_session", agent_name=agent.name):
            await agent.new_session()
        self._update_last_session_id(agent_id)

    def get_messages(self, agent_id: str) -> list[dict]:
        agent = self.agents.get(agent_id)
        if not agent or not agent.session:
            return []
        result = []
        for turn in agent.session.turns:
            for msg in turn.messages:
                msg_dict = msg.to_dict()
                ts = msg_dict.get("timestamp", 0)
                thinking = msg_dict.get("thinking", "")
                if thinking:
                    result.append({"role": "system", "content": thinking, "chunkType": "thinking", "source_agent": agent.name, "timestamp": ts})
                content = msg_dict.get("content", "")
                if msg_dict.get("role") == "tool":
                    pass
                elif isinstance(content, str):
                    if content.strip():
                        result.append({"role": msg_dict.get("role", ""), "content": content, "source_agent": agent.name, "timestamp": ts})
                elif isinstance(content, list):
                    for block in content:
                        bt = block.get("type", "")
                        if bt == "text":
                            text = block.get("text", "")
                            if text.strip():
                                result.append({"role": msg_dict.get("role", ""), "content": text, "source_agent": agent.name, "timestamp": ts})
                        elif bt in ("tool_use", "tooluse"):
                            tool_input = block.get("input", {})
                            result.append({"role": "system", "chunkType": "tool_use", "toolName": block.get("name", ""), "toolInput": tool_input, "content": json.dumps(tool_input, indent=2, ensure_ascii=False), "source_agent": agent.name, "timestamp": ts})
                for tc in msg_dict.get("tool_calls", []):
                    tc_input = tc.get("input", {})
                    result.append({"role": "system", "chunkType": "tool_use", "toolName": tc.get("name", ""), "toolInput": tc_input, "content": json.dumps(tc_input, indent=2, ensure_ascii=False), "source_agent": agent.name, "timestamp": ts})
                if msg_dict.get("role") == "tool":
                    result.append({"role": "system", "chunkType": "tool_result", "toolName": msg_dict.get("name", ""), "content": f"[{msg_dict.get('name', '')}]\n{str(msg_dict.get('content', ''))[:500]}", "source_agent": agent.name, "timestamp": ts})
        return result

    def get_dispatcher(self, agent_id: str) -> Optional[AgentOutputDispatcher]:
        return self._dispatchers.get(agent_id)

    # ------------------------------------------------------------------
    # Timer management
    # ------------------------------------------------------------------

    def list_timers(self, agent_id: str) -> list[dict]:
        cfg = self._agent_configs.get(agent_id)
        if not cfg:
            return []
        # Merge runtime running state if agent is running
        agent = self.agents.get(agent_id)
        running_names = set()
        if agent and agent._running:
            for t in agent.list_timers():
                if t.get("running"):
                    running_names.add(t["name"])
        return [
            {
                "name": t.name,
                "seconds": t.seconds,
                "hint": t.hint,
                "enabled": t.enabled,
                "running": t.name in running_names,
            }
            for t in cfg.timers
        ]

    def add_timer(self, agent_id: str, name: str, seconds: float, hint: str = "", enabled: bool = True):
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return

        # Auto-generate name if empty
        if not name or not name.strip():
            idx = len(cfg.timers) + 1
            while any(t.name == f"timer_{idx}" for t in cfg.timers):
                idx += 1
            name = f"timer_{idx}"

        # Reject duplicate name
        if any(t.name == name for t in cfg.timers):
            raise ValueError(f"Timer '{name}' already exists")

        new_timer = TimerConfig(name=name, seconds=seconds, hint=hint, enabled=enabled)
        cfg.timers.append(new_timer)

        if agent._running and enabled:
            agent.add_timer(seconds, name, hint)

        self._write_agent_json_full(agent_id, started=agent_id in self._started)

    def update_timer(self, agent_id: str, timer_name: str, seconds: float = None, hint: str = None, enabled: bool = None):
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return False

        timer = None
        for t in cfg.timers:
            if t.name == timer_name:
                timer = t
                break
        if timer is None:
            return False

        if seconds is not None:
            timer.seconds = seconds
        if hint is not None:
            timer.hint = hint
        if enabled is not None:
            timer.enabled = enabled

        if agent._running:
            agent.update_timer(timer_name, seconds=timer.seconds, hint=timer.hint)
            if timer.enabled:
                agent.start_timer(timer_name)
            else:
                agent.stop_timer(timer_name)

        self._write_agent_json_full(agent_id, started=agent_id in self._started)
        return True

    def start_timer(self, agent_id: str, timer_name: str) -> bool:
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return False

        success = agent.start_timer(timer_name)

        if success:
            for t in cfg.timers:
                if t.name == timer_name:
                    t.enabled = True
                    break
            self._write_agent_json_full(agent_id, started=agent_id in self._started)

        return success

    def stop_timer(self, agent_id: str, timer_name: str) -> bool:
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return False

        success = agent.stop_timer(timer_name)

        if success:
            for t in cfg.timers:
                if t.name == timer_name:
                    t.enabled = False
                    break
            self._write_agent_json_full(agent_id, started=agent_id in self._started)

        return success

    def cancel_timer(self, agent_id: str, timer_name: str) -> bool:
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return False

        if agent._running:
            agent.cancel_timer(timer_name)

        cfg.timers = [t for t in cfg.timers if t.name != timer_name]
        self._write_agent_json_full(agent_id, started=agent_id in self._started)
        return True

    # ------------------------------------------------------------------
    # Internal: tool/skill helpers
    # ------------------------------------------------------------------

    def _collect_missing_tool_ids(self, agent_id: str) -> list[str]:
        cfg = self._agent_configs.get(agent_id)
        if not cfg:
            return []
        missing: list[str] = []
        seen: set[str] = set()
        for tid in cfg.toolIds:
            if tid not in self._tool_factory._configs and tid not in seen:
                missing.append(tid)
                seen.add(tid)
        return missing

    # ------------------------------------------------------------------
    # Internal: hook helpers
    # ------------------------------------------------------------------

    def _build_shared_hook_config(self, hook_config: dict) -> BuiltinHookConfig:
        out = dict(hook_config or {})
        submodel_id = out.pop("submodelId", "") or ""
        submodel = self._model_factory.acquire_submodel(submodel_id)
        out["submodel"] = submodel
        return BuiltinHookConfig(**out)

    # ------------------------------------------------------------------
    # Internal: lazy init
    # ------------------------------------------------------------------

    async def _lazy_init(self, agent_id: str):
        agent = self.agents[agent_id]
        policy_raw = getattr(agent, "policy", {}) or {}
        if policy_raw:
            policy_snake = _policy_to_snake(policy_raw)
            policy_snake.setdefault("cwd", str(agent.base_dir))
            policy_obj = Policy(**policy_snake)
        else:
            policy_obj = None

        cfg = self._agent_configs.get(agent_id)
        tool_ids = list(cfg.toolIds) if cfg else []
        skill_ids = list(cfg.skillIds) if cfg else []

        # Build tools from toolIds
        mcp_server_to_template_ids: dict[str, list[str]] = {}
        for tid in tool_ids:
            tpl = self._tool_factory.get(tid)
            if tpl and tpl.mcpServerId:
                mcp_server_to_template_ids.setdefault(tpl.mcpServerId, []).append(tid)

        # Build tools from toolIds — in parallel
        async def _safe_build(tid):
            try:
                return await self._build_tool(agent_id, tid, policy_obj)
            except Exception as e:
                logger.warning(f"Agent '{agent.name}': failed to build tool '{tid}': {e}")
                return None

        build_results = await asyncio.gather(*[_safe_build(tid) for tid in tool_ids])
        built_tools = [t for t in build_results if t is not None]

        if built_tools:
            agent.add_tools(built_tools)

        # Register MCP clients
        mcp_client_map: dict[str, MCPClient] = {}
        bucket = self._mcp_clients.get(agent_id, {})
        for server_id in mcp_server_to_template_ids.keys():
            client = bucket.get(server_id)
            if client is not None:
                mcp_cfg = self._mcp_factory.get(server_id)
                if mcp_cfg:
                    mcp_client_map[mcp_cfg.name] = client
        if mcp_client_map:
            agent.register_mcp_clients(mcp_client_map)

        # Skills
        for sid in skill_ids:
            skill = self._skill_factory.get_instance(sid) if sid else None
            if skill:
                agent.add_skills([skill])

        # Hooks
        shared_hook_cfg = self._shared_hook_config.get(agent_id)
        if shared_hook_cfg is not None:
            for source in self._hook_names.get(agent_id, []):
                if source in HOOK_CREATOR:
                    HOOK_CREATOR[source](agent, shared_hook_cfg)

    # ------------------------------------------------------------------
    # Internal: tool building & MCP client management
    # ------------------------------------------------------------------

    async def _build_tool(self, agent_id: str, template_id: str, policy_obj=None) -> Tool:
        instances = self._tool_instances.setdefault(agent_id, {})
        if template_id in instances:
            return instances[template_id]

        async def _mcp_client_getter(mcp_server_id: str) -> MCPClient:
            return await self._get_mcp_client(agent_id, mcp_server_id)

        tool = await self._tool_factory.build_tool(
            template_id, policy=policy_obj, mcp_client_getter=_mcp_client_getter,
        )
        instances[template_id] = tool
        return tool

    async def _get_mcp_client(self, agent_id: str, mcp_server_id: str) -> MCPClient:
        bucket = self._mcp_clients.setdefault(agent_id, {})
        if mcp_server_id in bucket:
            return bucket[mcp_server_id]
        client = self._mcp_factory.create_client(mcp_server_id)
        try:
            await asyncio.wait_for(client.start(), timeout=15.0)
            await asyncio.wait_for(client.initialize(), timeout=15.0)
        except Exception:
            await client.close()
            raise
        bucket[mcp_server_id] = client
        return client

    async def _close_runtime(self, agent_id: str):
        bucket = self._mcp_clients.pop(agent_id, {})
        for client in bucket.values():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Failed to close MCP client for agent '{agent_id}': {e}")
        self._tool_instances.pop(agent_id, None)

    # ------------------------------------------------------------------
    # Internal: JSON persistence
    # ------------------------------------------------------------------

    def _write_agent_json_full(self, agent_id: str, started: bool):
        agent = self.agents.get(agent_id)
        if not agent:
            return
        cfg = self._agent_configs.get(agent_id)
        if not cfg:
            return
        policy = dict(getattr(agent, "policy", {}) or {})
        config_path = agent.base_dir / "agent_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            new_data: dict = {
                "id": agent_id,
                "name": agent.name,
                "type": cfg.type,
                "modelId": cfg.modelId,
                "systemPrompt": cfg.systemPrompt,
                "workingDir": policy.get("cwd", ""),
                "basePath": str(agent.base_dir),
                "toolIds": list(cfg.toolIds),
                "skillIds": list(cfg.skillIds),
                "toolPolicy": dict(policy),
                "hookNames": list(cfg.hookNames),
                "hookConfig": dict(cfg.hookConfig or {}),
                "timers": [t.model_dump() for t in cfg.timers],
                "started": bool(started),
                "lastSessionId": agent.session.id if getattr(agent, "session", None) else None,
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write json for agent '{agent.name}': {e}")

    def _update_last_session_id(self, agent_id: str):
        """Update lastSessionId in memory config and persist to disk."""
        agent = self.agents.get(agent_id)
        cfg = self._agent_configs.get(agent_id)
        if not agent or not cfg:
            return
        new_id = agent.session.id if getattr(agent, "session", None) else ""
        if cfg.lastSessionId == new_id:
            return
        cfg.lastSessionId = new_id
        # Persist to agent_config.json
        config_path = agent.base_dir / "agent_config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw = json.loads(f.read()) or {}
            raw["lastSessionId"] = new_id
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to update lastSessionId for '{agent.name}': {e}")

    def _update_json_started(self, agent_id: str, started: bool):
        agent = self.agents.get(agent_id)
        if not agent:
            return
        config_path = agent.base_dir / "agent_config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw = json.loads(f.read()) or {}
            raw["started"] = bool(started)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to update started flag for '{agent.name}': {e}")

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
