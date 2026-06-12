import hashlib
from collections.abc import Iterable

from ...core.message import HumanMessage, Session, TextBlock


def normalize_memory_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


def memory_fingerprint(text: str) -> bytes:
    normalized = normalize_memory_text(text)
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).digest()


def format_memory_for_injection(content: str) -> str:
    return normalize_memory_text(content)


def extract_injected_memory_lines(text: str, inject_prefix: str) -> list[str]:
    if not text.startswith(inject_prefix):
        return []

    body = text[len(inject_prefix):]
    separator_index = body.find("\n\n")
    if separator_index >= 0:
        body = body[:separator_index]

    memories = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("- "):
            content = line[2:].strip()
            if content:
                memories.append(content)
    return memories


def iter_user_message_texts(session: Session) -> Iterable[str]:
    for turn in session.turns:
        if not turn.messages:
            continue
        msg = turn.messages[0]
        if not isinstance(msg, HumanMessage):
            continue
        if isinstance(msg.content, str):
            yield msg.content
        elif isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    yield block.text


def extract_seen_memory_keys(session: Session, inject_prefix: str) -> set[bytes]:
    seen = set()
    for text in iter_user_message_texts(session):
        for memory in extract_injected_memory_lines(text, inject_prefix):
            seen.add(memory_fingerprint(memory))
    return seen
