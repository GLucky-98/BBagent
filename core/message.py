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
    'ToolUseBlock'
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
    token_num: int = 0
    role: str = "user"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": Message._serialize_content(self.content),
            "token_num": self.token_num,
            "timestamp": self.timestamp,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> 'HumanMessage':
        return cls(
            content=Message._deserialize_content(data['content']),
            token_num=data.get('token_num', 0),
            timestamp=data.get('timestamp', 0),
        )


@dataclass
class ToolMessage(Message):
    id: str
    name: str
    content: List[ContentBlock] | str
    token_num: int = 0 
    role: str = "tool"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "id": self.id,
            "name": self.name,
            "content": Message._serialize_content(self.content),
            "token_num": self.token_num,
            "timestamp": self.timestamp,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> 'ToolMessage':
        return cls(
            id=data['id'],
            name=data['name'],
            content=Message._deserialize_content(data['content']),
            token_num=data.get('token_num', 0),
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
    tool_calls: List[ToolUseBlock] = field(default_factory=list)
    input_tokens: int = 0
    token_num: int = 0
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
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "input_tokens": self.input_tokens,
            "token_num": self.token_num,
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
            tool_calls=[ContentBlock.from_dict(tc) for tc in data.get('tool_calls', [])],
            input_tokens=data.get('input_tokens', 0),
            token_num=data.get('token_num', 0),
            timestamp=data.get('timestamp', 0),
        )


