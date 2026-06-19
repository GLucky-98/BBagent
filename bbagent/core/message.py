import copy
import json
from typing import List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import uuid

__all__ = [
    'Session',
    'Message', 
    'HumanMessage', 
    'ModelMessage', 
    'ToolMessage',
    'ContentBlock',
    'TextBlock',
    'ImageBlock',
    'ToolUseBlock',
    'estimate_message_tokens'
]


class ContentBlock:
    def to_dict(self) -> dict:
        raise NotImplementedError

    @staticmethod
    def from_dict(data: dict) -> 'ContentBlock':
        block_type = data.get('type', '')
        if block_type == 'text':
            return TextBlock(text=data['text'])
        elif block_type == 'image':
            return ImageBlock(data=data['data'], image_type=data.get('image_type', 'base64'))
        elif block_type == 'tooluse':
            return ToolUseBlock(id=data['id'], name=data['name'], input=data['input'])
        raise ValueError(f"Unknown content block type: {block_type}")


@dataclass
class TextBlock(ContentBlock):
    text: str
    type: str = "text"

    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text}

@dataclass
class ImageBlock(ContentBlock):
    data: str
    image_type: str = 'base64'
    type: str = "image"

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data, "image_type": self.image_type}

@dataclass
class AudioBlock(ContentBlock):
    pass

@dataclass
class DocumentBlock(ContentBlock):
    pass

@dataclass
class ToolUseBlock(ContentBlock):
    id: str
    name: str
    input: dict
    type: str = "tooluse"

    def to_dict(self) -> dict:
        return {"type": self.type, "id": self.id, "name": self.name, "input": self.input}


class Message:
    @staticmethod
    def _serialize_content(content):
        if isinstance(content, str):
            return content
        return [block.to_dict() for block in content]

    @staticmethod
    def _deserialize_content(content_data):
        if isinstance(content_data, str):
            return content_data
        return [ContentBlock.from_dict(block) for block in content_data]

    def to_dict(self) -> dict:
        raise NotImplementedError

    @staticmethod
    def from_dict(data: dict) -> 'Message':
        role = data.get('role', '')
        if role == 'user':
            return HumanMessage._from_dict(data)
        elif role == 'model':
            return ModelMessage._from_dict(data)
        elif role == 'tool':
            return ToolMessage._from_dict(data)
        raise ValueError(f"Unknown message role: {role}")


@dataclass
class HumanMessage(Message):
    content: List[ContentBlock] | str
    role: str = "user"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": Message._serialize_content(self.content),
            "timestamp": self.timestamp,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> 'HumanMessage':
        return cls(
            content=Message._deserialize_content(data['content']),
            timestamp=data.get('timestamp', 0),
        )


@dataclass
class ToolMessage(Message):
    id: str
    name: str
    content: List[ContentBlock] | str
    role: str = "tool"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "id": self.id,
            "name": self.name,
            "content": Message._serialize_content(self.content),
            "timestamp": self.timestamp,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> 'ToolMessage':
        return cls(
            id=data['id'],
            name=data['name'],
            content=Message._deserialize_content(data['content']),
            timestamp=data.get('timestamp', 0),
        )


@dataclass
class ModelMessage(Message):
    id: str
    content: List[ContentBlock] | str 
    stop_reason: str
    usage_data: dict
    raw_json: str = ''
    thinking: str = ''
    thinking_signature: str = ''
    tool_calls: List[ToolUseBlock] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    role: str = "model"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "id": self.id,
            "content": Message._serialize_content(self.content),
            "stop_reason": self.stop_reason,
            "usage_data": self.usage_data,
            "raw_json": self.raw_json,
            "thinking": self.thinking,
            "thinking_signature": self.thinking_signature,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "timestamp": self.timestamp,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> 'ModelMessage':
        return cls(
            id=data['id'],
            content=Message._deserialize_content(data['content']),
            stop_reason=data.get('stop_reason', ''),
            usage_data=data.get('usage_data', {}),
            raw_json=data.get('raw_json', ''),
            thinking=data.get('thinking', ''),
            thinking_signature=data.get('thinking_signature', ''),
            tool_calls=[ContentBlock.from_dict(tc) for tc in data.get('tool_calls', [])],
            input_tokens=data.get('input_tokens', 0),
            output_tokens=data.get('output_tokens', data.get('token_num', 0)),
            timestamp=data.get('timestamp', 0),
        )


