import asyncio
from typing import List

from ..core.agenthook import HookContext
from ..core.agent import SubAgent
from ..core.model import Model
from ..core.tool import Tool
from ..core.message import Message, HumanMessage, ModelMessage

DEFAULT_SUMMARY_PROMPT = """You are a conversation summarizer. Your task is to compress a conversation history into a concise summary.

Rules:
- Preserve key decisions, conclusions, and action items
- Keep important tool call results (file paths, code snippets, error messages)
- Preserve any unresolved questions or ongoing tasks
- Remove redundant or verbose exchanges
- Output in the same language as the conversation"""

DEFAULT_SUMMARY_USER_PREFIX = """Summarize the following conversation history into a concise paragraph:\n\n"""


async def compress_session(
    session,
    subagent: SubAgent,
    threshold: float,
    keep_recent_msg: int,
    keep_recent_time: int,
) -> str:
    messages = session.messages
    compress_zone = list(messages[:-keep_recent_msg])
    keep_zone = list(messages[-keep_recent_msg:])

    keep_tokens = sum(session.get_message_tokens(m) for m in keep_zone)
    if keep_tokens > threshold:
        latest_timestamp = max(msg.timestamp for msg in messages)
        cutoff = latest_timestamp - keep_recent_time
        remaining = []
        for msg in keep_zone:
            if msg.timestamp < cutoff:
                compress_zone.append(msg)
            else:
                remaining.append(msg)
        keep_zone = remaining

        keep_tokens = sum(session.get_message_tokens(m) for m in keep_zone)
        if keep_tokens > threshold:
            last_human_idx = None
            for i in range(len(keep_zone) - 1, -1, -1):
                if isinstance(keep_zone[i], HumanMessage):
                    last_human_idx = i
                    break
            if last_human_idx is not None:
                compress_zone.extend(keep_zone[:last_human_idx])
                compress_zone.extend(keep_zone[last_human_idx + 1:])
                keep_zone = [keep_zone[last_human_idx]]
            else:
                compress_zone.extend(keep_zone)
                keep_zone = []

    if not compress_zone:
        return 

    last_compress = compress_zone[-1]
    if not (isinstance(last_compress, ModelMessage) and
            last_compress.stop_reason in ('end_turn', 'stop')):
        split_idx = None
        for i, msg in enumerate(keep_zone):
            if isinstance(msg, ModelMessage) and msg.stop_reason in ('end_turn', 'stop'):
                split_idx = i
                break
        if split_idx is not None:
            compress_zone.extend(keep_zone[:split_idx])
            keep_zone = keep_zone[split_idx:]

    summary_input = [HumanMessage(content=DEFAULT_SUMMARY_USER_PREFIX)] + compress_zone
    last_exception = None
    for attempt in range(3):
        try:
            summary = await subagent.run(summary_input)
            break
        except Exception as e:
            last_exception = e
            if attempt < 2:
                await asyncio.sleep(1)
    else:
        raise RuntimeError(
            f'Compression subagent failed after 3 retries: {last_exception}'
        ) from last_exception

    summary_msg = HumanMessage(content=summary)
    session.replace_messages([summary_msg] + keep_zone, summary=summary)
    return 


def create_ctx_compress_hook(
    submodel: Model,
    max_context_tokens: int,
    keep_recent_msg: int,
    keep_recent_time: int,
    compression_threshold: float
):

    threshold = int(max_context_tokens * compression_threshold)

    async def check_compression_needed(ctx: HookContext):
        agent = ctx.agent
        session = agent.session

        total_tokens = session.get_session_token_count()
        needed = total_tokens >= threshold

        ctx.set('compression_needed', needed)

    async def execute_compression(ctx: HookContext):
        needed = ctx.get('compression_needed', False)
        if not needed:
            ctx.set('compression_result', 'skipped')
            return

        agent = ctx.agent
        session = agent.session
        
        subagent = SubAgent(model=submodel, system_prompt=DEFAULT_SUMMARY_PROMPT)

        await compress_session(
            session=session,
            subagent=subagent,
            threshold=threshold,
            keep_recent_msg=keep_recent_msg,
            keep_recent_time=keep_recent_time,
        )

    return check_compression_needed, execute_compression
