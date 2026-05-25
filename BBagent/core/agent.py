import asyncio
import json
import shutil
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional
from uuid import uuid4 as uuid

from .model import Model, Model_Input
from .tool import Tool, tool
from .message import (
    Session,
    Message,
    HumanMessage,
    ModelMessage,
    ToolMessage,
    ContentBlock,
    TextBlock,
    ImageBlock,
    ToolUseBlock,
)
from .skill import Skill
from .hook import AgentHook, HookType, Hook
from .input import AgentEvent, EventType, InputChannel
from .logger import AgentLogger, _NullLogger

@dataclass
class AgentConfig:
    model: Model
    base_dir: Path | str = Path.cwd()
    system_prompt: str = ""
    name: str = 'Agent_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '_' + uuid().hex[:8]
    session: Session = None
    tools: List[Tool] = None
    skills: List[Skill] = None
    hook: AgentHook = None

    def __post_init__(self): 
        if self.tools is None:
            self.tools = []
        if self.skills is None:
            self.skills = []
        self.base_dir = Path(self.base_dir) / self.name


@dataclass
class AgentState:
    Ready = 'Ready'
    Waiting = 'Waiting'
    Running = 'Running'
    Error = 'Error'


class Agent:
    def __init__(self,agent_config:AgentConfig):
        self.name = agent_config.name
        self.model = agent_config.model

        self.base_dir = agent_config.base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt_path = self.base_dir / 'system_prompt.md'
        self.system_prompt = agent_config.system_prompt
        if not self.system_prompt_path.exists():
            self.system_prompt_path.write_text(agent_config.system_prompt, encoding='utf-8')
        self.session_dir = self.base_dir / 'session'
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.session = agent_config.session or Session.create(self.session_dir)

        self.tools: dict[str, Tool] = {}
        if agent_config.tools:
            self.add_tools(agent_config.tools)

        self.skills: dict[str, Skill] = {}
        if agent_config.skills:
            self._add_load_skills_tool()
            for skill in agent_config.skills:
                self.skills[skill.name] = skill
        self.skill_prompt = self._load_skill_prompt()

        self.team_prompt = ""
        self.teammate_prompt = ""

        self.hook = agent_config.hook if agent_config.hook else AgentHook()
        if self.hook:
            self.hook.set_context(self)

        self._event_queue: asyncio.Queue = asyncio.Queue()
        self.input = InputChannel()
        self._output_callback: Optional[Callable] = None
        self._running = False

        self.logger = AgentLogger(
            name=self.name,
            log_dir=self.base_dir,
        )

        self.state = AgentState.Ready

    def change_name(self, name: str):
        self.name = name
    
    def change_model(self, model: Model):
        self.model = model
    
    def change_base_dir(self, path: Path | str):
        new_base = Path(path)
        old_base = self.base_dir
        new_base.mkdir(parents=True, exist_ok=True)

        new_system_prompt = new_base / 'system_prompt.md'
        if new_system_prompt.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            deprecated = new_base / f'system_prompt_deprecated_{timestamp}.md'
            shutil.move(str(new_system_prompt), str(deprecated))
        shutil.copy2(old_base / 'system_prompt.md', new_system_prompt)

        new_session = new_base / 'session'
        if new_session.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            deprecated = new_base / f'session_deprecated_{timestamp}'
            shutil.move(str(new_session), str(deprecated))
        shutil.copytree(old_base / 'session', new_session)

        self.base_dir = new_base
        self.system_prompt_path = new_system_prompt
        self.session_dir = new_session
    
    def change_system_prompt(self, prompt: str):
        self.system_prompt = prompt
        self.system_prompt_path.write_text(prompt, encoding='utf-8')
    
    async def load_session(self, session_file_path: Path | str):
        await self.hook.trigger(HookType.NEW_SESSION)
        self.session.save()

        src = Path(session_file_path)
        if not src.exists():
            raise FileNotFoundError(f"Session file not found: {src}")

        session_id = src.stem
        src_dir = src.parent
        jsonl_src = src_dir / f'{session_id}.jsonl'
        md_src = src_dir / f'{session_id}.md'

        dst_dir = self.session_dir / session_id
        dst_dir.mkdir(parents=True, exist_ok=True)

        for f in [jsonl_src, md_src]:
            if f.exists():
                dst = dst_dir / f.name
                if dst.exists():
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    deprecated = dst_dir / f'{f.stem}_deprecated_{timestamp}{f.suffix}'
                    shutil.move(str(dst), str(deprecated))
                shutil.copy2(f, dst)

        self.session = Session.load(session_id, dst_dir)
        
        ever_used_tools = self.session.ever_used_tools
        for tool_name in ever_used_tools:
            if tool_name not in self.tools:
                self.logger.warning(f"Tool '{tool_name}' not found in agent tools")

    async def new_session(self):
        await self.hook.trigger(HookType.NEW_SESSION)
        self.session.save()
        self.session = Session.create(self.session_dir)
    
    def add_tools(self, tools: List[Tool]):
        for t in tools:
            self.tools[t.name] = t
    
    def _add_load_skills_tool(self):
        @tool
        def load_skill(skill_name: str):
            """Load a skill by name to get its full capabilities and instructions. Use this when you need to access a specific skill's detailed content."""
            skill = self.skills.get(skill_name)
            if not skill:
                return f"Unknown skill: {skill_name}"
            else:
                if skill.metadata:
                    return f"{skill.metadata.to_dict()}-{skill.body}"
                else:
                    return skill.body
        
        self.add_tools([load_skill])
    
    async def tool_execute(self, tool_use: ToolUseBlock) -> ToolMessage:
        await self.hook.trigger(HookType.ON_TOOL_USE, tool_use)
        tool = self.tools.get(tool_use.name)

        if tool is None:
            content = f"Unknown tool: {tool_use.name}"
            self.logger.warning(
                f"Tool not found: {tool_use.name}",
                context={"tool_name": tool_use.name, "tool_input": tool_use.input}
            )
        else:
            self.logger.info(
                f"Tool '{tool.name}' execution started",
                context={"tool_name": tool.name, "tool_input": tool_use.input}
            )
            with self.logger.span(f"tool_{tool.name}"):
                try:
                    if tool.is_async:
                        raw_result = await tool.async_invoke(tool_use.input)
                    else:
                        raw_result = tool.invoke(tool_use.input)

                    if isinstance(raw_result, str):
                        content = raw_result
                    elif isinstance(raw_result, list):
                        content = raw_result
                    else:
                        content = json.dumps(raw_result, ensure_ascii=False)

                    self.logger.debug(
                        f"Tool '{tool_use.name}' completed successfully",
                        context={"tool_name": tool_use.name}
                    )
                except Exception as e:
                    content = f"Tool invocation error: {str(e)}"
                    self.logger.error(
                        f"Tool '{tool_use.name}' execution failed",
                        context={
                            "tool_name": tool_use.name,
                            "tool_input": tool_use.input,
                            "error_type": type(e).__name__,
                        },
                        exc_info=sys.exc_info()
                    )

        tool_msg = ToolMessage(tool_use.id, tool_use.name, content)
        await self.hook.trigger(HookType.ON_TOOL_RESULT, tool_msg)
        return tool_msg

    def _load_skill_prompt(self):
        """从 skills.md 加载技能提示词，文件不存在时使用默认值"""
        skill_system_prompt = ["""You have access to the following skills. Each skill's complete information (including its full capabilities, usage instructions, and detailed behavior) is stored in a markdown file located at the skill's path. When you need to use a specific skill, read its SKILL.md file from the skill's path to get the complete details.

Your available skills are:
"""]
        skill_short_prompt = [f'- name: {s.name}, Path: {s.path}/SKILL.md, Description: {s.description}' for s in self.skills.values()]
        return '\n'.join(skill_system_prompt + skill_short_prompt)

    def add_skills(self, skills:List[Skill]):
        new_skills = {s.name: s for s in skills}
        self.skills.update(new_skills)
        self.skill_prompt = self._load_skill_prompt()
    
    def construct_model_input(self) -> Model_Input:
        tools = list(self.tools.values())
        prompt = self.system_prompt + self.team_prompt + self.teammate_prompt + self.skill_prompt
        messages = self.session.get_visible_context()
        return Model_Input(prompt=prompt, tools=tools, messages=messages)
      
    async def stream_tool_loop(self):
        try:
            while True:
                tool_tasks = []
                stop_reason = None
                interrupted = False
                
                await self.hook.trigger(HookType.BEFORE_STREAM)
                if self.hook.should_break():
                    break
                model_input = self.construct_model_input()
                async for chunk in self.model.async_stream_invoke(model_input): 
                    if self.hook.should_break():
                        interrupted = True
                        break
                    
                    chunk_type = chunk.get('type')
                    content = chunk.get('content', '')

                    if chunk_type == 'text':
                        await self.hook.trigger(HookType.ON_TEXT_CHUNK, content)
                        yield chunk

                    
                    if chunk_type == 'thinking':
                        await self.hook.trigger(HookType.ON_THINKING_CHUNK, content)
                        yield chunk

                    if chunk_type == 'completed_tool_use':
                        tool_use = content
                        task = asyncio.create_task(
                            self.tool_execute(tool_use)
                        )
                        tool_tasks.append(task)
                        yield chunk

                    if chunk_type == 'completed_message':
                        stop_reason = content.stop_reason
                        self.logger.debug(
                            "Model response received",
                            context={"stop_reason": stop_reason}
                        )
                        await self.hook.trigger(HookType.ON_MESSAGE, content)
                        self.session.add_message(content)
                        yield chunk
                        break
                
                if interrupted:
                    break
                
                if stop_reason == 'tool_use':
                    tool_results = await asyncio.gather(*tool_tasks)
                    yield {'type': 'tool_results', 'content': tool_results}
                    self.session.add_message(tool_results)
                elif stop_reason == 'end_turn':
                    break
                else:
                    self.logger.error(
                        f"Unexpected stop reason: {stop_reason}",
                        context={"stop_reason": stop_reason}
                    )
                    raise ValueError(f"Stop reason: {stop_reason}")
        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Agent loop error: {error_msg}",
                context={
                    "error_type": type(e).__name__
                },
                exc_info=sys.exc_info()
            )
            self.state = AgentState.Error
            await self.hook.trigger(HookType.ON_ERROR, e)
            raise
                 
    async def run(self, human_msg:HumanMessage):
        self.state = AgentState.Running
        self.logger.set_trace_id()
        self.logger.info(
            "Agent run started",
            context={"session_id": self.session.session_id}
        )
        self.session.add_message(human_msg)
        await self.hook.trigger(HookType.AFTER_INPUT)
        try:
            async for chunk in self.stream_tool_loop():
                        yield chunk
        except Exception as e:
            raise e
        finally:
            self.session.save()
            self.state = AgentState.Ready
            await self.hook.trigger(HookType.AFTER_RUN)
            self.logger.info("Agent run completed")
            self.logger.clear_trace_id()

    def on_output(self, callback: Callable):
        self._output_callback = callback

    async def _emit(self, chunk):
        if self._output_callback:
            if asyncio.iscoroutinefunction(self._output_callback):
                await self._output_callback(chunk)
            else:
                self._output_callback(chunk)

    async def start(self):
        if self._running:
            self.logger.warning("Agent already running, start ignored")
            return

        self.logger.info("Agent event loop started")
        self._running = True
        self.state = AgentState.Waiting

        await self.input.start(self._event_queue)

        try:
            while self._running:
                event = await self._event_queue.get()
                if event is _SENTINEL:
                    break
                self.state = AgentState.Running
                try:
                    await self._handle_event(event)
                except Exception:
                    pass
                if self._running:
                    self.state = AgentState.Waiting
        finally:
            await self.input.stop()
            self._event_queue = asyncio.Queue()
            self._running = False
            self.state = AgentState.Ready
            self.logger.info("Agent event loop stopped")

    async def interrupt(self):
        self.hook.context.break_loop()

    async def stop(self):
        self.logger.info("Agent stopping")
        self._running = False
        self.hook.context.break_loop()
        self._event_queue.put_nowait(_SENTINEL)

    async def _handle_event(self, event: AgentEvent):
        self.logger.set_trace_id(event.correlation_id)
        self.logger.info(
            "Event handling started",
            context={
                "event_type": event.type.value,
                "source_id": event.source_id,
                "correlation_id": event.correlation_id,
            }
        )
        with self.logger.span("event_handle"):
            msg = event.to_human_message()
            self.session.add_message(msg)
            await self.hook.trigger(HookType.AFTER_INPUT, msg)
            try:
                async for chunk in self.stream_tool_loop():
                    await self._emit(chunk)
            except Exception as e:
                self.logger.error(
                    f"Event handling failed: {str(e)}",
                    context={
                        "event_type": event.type.value,
                        "source_id": event.source_id,
                        "correlation_id": event.correlation_id,
                    },
                    exc_info=sys.exc_info()
                )
                await self.hook.trigger(HookType.ON_ERROR, e)
            finally:
                self.session.save()
                await self.hook.trigger(HookType.AFTER_RUN)
                self.logger.info("Event handling completed")
                self.logger.clear_trace_id()


