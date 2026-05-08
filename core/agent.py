import asyncio
import json
import shutil
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import  List
from uuid import uuid4 as uuid

from .model import Model, Model_Input
from .tool import Tool, tool
from .message import *
from .skill import Skill
from .agenthook import AgentHook, HookType, Hook
from .messagebus import MessageBus

@dataclass
class AgentConfig:
    model: List[Model]
    base_path: Path | str = Path.cwd()
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
        self.base_path = Path(self.base_path) / self.name


@dataclass
class AgentState:
    Ready = 'Ready'
    Running = 'Running'


class Agent:
    def __init__(self,agent_config:AgentConfig):
        self.name = agent_config.name
        self.model = agent_config.model

        self.base_path = agent_config.base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.system_prompt_path = self.base_path / 'system_prompt.md'
        self.system_prompt = agent_config.system_prompt
        if not self.system_prompt_path.exists():
            self.system_prompt_path.write_text(agent_config.system_prompt, encoding='utf-8')
        self.session_path = self.base_path / 'session'
        self.session_path.mkdir(parents=True, exist_ok=True)

        self.session = agent_config.session or Session.create(self.session_path)

        self.tools: dict[str, Tool] = {}
        if agent_config.tools:
            self.add_tools(agent_config.tools)

        self.skills: dict[str, Skill] = {}
        if agent_config.skills:
            self._add_load_skills_tool()
            for skill in agent_config.skills:
                self.skills[skill.name] = skill
        self.skill_prompt = self._load_skill_prompt()
        
        self.hook = agent_config.hook if agent_config.hook else AgentHook()
        if self.hook:
            self.hook.set_context(self)
        
        self.state = AgentState.Ready

    def change_name(self, name: str):
        self.name = name
    
    def choose_model(self):
        #TODO: 实现模型选择逻辑
        return self.model[0]
    
    def change_model(self, model: List[Model]):
        self.model = model
    
    def change_base_path(self, path: Path | str):
        new_base = Path(path)
        old_base = self.base_path
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

        self.base_path = new_base
        self.system_prompt_path = new_system_prompt
        self.session_path = new_session
    
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

        dst_dir = self.session_path / session_id
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
        
        ever_used_tools = self.session.ever_used_tools()
        for tool_name in ever_used_tools:
            if tool_name not in self.tools:
                print(f'Warning: Tool {tool_name} not found in agent tools')

    async def new_session(self):
        await self.hook.trigger(HookType.NEW_SESSION)
        self.session.save()
        self.session = Session.create(self.session_path)
    
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
        
        if tool:
            try:
                if tool.is_async:
                    result = await tool.async_invoke(tool_use.input)
                else:
                    result = tool.invoke(tool_use.input)
                if isinstance(result, str):
                    content = result
                else:
                    content = json.dumps(result, ensure_ascii=False)                 
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unknown tool:{tool_use.name}'
            
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
        prompt = self.system_prompt + self.skill_prompt
        messages = self.session.messages
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
                model = self.choose_model()
                async for chunk in model.async_stream_invoke(model_input): 
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
                        await self.hook.trigger(HookType.ON_MESSAGE, content)
                        self.session.add_message(content)
                        yield chunk
                        break
                
                if interrupted:
                    break
                
                if stop_reason in ['tool_use', 'tool_calls']:
                    tool_results = await asyncio.gather(*tool_tasks)
                    yield {'type': 'tool_results', 'content': tool_results}
                    self.session.add_message(tool_results)
                elif stop_reason in ['end_turn', 'stop']:
                    break
                else:
                    raise ValueError(f"Stop reason: {stop_reason}")
        except Exception as e:
            raise e
                 
    async def run(self, human_msg:HumanMessage):
        self.state = AgentState.Running
        self.session.add_message(human_msg)
        await self.hook.trigger(HookType.AFTER_INPUT, human_msg)
        try:
            async for chunk in self.stream_tool_loop():
                        yield chunk
        except Exception as e:
            raise e
        finally:
            self.session.save()
            self.state = AgentState.Ready
            await self.hook.trigger(HookType.AFTER_RUN)


class SubAgent:
    def __init__(self, model: Model, tools: List[Tool] = None, system_prompt: str = "",
                skills: List[Skill] = None, agent_id: str = None):
        self.model = model
        self.system_prompt = system_prompt
        self.skills = skills or []
        self.skill_prompt = self._load_skill_prompt()
        self._agent_id = agent_id or f'sub_{id(self)}'

        self.tools: dict[str, Tool] = {}
        if tools:
            for t in tools:
                self.tools[t.name] = t


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

        if tool:
            try:
                if tool.is_async:
                    result = await tool.async_invoke(tool_use.input)
                else:
                    result = tool.invoke(tool_use.input)
                content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            except Exception as e:
                content = f'Tool invocation error {e}'
        else:
            content = f'Unknown tool: {tool_use.name}'

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

        while True:
            model_input = Model_Input(
                prompt=self.system_prompt + self.skill_prompt,
                tools=tools,
                messages=messages,
            )
            result = await self.model.async_invoke(model_input)
            messages.append(result)

            if result.stop_reason in ['tool_use', 'tool_calls']:
                for tool_use in result.tool_calls:
                    tool_msg = await self.tool_execute(tool_use)
                    messages.append(tool_msg)
            elif result.stop_reason in ['end_turn', 'stop']:
                break
            else:
                raise ValueError(f"SubAgent stop reason: {result.stop_reason}")

        if isinstance(result.content, list):
            parts = [b.text for b in result.content if isinstance(b, TextBlock)]
            return '\n'.join(parts)
        return str(result.content)