def estimate_message_tokens(msg: Message) -> int:
    serialized = json.dumps(msg.to_dict(), ensure_ascii=False)
    return max(1, len(serialized.encode('utf-8')) // 3)


@dataclass
class Turn:
    messages: List[Message] = field(default_factory=list)
    key_content: List[str] = field(default_factory=list)
    is_summarized: bool = False
    summary: str = ''
    summary_group_id: str = ''
    skip_summary: bool = False
    token_count: int = 0
    ever_used_tools: List[str] = field(default_factory=list)
    start_timestamp: int = 0
    end_timestamp: int = 0
    memory_extracted: bool = False

    @property
    def is_complete(self) -> bool:
        return bool(self.messages and
                    isinstance(self.messages[-1], ModelMessage) and
                    self.messages[-1].stop_reason == 'end_turn')

    def add_message(self, msg: Message):
        self.messages.append(msg)

    DEFAULT_MERGE_HEADER = "[Context from an incomplete previous turn - merged into this message]"
    CURRENT_REQUEST_LABEL = "[Current request]"

    @staticmethod
    def _role_label(msg: Message) -> str:
        if isinstance(msg, HumanMessage):
            return "[User]"
        if isinstance(msg, ModelMessage):
            return "[Assistant]"
        if isinstance(msg, ToolMessage):
            name = getattr(msg, 'name', '') or ''
            return f"[Tool({name})]" if name else "[Tool]"
        return "[Unknown]"

    @staticmethod
    def _normalize_content(content) -> List[ContentBlock]:
        if isinstance(content, str):
            return [TextBlock(text=content)] if content else []
        return list(content)

    def _message_to_blocks(self, msg: Message) -> List[ContentBlock]:
        role = self._role_label(msg)
        result: List[ContentBlock] = []

        content_blocks = self._normalize_content(msg.content)
        text_emitted = False

        for block in content_blocks:
            if isinstance(block, TextBlock):
                if block.text:
                    result.append(TextBlock(text=f"{role} {block.text}"))
                    text_emitted = True
                continue
            if not text_emitted:
                result.append(TextBlock(text=role))
                text_emitted = True
            result.append(block)

        if isinstance(msg, ModelMessage):
            for tc in msg.tool_calls:
                input_str = json.dumps(tc.input, ensure_ascii=False)
                result.append(TextBlock(text=f"{role} [ToolCall {tc.name}({input_str})]"))

        if not text_emitted and not (isinstance(msg, ModelMessage) and msg.tool_calls):
            result.append(TextBlock(text=role))

        return result

    def to_merged_blocks(self, header: str = None) -> List[ContentBlock]:
        if header is None:
            header = self.DEFAULT_MERGE_HEADER
        blocks: List[ContentBlock] = [
            TextBlock(text=header),
            TextBlock(text=""),
        ]
        for msg in self.messages:
            blocks.extend(self._message_to_blocks(msg))
        return blocks


class Session:
    def __init__(self, dir: str | Path = None, id: str = None, turns: List[Turn] = None):
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.id = id if id else self.timestamp + '_' + uuid.uuid4().hex[:16]
        self.dir = Path(dir) if dir else None
        self.turns = turns if turns else []

        self.window_start = 0
        self.compress_turn_count = 0
        self.total_input_cost_tokens = 0
        self.total_output_cost_tokens = 0
        self._prev_context_total: int = 0

        # Fork 来源追踪
        self.parent_session_id: str = ''
        self.fork_turn_index: int = -1

    @property
    def messages(self) -> List[Message]:
        result = []
        for turn in self.turns[self.window_start:]:
            result.extend(turn.messages)
        return result

    @property
    def ever_used_tools(self) -> List[str]:
        seen = set()
        result = []
        for turn in self.turns:
            for tool in turn.ever_used_tools:
                if tool not in seen:
                    seen.add(tool)
                    result.append(tool)
        return result

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def _messages_path(self) -> Path:
        return self.dir / f'{self.id}.jsonl'

    def _metadata_path(self) -> Path:
        return self.dir / f'{self.id}.md'

    @classmethod
    def create(cls, session_dir: str | Path) -> 'Session':
        id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '_' + uuid.uuid4().hex[:16]
        session_path = Path(session_dir) / id
        session_path.mkdir(parents=True, exist_ok=True)

        session = cls(dir=session_path, id=id)
        session._messages_path().touch()
        session._write_metadata()
        return session

    def fork(self, session_root: str | Path = None, at: int = None) -> 'Session':
        """基于当前 Session 创建一个独立的副本 Session。

        Args:
            session_root: fork 副本的根目录；None 时使用默认的 {self.dir}/fork
            at: 复制到第几个 turn（含）。None 表示复制所有 turn；
                支持负数索引（-1 表示最后一个 turn）。

        Returns:
            与原 Session 完全独立的新 Session 实例。

        Raises:
            IndexError: at 越界或 session 没有任何 turn
            ValueError: 纯内存 session（dir=None）无法 fork
        """
        n = len(self.turns)
        if at is not None:
            if n == 0:
                raise IndexError("Cannot fork at a turn index: session has no turns")
            if at < 0:
                at = n + at
            if at < 0 or at >= n:
                raise IndexError(f"Turn index {at} out of range, session has {n} turns")
            end = at + 1
        else:
            end = n

        fork_dir = Path(session_root) if session_root else (self.dir / 'fork') if self.dir else None
        if not fork_dir:
            raise ValueError("Cannot fork an in-memory session, provide session_root or persist the session first")

        new_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_id = f'{new_timestamp}_{uuid.uuid4().hex[:16]}'
        fork_path = fork_dir / new_id
        fork_path.mkdir(parents=True, exist_ok=True)

        new_turns = [copy.deepcopy(turn) for turn in self.turns[:end]]

        new_session = Session(dir=fork_path, id=new_id, turns=new_turns)
        new_session.window_start = 0
        new_session.compress_turn_count = sum(
            1 for turn in new_turns if turn.is_summarized
        )
        new_session.total_input_cost_tokens = sum(
            msg.input_tokens for turn in new_turns
            for msg in turn.messages if isinstance(msg, ModelMessage)
        )
        new_session.total_output_cost_tokens = sum(
            msg.output_tokens for turn in new_turns
            for msg in turn.messages if isinstance(msg, ModelMessage)
        )

        new_session._rebuild_token_counts()

        for turn in new_session.turns:
            if turn.is_complete:
                new_session._flush_turn(turn)

        new_session._write_metadata()

        return new_session

    def _flush_turn(self, turn: Turn):
        if not self.dir:
            return
        with open(self._messages_path(), 'a', encoding='utf-8') as f:
            for msg in turn.messages:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + '\n')

    def _rebuild_token_counts(self):
        self._prev_context_total = 0
        for turn in self.turns:
            for msg in turn.messages:
                if isinstance(msg, ModelMessage):
                    current_total = msg.input_tokens + msg.output_tokens
                    turn.token_count = current_total - self._prev_context_total
                    if msg.stop_reason == 'end_turn':
                        self._prev_context_total = current_total

    def add_message(self, message: Message | List[Message]):
        messages = message if isinstance(message, list) else [message]
        for msg in messages:
            if isinstance(msg, HumanMessage):
                prefix_blocks: List[ContentBlock] = []
                inherited_tools: List[str] = []
                if self.turns and not self.turns[-1].is_complete:
                    old_turn = self.turns[-1]
                    prefix_blocks = old_turn.to_merged_blocks()
                    inherited_tools = list(old_turn.ever_used_tools)
                    self.turns.pop()

                new_blocks = Turn._normalize_content(msg.content)
                if prefix_blocks and new_blocks:
                    msg.content = prefix_blocks + [
                        TextBlock(text=Turn.CURRENT_REQUEST_LABEL),
                    ] + new_blocks
                elif prefix_blocks:
                    msg.content = prefix_blocks
                else:
                    msg.content = new_blocks

                turn = Turn()
                turn.start_timestamp = msg.timestamp
                turn.ever_used_tools = list(dict.fromkeys(inherited_tools))
                turn.messages.append(msg)
                self.turns.append(turn)
            elif not self.turns or self.turns[-1].is_complete:
                continue
            else:
                last_turn = self.turns[-1]
                last_turn.add_message(msg)
                if isinstance(msg, ModelMessage):
                    current_total = msg.input_tokens + msg.output_tokens
                    last_turn.token_count = current_total - self._prev_context_total
                    if msg.stop_reason == 'end_turn':
                        last_turn.end_timestamp = msg.timestamp
                        self._prev_context_total = current_total
                        self._flush_turn(last_turn)
                    self.total_input_cost_tokens += msg.input_tokens
                    self.total_output_cost_tokens += msg.output_tokens
                elif isinstance(msg, ToolMessage):
                    if msg.name and msg.name not in last_turn.ever_used_tools:
                        last_turn.ever_used_tools.append(msg.name)

    @staticmethod
    def _build_inject_text(summaries: List[str], keys: List[str]) -> str:
        parts = []
        if summaries:
            parts.append("[Historical Conversation Summary]")
            parts.append("\n---\n".join(summaries))
        if keys:
            parts.append("[Key Information Preserved]")
            for k in keys:
                parts.append(f"- {k}")
        return "\n\n".join(parts)

    def get_visible_context(self) -> List[Message]:
        turns = self.turns[self.window_start:]
        collected_summaries = []
        collected_keys = []
        seen_groups = set()
        seen_keys = set()
        inject_idx = None

        for i, turn in enumerate(turns):
            if turn.is_summarized:
                if turn.skip_summary:
                    for key in turn.key_content:
                        if key not in seen_keys:
                            seen_keys.add(key)
                            collected_keys.append(key)
                else:
                    if turn.summary and turn.summary_group_id not in seen_groups:
                        seen_groups.add(turn.summary_group_id)
                        collected_summaries.append(turn.summary)
                    for key in turn.key_content:
                        if key not in seen_keys:
                            seen_keys.add(key)
                            collected_keys.append(key)
            else:
                inject_idx = i
                break

        if inject_idx is None:
            if not collected_summaries and not collected_keys:
                return []
            inject_text = self._build_inject_text(collected_summaries, collected_keys)
            return [HumanMessage(content=inject_text)]

        if not collected_summaries and not collected_keys:
            result = []
            for turn in turns:
                result.extend(turn.messages)
            return result

        inject_text = self._build_inject_text(collected_summaries, collected_keys)
        result = []
        target_turn = turns[inject_idx]
        target_msgs = list(target_turn.messages)
        if target_msgs:
            first_msg = target_msgs[0]
            if isinstance(first_msg, HumanMessage):
                if isinstance(first_msg.content, str):
                    new_first = HumanMessage(
                        content=inject_text + first_msg.content,
                        timestamp=first_msg.timestamp
                    )
                else:
                    new_first = HumanMessage(
                        content=[TextBlock(text=inject_text)] + list(first_msg.content),
                        timestamp=first_msg.timestamp
                    )
                target_msgs[0] = new_first
        result.extend(target_msgs)
        for turn in turns[inject_idx + 1:]:
            result.extend(turn.messages)
        return result

    def get_visible_token_count(self) -> int:
        turns = self.turns[self.window_start:]
        if not turns:
            return 0

        total = 0
        seen_groups = set()
        seen_keys = set()

        for turn in turns:
            if turn.is_summarized:
                if not turn.skip_summary:
                    if turn.summary and turn.summary_group_id not in seen_groups:
                        seen_groups.add(turn.summary_group_id)
                        total += estimate_message_tokens(
                            HumanMessage(content=turn.summary)
                        )
                for key in turn.key_content:
                    if key not in seen_keys:
                        seen_keys.add(key)
                        total += estimate_message_tokens(
                            HumanMessage(content=key)
                        )
            else:
                if turn.is_complete:
                    total += turn.token_count
                else:
                    for msg in turn.messages:
                        total += estimate_message_tokens(msg)

        return total

    def get_turn(self, n: int) -> Turn:
        if not self.turns:
            raise IndexError("No turns available in this session")
        if n < 0:
            n = len(self.turns) + n
        if n < 0 or n >= len(self.turns):
            raise IndexError(f"Turn index {n} out of range, session has {len(self.turns)} turns")
        return self.turns[n]

    def save(self):
        if not self.dir:
            raise ValueError("Session dir not set, use Session.create() for persistent sessions")
        self._write_metadata()

    def _write_metadata(self):
        content_lines = [f'# Session: {self.id}', '']
        content_lines.append(f'id: {self.id}')
        content_lines.append(f'timestamp: {self.timestamp}')
        content_lines.append(f'window_start: {self.window_start}')
        content_lines.append(f'compress_turn_count: {self.compress_turn_count}')
        content_lines.append(f'total_input_cost_tokens: {self.total_input_cost_tokens}')
        content_lines.append(f'total_output_cost_tokens: {self.total_output_cost_tokens}')
        content_lines.append(f'turn_count: {len(self.turns)}')
        if self.parent_session_id:
            content_lines.append(f'parent_session_id: {self.parent_session_id}')
        if self.fork_turn_index >= 0:
            content_lines.append(f'fork_turn_index: {self.fork_turn_index}')
        content_lines.append('')
        content_lines.append('---')
        content_lines.append('')

        for i, turn in enumerate(self.turns):
            label = f'## Turn {i}'
            if not turn.is_complete:
                label += ' (incomplete)'
            content_lines.append(label)
            content_lines.append('')
            content_lines.append(f'is_summarized: {str(turn.is_summarized).lower()}')
            content_lines.append(f'summary: {turn.summary if turn.summary else "(empty)"}')
            content_lines.append(f'key_content: {json.dumps(turn.key_content, ensure_ascii=False) if turn.key_content else "(empty)"}')
            content_lines.append(f'summary_group_id: {turn.summary_group_id}')
            content_lines.append(f'skip_summary: {str(turn.skip_summary).lower()}')
            tools_str = ', '.join(turn.ever_used_tools) if turn.ever_used_tools else '(none)'
            content_lines.append(f'ever_used_tools: {tools_str}')
            content_lines.append(f'start_timestamp: {turn.start_timestamp}')
            content_lines.append(f'end_timestamp: {turn.end_timestamp if turn.end_timestamp else "(none)"}')
            content_lines.append(f'token_count: {turn.token_count}')
            content_lines.append(f'memory_extracted: {str(turn.memory_extracted).lower()}')
            content_lines.append('')

        self._metadata_path().write_text('\n'.join(content_lines), encoding='utf-8')

    @classmethod
    def load(cls, session_id: str, session_dir: str | Path) -> 'Session':
        session_path = Path(session_dir)
        messages_file = session_path / f'{session_id}.jsonl'
        metadata_file = session_path / f'{session_id}.md'

        if not messages_file.exists():
            raise FileNotFoundError(f"Messages file not found: {messages_file}")
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        turns = []
        current_turn = None
        with open(messages_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                msg = Message.from_dict(data)

                if isinstance(msg, HumanMessage):
                    current_turn = Turn()
                    current_turn.start_timestamp = msg.timestamp
                    current_turn.add_message(msg)
                    turns.append(current_turn)
                else:
                    if current_turn is None:
                        current_turn = Turn()
                        turns.append(current_turn)
                    current_turn.add_message(msg)
                    if isinstance(msg, ModelMessage) and msg.stop_reason == 'end_turn':
                        current_turn.end_timestamp = msg.timestamp
                    elif isinstance(msg, ToolMessage) and msg.name:
                        if msg.name not in current_turn.ever_used_tools:
                            current_turn.ever_used_tools.append(msg.name)

        session = cls(dir=session_path, id=session_id, turns=turns)
        metadata = cls._parse_metadata(metadata_file)
        session.window_start = int(metadata.get('window_start', 0))
        session.compress_turn_count = int(metadata.get('compress_turn_count', 0))
        session.total_input_cost_tokens = int(metadata.get('total_input_cost_tokens', 0))
        session.total_output_cost_tokens = int(metadata.get('total_output_cost_tokens', 0))
        session.parent_session_id = metadata.get('parent_session_id', '')
        fork_idx = metadata.get('fork_turn_index', '')
        session.fork_turn_index = int(fork_idx) if fork_idx != '' else -1

        for i, turn_meta in enumerate(metadata.get('turns_metadata', [])):
            if i < len(turns):
                turn = turns[i]
                turn.is_summarized = turn_meta.get('is_summarized', 'false') == 'true'
                turn.summary = '' if turn_meta.get('summary', '') == '(empty)' else turn_meta.get('summary', '')
                key_raw = turn_meta.get('key_content', '(empty)')
                turn.key_content = json.loads(key_raw) if key_raw != '(empty)' else []
                turn.summary_group_id = turn_meta.get('summary_group_id', '')
                turn.skip_summary = turn_meta.get('skip_summary', 'false') == 'true'
                tools_raw = turn_meta.get('ever_used_tools', '(none)')
                turn.ever_used_tools = [t.strip() for t in tools_raw.split(',') if t.strip()] if tools_raw != '(none)' else []
                turn.start_timestamp = int(turn_meta.get('start_timestamp', 0))
                end_ts = turn_meta.get('end_timestamp', '(none)')
                turn.end_timestamp = 0 if end_ts == '(none)' else int(end_ts)
                turn.token_count = int(turn_meta.get('token_count', 0))
                turn.memory_extracted = turn_meta.get('memory_extracted', 'false') == 'true'

        session._rebuild_token_counts()

        return session

    @staticmethod
    def _parse_metadata(md_path: Path) -> dict:
        text = md_path.read_text(encoding='utf-8')
        result = {}
        turns_metadata = []
        current_turn = None

        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('## Turn'):
                if current_turn is not None:
                    turns_metadata.append(current_turn)
                current_turn = {}
                continue

            if not stripped or stripped.startswith('#') or stripped == '---':
                continue

            if ':' in stripped and current_turn is not None:
                key, _, value = stripped.partition(':')
                current_turn[key.strip()] = value.strip()
            elif ':' in stripped:
                key, _, value = stripped.partition(':')
                key, value = key.strip(), value.strip()
                if key in ('window_start', 'compress_turn_count',
                           'total_input_cost_tokens', 'total_output_cost_tokens', 'turn_count'):
                    result[key] = value
                else:
                    result[key] = value

        if current_turn is not None:
            turns_metadata.append(current_turn)

        result['turns_metadata'] = turns_metadata
        return result