_SENTINEL = object()


class SubAgent:
    def __init__(self, model: Model, tools: List[Tool] = None, system_prompt: str = "",
                skills: List[Skill] = None, name: str = None,
                logger: AgentLogger = None):
        self.name = name or f'sub_{id(self)}'
        self.model = model
        self.system_prompt = system_prompt

        self.logger = logger or _NullLogger()

        self.skills: dict[str, Skill] = {}
        if skills:
            self._add_load_skills_tool()
            for skill in skills:
                self.skills[skill.name] = skill
        self.skill_prompt = self._load_skill_prompt()
        
        self.tools: dict[str, Tool] = {}
        if tools:
            for t in tools:
                self.tools[t.name] = t

    def add_tools(self, tools: List[Tool]):
        for t in tools:
            self.tools[t.name] = t
    
    def _add_load_skills_tool(self):
        @tool
        def load_skill(skill_name: str):
            """Load a skill by name to get its full capabilities and instructions. Use this when you need to access a specific skill's detailed content."""
            skill = self.skills.get(skill_name)
            if not skill:
                return f"Unknown skill: {skill_name}"
            else:
                if skill.metadata:
                    return f"{skill.metadata.to_dict()}-{skill.body}"
                else:
                    return skill.body
        
        self.add_tools([load_skill])

    def _load_skill_prompt(self):
        if not self.skills:
            return ''
        skill_system_prompt = ["""You have access to the following skills. Each skill's complete information (including its full capabilities, usage instructions, and detailed behavior) is stored in a markdown file located at the skill's path. When you need to use a specific skill, read its SKILL.md file from the skill's path to get the complete details.

Your available skills are:
"""]
        skill_short_prompt = [f'- name: {s.name}, Path: {s.path}/SKILL.md, Description: {s.description}' for s in self.skills]
        return '\n'.join(skill_system_prompt + skill_short_prompt)

    def add_skills(self, skills: List[Skill]):
        self.skills.extend(skills)
        self.skill_prompt += '\n'.join([f'- name: {s.name}, Path: {s.path}/SKILL.md, Description: {s.description}' for s in skills])

    async def tool_execute(self, tool_use: ToolUseBlock) -> ToolMessage:
        tool = self.tools.get(tool_use.name)

        if tool is None:
            content = f"Unknown tool: {tool_use.name}"
            self.logger.warning(
                f"Tool not found: {tool_use.name}",
                context={"tool_name": tool_use.name, "tool_input": tool_use.input}
            )
        else:
            self.logger.info(
                f"Tool '{tool.name}' execution started",
                context={"tool_name": tool.name, "tool_input": tool_use.input}
            )
            with self.logger.span(f"tool_{tool.name}"):
                try:
                    if tool.is_async:
                        raw_result = await tool.async_invoke(tool_use.input)
                    else:
                        raw_result = tool.invoke(tool_use.input)

                    if isinstance(raw_result, str):
                        content = raw_result
                    elif isinstance(raw_result, list):
                        content = raw_result
                    else:
                        content = json.dumps(raw_result, ensure_ascii=False)

                    self.logger.debug(
                        f"Tool '{tool_use.name}' completed successfully",
                        context={"tool_name": tool_use.name}
                    )
                except Exception as e:
                    content = f"Tool invocation error: {str(e)}"
                    self.logger.error(
                        f"Tool '{tool_use.name}' execution failed",
                        context={
                            "tool_name": tool_use.name,
                            "tool_input": tool_use.input,
                            "error_type": type(e).__name__,
                        },
                        exc_info=sys.exc_info()
                    )

        return ToolMessage(tool_use.id, tool_use.name, content)

    def _normalize_input(self, messages: List[Message] | Message | str) -> List[Message]:
        if isinstance(messages, str):
            return [HumanMessage(messages)]
        if isinstance(messages, Message):
            return [messages]
        return list(messages)

    async def run(self, messages: List[Message] | Message | str) -> str:
        messages = self._normalize_input(messages)
        tools = list(self.tools.values())

        self.logger.set_trace_id()
        self.logger.info(
            "SubAgent run started",
            context={"agent_name": self.name}
        )
        try:
            with self.logger.span("subagent_run"):
                while True:
                    model_input = Model_Input(
                        prompt=self.system_prompt + self.skill_prompt,
                        tools=tools,
                        messages=messages,
                    )
                    try:
                        result = await self.model.async_invoke(model_input)
                    except Exception as e:
                        self.logger.error(
                            f"SubAgent model run failed: {str(e)}",
                            context={"agent_name": self.name, "error_type": type(e).__name__},
                            exc_info=sys.exc_info()
                        )
                        raise e

                    messages.append(result)
                    self.logger.debug(
                        "Model response received",
                        context={"agent_name": self.name, "stop_reason": result.stop_reason}
                    )

                    if result.stop_reason == 'tool_use':
                        for tool_use in result.tool_calls:
                            tool_msg = await self.tool_execute(tool_use)
                            messages.append(tool_msg)
                    elif result.stop_reason == 'end_turn':
                        break
                    else:
                        error_msg = f"SubAgent stop reason: {result.stop_reason}"
                        self.logger.error(
                            error_msg,
                            context={"agent_name": self.name, "stop_reason": result.stop_reason}
                        )
                        raise ValueError(error_msg)

            if isinstance(result.content, list):
                parts = [b.text for b in result.content if isinstance(b, TextBlock)]
                text = '\n'.join(parts)
            else:
                text = str(result.content)

            self.logger.info(
                "SubAgent run completed",
                context={"agent_name": self.name}
            )
            return text
        finally:
            self.logger.clear_trace_id()