class Session:
    def __init__(self, path: str | Path = None, id: str = None, messages: List[Message] = None):
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.id = id if id else self.timestamp + '_' + uuid.uuid4().hex[:8]
        self.path = Path(path) if path else None
        self.messages = messages if messages else []
        
        self.total_tokens = 0
        self.compress_num = 0
        self.summary = ''
        self.compact_summary = []
        self.ever_used_tools = []

    @classmethod
    def create(cls, session_path: str | Path) -> 'Session':
        id =datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '_' + uuid.uuid4().hex[:8]
        session_dir = Path(session_path) / id
        session_dir.mkdir(parents=True, exist_ok=True)

        session = cls(path=session_dir, id=id)
        session._messages_path().touch()
        session._write_metadata()
        return session

    def _messages_path(self) -> Path:
        return self.path / f'{self.id}.jsonl'

    def _metadata_path(self) -> Path:
        return self.path / f'{self.id}.md'

    def add_message(self, message: Message | List[Message]):
        messages = message if isinstance(message, list) else [message]
        for msg in messages:
            if isinstance(msg, ModelMessage) and msg.input_tokens > 0:
                self._token_calculate(msg)
            self.messages.append(msg)
        if self.path:
            with open(self._messages_path(), 'a', encoding='utf-8') as f:
                for msg in messages:
                    f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + '\n')

    def _token_calculate(self, model_msg: ModelMessage):
        last_model_idx = -1
        for i in range(len(self.messages) - 1, -1, -1):
            if isinstance(self.messages[i], ModelMessage):
                last_model_idx = i
                break

        last_model_token = self.messages[last_model_idx].token_num if last_model_idx >= 0 else 0

        since_last = self.messages[last_model_idx + 1:] if last_model_idx >= 0 else self.messages

        known_sum = last_model_token
        unknown_indices = []
        for i, m in enumerate(since_last):
            if m.token_num > 0:
                known_sum += m.token_num
            else:
                unknown_indices.append(i)

        unknown_total = max(0, model_msg.input_tokens - known_sum)

        if len(unknown_indices) == 1:
            since_last[unknown_indices[0]].token_num = unknown_total
        elif len(unknown_indices) > 1:
            per_msg = unknown_total // len(unknown_indices)
            remainder = unknown_total % len(unknown_indices)
            for j, idx in enumerate(unknown_indices):
                since_last[idx].token_num = per_msg + (1 if j < remainder else 0)

        self.total_tokens = model_msg.input_tokens + model_msg.token_num

    @staticmethod
    def _estimate_token_count(msg: Message) -> int:
        serialized = json.dumps(msg.to_dict(), ensure_ascii=False)
        return max(1, len(serialized.encode('utf-8')) // 3)

    def get_message_tokens(self, msg: Message) -> int:
        if msg.token_num > 0:
            return msg.token_num
        return self._estimate_token_count(msg)

    def get_session_token_count(self) -> int:
        messages = self.messages
        if not messages:
            return 0
        if isinstance(messages[-1], ModelMessage):
            return self.total_tokens
        last_model_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], ModelMessage):
                last_model_idx = i
                break
        if last_model_idx < 0:
            return sum(self.get_message_tokens(m) for m in messages)
        return self.total_tokens + sum(self.get_message_tokens(m) for m in messages[last_model_idx + 1:])

    def replace_messages(self, new_messages: List[Message], summary: str = ''):
        if self.path:
            marker = {
                "type": "compress_boundary",
                "compress_num": self.compress_num + 1,
                "timestamp": int(datetime.now().timestamp()),
                "old_messages_count": len(self.messages),
                "summary": summary,
            }
            with open(self._messages_path(), 'a', encoding='utf-8') as f:
                f.write(json.dumps(marker, ensure_ascii=False) + '\n')
                for msg in new_messages:
                    f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + '\n')

        self.compress_num += 1
        if summary:
            self.compact_summary.append(summary)
        self.messages = new_messages
        self.total_tokens = sum(self.get_message_tokens(m) for m in self.messages)

    def save(self):
        if not self.path:
            raise ValueError("Session path not set, use Session.create() for persistent sessions")
        if not self.path:
            raise ValueError("Session path not set, use Session.create() for persistent sessions")
        self._write_metadata()

    def _write_metadata(self):
        tools_str = ', '.join(self.ever_used_tools) if self.ever_used_tools else 'None'
        compact_str = '\n'.join(self.compact_summary) if self.compact_summary else '(empty)'
        summary_str = self.summary if self.summary else '(empty)'

        content = f"""# Session: {self.id}

id: {self.id}
timestamp: {self.timestamp}
total_tokens: {self.total_tokens}
compress_num: {self.compress_num}
messages_count: {len(self.messages)}
ever_used_tools: {tools_str}

---

## Summary

{summary_str}

---

## Compact Summary

{compact_str}
"""
        self._metadata_path().write_text(content, encoding='utf-8')

    @classmethod
    def load(cls, session_id: str, session_path: str | Path) -> 'Session':
        session_dir = Path(session_path)
        messages_file = session_dir / f'{session_id}.jsonl'
        metadata_file = session_dir / f'{session_id}.md'

        if not messages_file.exists():
            raise FileNotFoundError(f"Messages file not found: {messages_file}")
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        lines = []
        with open(messages_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(json.loads(line))

        last_boundary_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].get('type') == 'compress_boundary':
                last_boundary_idx = i
                break

        messages = []
        for data in lines[last_boundary_idx + 1:]:
            if data.get('type') != 'compress_boundary':
                messages.append(Message.from_dict(data))

        metadata = cls._parse_metadata(metadata_file)

        session = cls(
            path=session_dir,
            id=session_id,
            messages=messages,
        )
        session.timestamp = metadata.get('timestamp', session.timestamp)
        session.total_tokens = metadata.get('total_tokens', 0)
        session.compress_num = metadata.get('compress_num', 0)
        session.summary = metadata.get('summary', '')
        session.compact_summary = metadata.get('compact_summary', [])
        session.ever_used_tools = metadata.get('ever_used_tools', [])

        md_count = metadata.get('messages_count', len(messages))
        if len(messages) != md_count:
            print(f"Warning: message count mismatch. JSONL: {len(messages)}, metadata: {md_count}")

        return session

    @staticmethod
    def _parse_metadata(md_path: Path) -> dict:
        text = md_path.read_text(encoding='utf-8')
        result = {}
        section = 'header'
        summary_lines = []
        compact_lines = []

        for line in text.split('\n'):
            stripped = line.strip()
            if stripped == '---':
                if section == 'header':
                    section = 'after_header'
                elif section == 'summary':
                    section = 'after_summary'
                continue
            if stripped == '## Summary':
                section = 'summary'
                continue
            if stripped == '## Compact Summary':
                section = 'compact'
                continue

            if section == 'header' and ':' in stripped and not stripped.startswith('#'):
                key, _, value = stripped.partition(':')
                key, value = key.strip(), value.strip()
                if key in ('total_tokens', 'compress_num', 'messages_count'):
                    result[key] = int(value) if value.isdigit() else 0
                elif key == 'ever_used_tools':
                    result[key] = [t.strip() for t in value.split(',') if t.strip()] if value != 'None' else []
                else:
                    result[key] = value
            elif section == 'summary':
                summary_lines.append(line)
            elif section == 'compact' and stripped:
                compact_lines.append(stripped)

        result['summary'] = '\n'.join(summary_lines).strip()
        if result['summary'] == '(empty)':
            result['summary'] = ''
        result['compact_summary'] = compact_lines if compact_lines and compact_lines != ['(empty)'] else []

        return result
