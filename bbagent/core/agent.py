import asyncio
import contextlib
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4 as uuid

from .hook import AgentHook, HookType
from .input import InputChannel, InputEvent
from .logger import AgentLogger, _NullLogger
from .message import (
    ContentBlock,
    HumanMessage,
    Message,
    ModelMessage,
    Session,
    TextBlock,
    ToolMessage,
    ToolUseBlock,
)
from .model import Model, Model_Input
from .skill import Skill
from .tool import Tool, tool


@dataclass
class AgentConfig:
    model: Model
    base_dir: Path | str = field(default_factory=Path.cwd)
    system_prompt: str = ""
    name: str = ""
    session: Session | None = None
    tools: list[Tool] | None = None
    skills: list[Skill] | None = None

    def __post_init__(self):
        if not self.name:
            self.name = 'Agent_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '_' + uuid().hex[:8]
        if self.tools is None:
            self.tools = []
        if self.skills is None:
            self.skills = []
        self.base_dir = Path(self.base_dir)
        if self.base_dir.name != self.name:
            self.base_dir = self.base_dir / self.name


@dataclass
class AgentState:
    Ready = 'ready'
    Waiting = 'waiting'
    Running = 'running'
    Error = 'error'


class Agent:
    # ========================================================================
    # Initialization
    # ========================================================================
    def __init__(self,agent_config:AgentConfig):
        self.name = agent_config.name

        self.model = agent_config.model
        self.policy: dict[str, Any] = {}

        self.base_dir = Path(agent_config.base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.system_prompt_path = self.base_dir / 'system_prompt.md'
        self.system_prompt = agent_config.system_prompt
        if not self.system_prompt_path.exists():
            self.system_prompt_path.write_text(agent_config.system_prompt, encoding='utf-8')
        self.runtime_prompts_path = self.base_dir / 'runtime_prompts.md'
        self.runtime_prompts: dict[str, dict[str, str | int]] = {}
        self._write_runtime_prompts_file()

        self.session_dir = self.base_dir / 'session'
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session = agent_config.session

        self.tools: dict[str, Tool] = {}
        if agent_config.tools:
            self.add_tools(agent_config.tools)

        self.skills: dict[str, Skill] = {}
        if agent_config.skills:
            self._add_load_skills_tool()
            for skill in agent_config.skills:
                self.skills[skill.name] = skill
        skill_prompt = self._load_skill_prompt()
        if skill_prompt:
            self.set_runtime_prompt("skills", skill_prompt, order=40)

        self.hook = AgentHook()
        self.hook.set_context(self)

        self.input = InputChannel()
        self._output_callback: Callable | None = None
        self._loop_running = False
        self._interrupt_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._active_tool_tasks: set[asyncio.Task[ToolMessage]] = set()

        self.logger = AgentLogger(
            name=self.name,
            log_dir=self.base_dir,
        )

        self.state = AgentState.Ready

    # ========================================================================
    # Properties
    # ========================================================================
    @property
    def is_running(self) -> bool:
        return self._loop_running

    # ========================================================================
    # Session Management
    # ========================================================================
    def _ensure_session(self) -> Session:
        if self.session is None:
            self.session = Session.create(self.session_dir)
        return self.session

    def set_session(self, session: Session):
        self.session = session

    async def load_session(self, session_file_path: Path | str):
        await self.hook.trigger(HookType.NEW_SESSION)
        if self.session is not None:
            self.session.save()

        src = Path(session_file_path)
        if not src.exists():
            raise FileNotFoundError(f"Session file not found: {src}")

        session_id = src.stem
        src_dir = src.parent
        dst_dir = self.session_dir / session_id
        dst_dir.mkdir(parents=True, exist_ok=True)

        # Only copy files when importing from an external location.
        # If the session is already in this agent's session_dir, skip the
        # copy to avoid moving the source file away from under itself.
        if src_dir.resolve() != dst_dir.resolve():
            jsonl_src = src_dir / f'{session_id}.jsonl'
            md_src = src_dir / f'{session_id}.md'
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
        if self.session is not None:
            self.session.save()
        self.session = Session.create(self.session_dir)

    # ========================================================================
    # Configuration
    # ========================================================================
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
        new_runtime_prompts = new_base / 'runtime_prompts.md'
        old_runtime_prompts = old_base / 'runtime_prompts.md'
        if new_runtime_prompts.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            deprecated = new_base / f'runtime_prompts_deprecated_{timestamp}.md'
            shutil.move(str(new_runtime_prompts), str(deprecated))
        if old_runtime_prompts.exists():
            shutil.copy2(old_runtime_prompts, new_runtime_prompts)

        new_session = new_base / 'session'
        if new_session.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            deprecated = new_base / f'session_deprecated_{timestamp}'
            shutil.move(str(new_session), str(deprecated))
        shutil.copytree(old_base / 'session', new_session)

        self.base_dir = new_base
        self.system_prompt_path = new_system_prompt
        self.runtime_prompts_path = new_runtime_prompts
        self.session_dir = new_session

    def change_system_prompt(self, prompt: str):
        self.system_prompt = prompt
        self.system_prompt_path.write_text(prompt, encoding='utf-8')

    # ========================================================================
    # Runtime Prompt Management
    # ========================================================================
    def set_runtime_prompt(self, key: str, prompt: str, order: int = 100) -> None:
        if not prompt:
            self.remove_runtime_prompt(key)
            return
        self.runtime_prompts[key] = {"content": prompt, "order": order}
        self._write_runtime_prompts_file()

    def remove_runtime_prompt(self, key: str) -> None:
        self.runtime_prompts.pop(key, None)
        self._write_runtime_prompts_file()

    def render_runtime_prompts(self) -> str:
        rendered = [
            str(item["content"])
            for _key, item in sorted(
                self.runtime_prompts.items(),
                key=lambda pair: (int(pair[1].get("order", 100)), pair[0]),
            )
            if str(item.get("content", "")).strip()
        ]
        if not rendered:
            return ""
        return "\n\n" + "\n\n".join(rendered)

    def _write_runtime_prompts_file(self) -> None:
        lines = [
            "# Runtime Prompts",
            "",
            "This file is generated for inspection only. Runtime prompts are rebuilt from agent/team/skill/hook configuration and are not loaded from this file.",
        ]
        for key, item in sorted(
            self.runtime_prompts.items(),
            key=lambda pair: (int(pair[1].get("order", 100)), pair[0]),
        ):
            content = str(item.get("content", "")).rstrip()
            if not content:
                continue
            lines.extend(["", f"## {key}", "", content])
        lines.append("")
        self.runtime_prompts_path.write_text("\n".join(lines), encoding='utf-8')

    # ========================================================================
    # Timer Management
    # ========================================================================
    def add_timer(self, seconds: float, name: str = "", hint: str = "") -> None:
        """Add interval-triggered timer task"""
        self.input.every(seconds, name, hint)

    def add_at_timer(self, time_str: str, name: str = "", hint: str = "") -> None:
        """Add time-point-triggered timer task

        Args:
            time_str: time string, format is "HH:MM" or "HH:MM:SS"
            name: task name
            hint: task hint
        """
        self.input.at(time_str, name, hint)

    def list_timers(self) -> list[dict]:
        return self.input.list_timers()

    def update_timer(self, name: str, seconds: float | None = None, time_str: str | None = None, hint: str | None = None) -> bool:
        """Update timer configuration

        Args:
            name: task name
            seconds: new interval seconds (interval-triggered task)
            time_str: new time point (time-point-triggered task)
            hint: new task hint
        """
        # find interval config
        for s, n, h in self.input._interval_configs:
            if n == name:
                new_seconds = seconds if seconds is not None else s
                new_hint = hint if hint is not None else h
                self.input.every(new_seconds, name, new_hint)
                return True

        # find time-point config
        for t, n, h in self.input._at_configs:
            if n == name:
                new_time = time_str if time_str is not None else t
                new_hint = hint if hint is not None else h
                self.input.at(new_time, name, new_hint)
                return True

        return False

    def start_timer(self, name: str) -> bool:
        return self.input.start_timer(name)

    def stop_timer(self, name: str) -> bool:
        return self.input.stop_timer(name)

    def cancel_timer(self, name: str) -> bool:
        return self.input.cancel(name)

    def clear_timers(self):
        self.input.clear_timers()

    # ========================================================================
    # Tool Management
    # ========================================================================
    def add_tools(self, tools: list[Tool]):
        for t in tools:
            existing = self.tools.get(t.name)
            if existing is not None and existing is not t:
                raise ValueError(f"Duplicate tool name: {t.name}")
            self.tools[t.name] = t
        self.tools = dict(sorted(self.tools.items(), key=lambda item: item[0]))

    def remove_tools(self, tool_names: list[str]):
        for name in tool_names:
            self.tools.pop(name, None)
        if self.session is not None:
            ever_used_tools = self.session.ever_used_tools
            for tool_name in ever_used_tools:
                if tool_name not in self.tools:
                    self.logger.warning(f"Tool '{tool_name}' not found in agent tools")

    # ========================================================================
    # Skill Management
    # ========================================================================
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
        """Load skill prompts from skills.md, uses default value if file does not exist"""
        if not self.skills:
            return ''
        skill_system_prompt = ["""You have access to the following skills. When you need to use a specific skill, call the `load_skill` tool with the skill name to get its full capabilities, usage instructions, and detailed behavior.

Your available skills are:
"""]
        skill_short_prompt = [f'- name: {s.name}, Description: {s.description}' for s in self.skills.values()]
        return '\n'.join(skill_system_prompt + skill_short_prompt)

    def add_skills(self, skills:list[Skill]):
        new_skills = {s.name: s for s in skills}
        if not self.skills and new_skills:
            self._add_load_skills_tool()
        self.skills.update(new_skills)
        self.set_runtime_prompt("skills", self._load_skill_prompt(), order=40)

    def remove_skills(self, skill_names: list[str]):
        """Remove skills with specified names, and refresh runtime skill prompt."""
        if not skill_names:
            return
        for name in skill_names:
            self.skills.pop(name, None)
        if not self.skills:
            self.remove_runtime_prompt("skills")
        else:
            self.set_runtime_prompt("skills", self._load_skill_prompt(), order=40)

    # ========================================================================
    # Execution: Model Input & Tool Execution
    # ========================================================================
    def construct_model_input(self) -> Model_Input:
        session = self._ensure_session()
        tools = list(self.tools.values())
        prompt = self.system_prompt + self.render_runtime_prompts()
        messages = session.get_visible_context()
        return Model_Input(prompt=prompt, tools=tools, messages=messages)

    async def tool_execute(self, tool_use: ToolUseBlock) -> ToolMessage:
        tool = self.tools.get(tool_use.name)

        if tool is None:
            content: str | list[ContentBlock] = f"Unknown tool: {tool_use.name}"
            self.logger.warning(
                f"Tool not found: {tool_use.name}",
                context={"tool_name": tool_use.name, "tool_input": tool_use.input}
            )
        else:
            await self.hook.trigger(HookType.ON_TOOL_USE, tool_use)
            self.logger.info(
                f"Tool '{tool.name}' execution started",
                context={"tool_name": tool.name, "tool_input": tool_use.input}
            )
            with self.logger.span(f"tool_{tool.name}"):
                try:
                    if tool.is_async:
                        raw_result = await tool.async_invoke(tool_use.input)
                    else:
                        raw_result = await asyncio.to_thread(tool.invoke, tool_use.input)

                    if isinstance(raw_result, str):
                        content = raw_result
                    elif isinstance(raw_result, list):
                        content = cast(list[ContentBlock], raw_result)
                    else:
                        content = json.dumps(raw_result, ensure_ascii=False)

                    self.logger.debug(
                        f"Tool '{tool_use.name}' completed successfully",
                        context={"tool_name": tool_use.name}
                    )
                except asyncio.CancelledError:
                    self.logger.info(
                        f"Tool '{tool_use.name}' execution cancelled",
                        context={"tool_name": tool_use.name}
                    )
                    raise
                except Exception as e:
                    content = f"Tool invocation error: {e!s}"
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

    # ========================================================================
    # Execution: Interrupt Control
    # ========================================================================
    async def _cancel_tool_tasks(self, tool_tasks: list[asyncio.Task[ToolMessage]]) -> None:
        for task in tool_tasks:
            if not task.done():
                task.cancel()
        if tool_tasks:
            await asyncio.gather(*tool_tasks, return_exceptions=True)

    async def _wait_for_tool_results(
        self,
        tool_tasks: list[asyncio.Task[ToolMessage]],
    ) -> list[ToolMessage] | None:
        tool_results_future = asyncio.gather(*tool_tasks)
        interrupt_waiter = asyncio.create_task(self._interrupt_event.wait())
        try:
            waitables: set[asyncio.Future[Any]] = {tool_results_future, interrupt_waiter}
            _done, _ = await asyncio.wait(
                waitables,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._interrupt_event.is_set():
                tool_results_future.cancel()
                await self._cancel_tool_tasks(tool_tasks)
                return None

            interrupt_waiter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await interrupt_waiter
            return await tool_results_future
        except asyncio.CancelledError:
            tool_results_future.cancel()
            await self._cancel_tool_tasks(tool_tasks)
            raise

    # ========================================================================
    # Execution: Core Execution Flow
    # ========================================================================
    async def stream_tool_loop(self):
        try:
            while True:
                tool_tasks: list[asyncio.Task[ToolMessage]] = []
                stop_reason: str | None = None
                interrupted = False
                pending_model_message: ModelMessage | None = None

                await self.hook.trigger(HookType.BEFORE_STREAM)
                if self._interrupt_event.is_set():
                    self.logger.info("Agent interrupted before stream")
                    yield {'type': 'event', 'event_type': 'interrupted', 'content': 'Agent interrupted'}
                    break
                model_input = self.construct_model_input()
                async for chunk in self.model.async_stream_invoke(model_input):
                    if self._interrupt_event.is_set():
                        self.logger.info("Agent interrupted during stream")
                        interrupted = True
                        break

                    chunk_type = chunk.get('type')
                    content = chunk.get('content', '')

                    if chunk_type == 'text':
                        await self.hook.trigger(HookType.ON_TEXT_CHUNK, content)
                        yield {'type': 'stream_chunk', 'chunk_type': 'text', 'content': content}


                    if chunk_type == 'thinking':
                        await self.hook.trigger(HookType.ON_THINKING_CHUNK, content)
                        yield {'type': 'stream_chunk', 'chunk_type': 'thinking', 'content': content}

                    if chunk_type == 'completed_tool_use':
                        tool_use = cast(ToolUseBlock, content)
                        task = asyncio.create_task(
                            self.tool_execute(tool_use)
                        )
                        self._active_tool_tasks.add(task)
                        task.add_done_callback(self._active_tool_tasks.discard)
                        tool_tasks.append(task)
                        yield {'type': 'stream_chunk', 'chunk_type': 'completed_tool_use', 'content': tool_use}

                    if chunk_type == 'completed_message':
                        model_message = cast(ModelMessage, content)
                        stop_reason = model_message.stop_reason
                        self.logger.debug(
                            "Model response received",
                            context={"stop_reason": stop_reason}
                        )
                        await self.hook.trigger(HookType.ON_MESSAGE, model_message)
                        session = self._ensure_session()
                        if stop_reason == 'tool_use':
                            pending_model_message = model_message
                        else:
                            session.add_message(model_message)
                        yield {'type': 'stream_chunk', 'chunk_type': 'completed_message', 'content': model_message}
                        break

                if interrupted:
                    self.logger.info("Agent tool loop interrupted after stream")
                    await self._cancel_tool_tasks(tool_tasks)
                    yield {'type': 'event', 'event_type': 'interrupted', 'content': 'Agent interrupted'}
                    break

                if stop_reason == 'tool_use':
                    self.logger.info(
                        "Agent tool loop continuing for tool execution",
                        context={"tool_count": len(tool_tasks)}
                    )
                    tool_results = await self._wait_for_tool_results(tool_tasks)
                    if tool_results is None:
                        self.logger.info("Agent tool loop interrupted during tool execution")
                        yield {'type': 'event', 'event_type': 'interrupted', 'content': 'Agent interrupted'}
                        break
                    yield {'type': 'stream_chunk', 'chunk_type': 'tool_results', 'content': tool_results}
                    session = self._ensure_session()
                    if pending_model_message is not None:
                        session.add_message([pending_model_message, *tool_results])
                    else:
                        session.add_message(tool_results)
                elif stop_reason == 'end_turn':
                    self.logger.info("Agent tool loop ended with end_turn")
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
        self._interrupt_event.clear()
        self.state = AgentState.Running
        self.logger.set_trace_id()
        session = self._ensure_session()
        with self.logger.span("agent_run"):
            self.logger.info(
                "Agent run started",
                context={"session_id": session.id}
            )
            session.add_message(human_msg)
            await self.hook.trigger(HookType.AFTER_INPUT)
            try:
                async for chunk in self.stream_tool_loop():
                            yield chunk
            except Exception as e:
                self.logger.error(
                    f"Agent run failed: {e}",
                    exc_info=True,
                )
                raise
            finally:
                if self.state == AgentState.Running:
                    self.state = AgentState.Ready
                await self.hook.trigger(HookType.AFTER_RUN)
                if self.session is not None and self.session.dir is not None:
                    try:
                        self.session.save()
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to save session metadata: {e}",
                            context={"session_id": self.session.id},
                        )
                self.logger.info("Agent run completed")
                self.logger.clear_trace_id()

    async def _handle_event(self, event: InputEvent):
        self._interrupt_event.clear()
        self.logger.set_trace_id()
        with self.logger.span("event_handle"):
            self.logger.info(
                "Event handling started",
                context={
                    "event_type": event.type.value,
                    "source_id": event.source_id,
                }
            )
            msg = event.to_human_message()
            session = self._ensure_session()
            session.add_message(msg)

            if isinstance(msg.content, str):
                text = msg.content
            elif isinstance(msg.content, list):
                text = " ".join(
                    b.text if hasattr(b, "text") else str(b)
                    for b in msg.content
                )
            else:
                text = str(msg.content)
            await self._emit({
                "type": "event",
                "event_type": event.type.value,
                "source_id": event.source_id,
                "content": text,
            })

            await self.hook.trigger(HookType.AFTER_INPUT)
            try:
                async for chunk in self.stream_tool_loop():
                    await self._emit(chunk)
            except Exception as e:
                self.logger.error(
                    f"Event handling failed: {e!s}",
                    context={
                        "event_type": event.type.value,
                        "source_id": event.source_id,
                    },
                    exc_info=sys.exc_info()
                )
                await self.hook.trigger(HookType.ON_ERROR, e)
                raise
            finally:
                await self.hook.trigger(HookType.AFTER_RUN)
                if self.session is not None and self.session.dir is not None:
                    try:
                        self.session.save()
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to save session metadata: {e}",
                            context={"session_id": self.session.id},
                        )
                self.logger.info("Event handling completed")
                self.logger.clear_trace_id()

    # ========================================================================
    # Execution: Event Loop Lifecycle
    # ========================================================================
    async def start(self):
        if self._loop_running:
            self.logger.warning("Agent already running, start ignored")
            return

        with self.logger.span("agent_start"):
            self.logger.info("Agent event loop started")
            self._stop_event.clear()
            self._interrupt_event.clear()
            self._loop_running = True
            self.state = AgentState.Waiting
            await self._emit_state()

            try:
                await self.input.start()
            except Exception as e:
                self.logger.error(
                    f"Failed to start input channel: {e}",
                    exc_info=True,
                )
                self._loop_running = False
                self.state = AgentState.Error
                await self._emit_state()
                return

            _exit_reason = "unknown"
            try:
                while self._loop_running:
                    event_task = asyncio.create_task(self.input.queue.get())
                    stop_task = asyncio.create_task(self._stop_event.wait())
                    try:
                        done, pending = await asyncio.wait(
                            {event_task, stop_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to get event from queue: {e}",
                            exc_info=True,
                        )
                        _exit_reason = "queue_error"
                        break

                    for task in pending:
                        task.cancel()
                    for task in pending:
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                    if self._stop_event.is_set() or not self._loop_running:
                        _exit_reason = "stopped"
                        break

                    if event_task not in done:
                        _exit_reason = "stopped"
                        break

                    event = event_task.result()
                    self.state = AgentState.Running
                    await self._emit_state()
                    if self._stop_event.is_set() or not self._loop_running:
                        _exit_reason = "stopped"
                        break
                    try:
                        await self._handle_event(event)
                    except Exception as e:
                        self.logger.error(
                            f"Unhandled error in event loop: {e}",
                            exc_info=True,
                        )
                        try:
                            self.state = AgentState.Error
                            await self._emit({'type': 'event', 'event_type': 'error', 'content': str(e)})
                            await self._emit_state()
                        except Exception:
                            self.logger.error(
                                "Failed to emit error/agent_state in event loop handler",
                                exc_info=True,
                            )
                        _exit_reason = "error"
                        break
                    if self._loop_running and self.state != AgentState.Error:
                        self.state = AgentState.Waiting
                        await self._emit_state()
            finally:
                await self.input.stop()
                self._loop_running = False
                if self.state != AgentState.Error:
                    self.state = AgentState.Ready
                    try:
                        await self._emit_state()
                    except Exception:
                        self.logger.error(
                            "Failed to emit agent_state 'ready'",
                            exc_info=True,
                        )
                self.logger.info(
                    "Agent event loop stopped",
                    context={"exit_reason": _exit_reason}
                )

    async def interrupt(self):
        self._interrupt_event.set()
        for task in list(self._active_tool_tasks):
            if not task.done():
                task.cancel()

    async def stop(self):
        with self.logger.span("agent_stop"):
            self.logger.info("Agent stopping")
            self._stop_event.set()
            self._loop_running = False
            self._interrupt_event.set()
            for task in list(self._active_tool_tasks):
                if not task.done():
                    task.cancel()
            await self.input.stop()

    # ========================================================================
    # output callback
    # ========================================================================
    def on_output(self, callback: Callable):
        self._output_callback = callback

    async def _emit(self, chunk: dict):
        """Emit a chunk to the output callback.

        Top-level ``"type"`` field is either ``"stream_chunk"`` or ``"event"``.

        **stream_chunk** (via ``"chunk_type"`` discriminator):

        * ``{"type": "stream_chunk", "chunk_type": "text", "content": str}``
        * ``{"type": "stream_chunk", "chunk_type": "thinking", "content": str}``
        * ``{"type": "stream_chunk", "chunk_type": "completed_tool_use", "content": ToolUseBlock}``
        * ``{"type": "stream_chunk", "chunk_type": "completed_message", "content": ModelMessage}``
        * ``{"type": "stream_chunk", "chunk_type": "tool_results", "content": list[ToolMessage]}``

        **event** (via ``"event_type"`` discriminator):

        * ``{"type": "event", "event_type": "user_input", "source_id": str, "content": str}``
        * ``{"type": "event", "event_type": "timer_input", "source_id": str, "content": str}``
        * ``{"type": "event", "event_type": "agent_input", "source_id": str, "content": str}``
        * ``{"type": "event", "event_type": "interrupted", "content": str}``
        * ``{"type": "event", "event_type": "agent_state", "state": AgentState}`` —
          when ``self.session`` exists, ``"context_tokens": int`` field is automatically appended
        * ``{"type": "event", "event_type": "error", "content": str}``
        """
        if chunk.get("event_type") == "agent_state" and self.session:
            chunk["context_tokens"] = self.session.get_visible_token_count()
        if self._output_callback:
            if asyncio.iscoroutinefunction(self._output_callback):
                await self._output_callback(chunk)
            else:
                self._output_callback(chunk)

    async def _emit_state(self):
        await self._emit({'type': 'event', 'event_type': 'agent_state', 'state': self.state})


class SubAgent:
    def __init__(self, model: Model, tools: list[Tool] | None = None, system_prompt: str = "",
                skills: list[Skill] | None = None, name: str | None = None,
                logger: AgentLogger | None = None):
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
                existing = self.tools.get(t.name)
                if existing is not None and existing is not t:
                    raise ValueError(f"Duplicate tool name: {t.name}")
                self.tools[t.name] = t

        self._force_stop = False

    def stop(self):
        self._force_stop = True

    def add_tools(self, tools: list[Tool]):
        for t in tools:
            existing = self.tools.get(t.name)
            if existing is not None and existing is not t:
                raise ValueError(f"Duplicate tool name: {t.name}")
            self.tools[t.name] = t
        self.tools = dict(sorted(self.tools.items(), key=lambda item: item[0]))

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
        skill_short_prompt = [f'- name: {s.name}, Path: {s.path}/SKILL.md, Description: {s.description}' for s in self.skills.values()]
        return '\n'.join(skill_system_prompt + skill_short_prompt)

    def add_skills(self, skills: list[Skill]):
        self.skills.update({s.name: s for s in skills})
        new_prompt = '\n'.join([f'- name: {s.name}, Path: {s.path}/SKILL.md, Description: {s.description}' for s in skills])
        self.skill_prompt += new_prompt

    def remove_skills(self, skill_names: list[str]):
        """Remove skills with specified names, and refresh skill_prompt."""
        if not skill_names:
            return
        for name in skill_names:
            self.skills.pop(name, None)
        if not self.skills:
            self.skill_prompt = ''
        else:
            self.skill_prompt = self._load_skill_prompt()

    async def tool_execute(self, tool_use: ToolUseBlock) -> ToolMessage:
        tool = self.tools.get(tool_use.name)

        if tool is None:
            content: str | list[ContentBlock] = f"Unknown tool: {tool_use.name}"
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
                        raw_result = await asyncio.to_thread(tool.invoke, tool_use.input)

                    if isinstance(raw_result, str):
                        content = raw_result
                    elif isinstance(raw_result, list):
                        content = cast(list[ContentBlock], raw_result)
                    else:
                        content = json.dumps(raw_result, ensure_ascii=False)

                    self.logger.debug(
                        f"Tool '{tool_use.name}' completed successfully",
                        context={"tool_name": tool_use.name}
                    )
                except Exception as e:
                    content = f"Tool invocation error: {e!s}"
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

    def _normalize_input(self, messages: list[Message] | Message | str) -> list[Message]:
        if isinstance(messages, str):
            return [HumanMessage(messages)]
        if isinstance(messages, Message):
            return [messages]
        return list(messages)

    async def run(self, messages: list[Message] | Message | str) -> str:
        messages = self._normalize_input(messages)
        tools = list(self.tools.values())
        final_result: ModelMessage | None = None

        trace = getattr(self.logger, "trace", None)
        trace_context = trace(inherit=True) if trace else contextlib.nullcontext()
        with trace_context:
            self.logger.info(
                "SubAgent run started",
                context={"agent_name": self.name}
            )
            with self.logger.span("subagent_run"):
                while True:
                    if self._force_stop:
                        self.logger.debug(
                            "SubAgent forced to stop",
                            context={"agent_name": self.name}
                        )
                        break

                    model_input = Model_Input(
                        prompt=self.system_prompt + self.skill_prompt,
                        tools=tools,
                        messages=messages,
                    )
                    try:
                        model_result = await self.model.async_invoke(model_input)
                    except Exception as e:
                        self.logger.error(
                            f"SubAgent model run failed: {e!s}",
                            context={"agent_name": self.name, "error_type": type(e).__name__},
                            exc_info=sys.exc_info()
                        )
                        raise

                    if isinstance(model_result, str):
                        return model_result

                    result = model_result
                    messages.append(result)
                    self.logger.debug(
                        "Model response received",
                        context={"agent_name": self.name, "stop_reason": result.stop_reason}
                    )

                    if result.stop_reason == 'tool_use':
                        for tool_use in result.tool_calls:
                            tool_msg = await self.tool_execute(tool_use)
                            messages.append(tool_msg)
                            if self._force_stop:
                                break
                    elif result.stop_reason == 'end_turn':
                        final_result = result
                        break
                    else:
                        error_msg = f"SubAgent stop reason: {result.stop_reason}"
                        self.logger.error(
                            error_msg,
                            context={"agent_name": self.name, "stop_reason": result.stop_reason}
                        )
                        raise ValueError(error_msg)

            if final_result is None:
                return ""

            if isinstance(final_result.content, list):
                parts = [b.text for b in final_result.content if isinstance(b, TextBlock)]
                text = '\n'.join(parts)
            else:
                text = str(final_result.content)

            self.logger.info(
                "SubAgent run completed",
                context={"agent_name": self.name}
            )
            return text
