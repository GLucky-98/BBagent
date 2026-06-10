import asyncio
import uuid

from ..core.hook import HookContext
from ..core.agent import SubAgent
from ..core.message import HumanMessage


COMPRESS_PROMPT = """You are a conversation summarizer. Your task is to compress a conversation history into a concise summary.

Rules:
- Preserve key decisions, conclusions, and action items
- Keep important tool call results (file paths, code snippets, error messages)
- Preserve any unresolved questions or ongoing tasks
- Remove redundant or verbose exchanges or useless thinking 
- Output in the same language as the conversation"""


COMPRESS_PREFIX = (
    "Below is a conversation history that needs to be compressed into a concise summary. "
    "This summary will be used as context for future conversations, so preserve key decisions, "
    "conclusions, action items, important tool call results, and unresolved questions.\n\n"
    "Conversation history:\n"
)


async def compress_session(
    session,
    model,
    compression_threshold: float = 0.8,
    merge_ratio: float = 0.2,
    small_turn_cap: int = 5000,
    keep_recent_turns: int = 3,
    compress_prompt: str = COMPRESS_PROMPT,
    compress_prefix: str = COMPRESS_PREFIX,
    logger=None,
):
    max_context_tokens = model.max_context_tokens
    context_threshold = int(max_context_tokens * compression_threshold)
    merge_threshold = int(max_context_tokens * merge_ratio)
    small_turn_threshold = min(int(merge_threshold / 3), small_turn_cap)

    # Phase 0: need at least 2 visible turns to make compression meaningful
    visible_turns = session.turns[session.window_start:]
    if len(visible_turns) <= 1:
        if logger:
            logger.debug(
                f"Compression skipped: {len(visible_turns)} visible turns (need at least 2)",
                context={"visible_turns": len(visible_turns)},
            )
        return

    # Phase 1: divide visible turns into pending_zone and keep_zone
    keep_zone = list(visible_turns[-keep_recent_turns:])
    pending_zone = list(visible_turns[:-keep_recent_turns])

    # Phase 2: if keep_zone is overweight, spill oldest turns into pending_zone
    spill_count = 0
    while len(keep_zone) > 1:
        if sum(t.token_count for t in keep_zone) <= context_threshold:
            break
        pending_zone.append(keep_zone.pop(0))
        spill_count += 1

    if logger:
        pending_count = len(pending_zone)
        keep_count = len(keep_zone)
        visible_count = len(visible_turns)
        total_tok = sum(t.token_count for t in visible_turns)
        keep_tok = sum(t.token_count for t in keep_zone)
        logger.info(
            f"Compression zones: {pending_count} pending + {keep_count} keep = {visible_count} turns ({total_tok} tokens)",
            context={
                "pending_count": pending_count,
                "keep_count": keep_count,
                "total_tokens": total_tok,
                "keep_tokens": keep_tok,
            },
        )
        if spill_count > 0:
            logger.debug(
                f"Keep zone overweight, spilled {spill_count} turns to pending",
                context={"spilled_count": spill_count},
            )

    if not pending_zone:
        return

    subagent = SubAgent(model=model, system_prompt=compress_prompt, logger=logger, name="ContextCompressor")
    # Phase 3: compress all uncompressed turns in pending_zone
    uncompressed_turns = [t for t in pending_zone if not t.is_summarized]
    if uncompressed_turns:
        if logger:
            logger.info(
                f"Starting compression: {len(uncompressed_turns)} turns in pending zone",
                context={"pending_turn_count": len(uncompressed_turns)},
            )

        groups = []
        current_group = []
        current_group_tokens = 0

        for turn in uncompressed_turns:
            t = turn.token_count
            if t < small_turn_threshold:
                if current_group_tokens + t <= merge_threshold:
                    current_group.append(turn)
                    current_group_tokens += t
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [turn]
                    current_group_tokens = t
            else:
                if current_group:
                    groups.append(current_group)
                groups.append([turn])
                current_group = []
                current_group_tokens = 0

        if current_group:
            groups.append(current_group)

        if logger:
            logger.debug(
                f"Grouped {len(uncompressed_turns)} uncompressed turns into {len(groups)} groups",
                context={"total_turns": len(uncompressed_turns), "group_count": len(groups)},
            )

        group_id_base = str(uuid.uuid4())

        for idx, group in enumerate(groups):
            group_tokens = sum(t.token_count for t in group)
            if logger:
                logger.debug(
                    f"Compressing group {idx + 1}/{len(groups)}: {len(group)} turns, {group_tokens} tokens",
                    context={
                        "group_index": idx + 1,
                        "total_groups": len(groups),
                        "turns_in_group": len(group),
                        "total_tokens": group_tokens,
                    },
                )

            input_messages = []

            for turn in group:
                input_messages.extend(turn.messages)

            compress_input = [HumanMessage(content=compress_prefix)] + input_messages

            last_exception = None
            for attempt in range(3):
                try:
                    summary_raw = await subagent.run(compress_input)
                    break
                except Exception as e:
                    last_exception = e
                    if attempt < 2:
                        if logger:
                            logger.warning(
                                f"Compression group {idx + 1} failed (attempt {attempt + 1}/3): {e}",
                                context={"group_index": idx + 1, "attempt": attempt + 1},
                            )
                        await asyncio.sleep(1)
            else:
                if logger:
                    logger.error(
                        f"Compression subagent permanently failed after 3 retries for group {idx + 1}",
                        context={"group_index": idx + 1, "last_error": str(last_exception)},
                    )
                raise RuntimeError(
                    f'Compression subagent failed after 3 retries: {last_exception}'
                ) from last_exception

            full_summary = f"[Historical Conversation Summary]\n{summary_raw}"

            if logger:
                logger.info(
                    f"Group {idx + 1}/{len(groups)} compressed: {len(group)} turns -> summary ({len(full_summary)} chars)",
                    context={
                        "group_index": idx + 1,
                        "total_groups": len(groups),
                        "turn_count": len(group),
                        "summary_length": len(full_summary),
                    },
                )

            group_id = f"{group_id_base}_{idx}"
            for turn in group:
                turn.is_summarized = True
                turn.summary = full_summary
                turn.summary_group_id = group_id

    session.compress_turn_count += 1

    # Phase 4: check threshold after compression
    tokens_after = session.get_visible_token_count()
    if tokens_after <= context_threshold:
        if logger:
            logger.debug(
                f"After compression, token count ({tokens_after}) within threshold, no skip needed",
                context={"tokens": tokens_after, "threshold": context_threshold},
            )
        return

    # Phase 5: skip summaries by compression-group, from oldest to newest
    pending_start = session.window_start
    pending_end = session.window_start + len(pending_zone)
    skipped_group_ids = set()
    skipped_turn_count_phase5 = 0

    for i in range(pending_start, pending_end):
        turn = session.turns[i]
        if not turn.is_summarized:
            continue

        group_id = turn.summary_group_id
        if group_id and group_id not in skipped_group_ids:
            for t in session.turns[session.window_start:]:
                if t.summary_group_id == group_id:
                    t.skip_summary = True
                    skipped_turn_count_phase5 += 1
            skipped_group_ids.add(group_id)
            if session.get_visible_token_count() <= context_threshold:
                if logger:
                    logger.info(
                        f"Skipped {len(skipped_group_ids)} summary groups ({skipped_turn_count_phase5} turns) to meet threshold",
                        context={
                            "skipped_groups": len(skipped_group_ids),
                            "skipped_turns": skipped_turn_count_phase5,
                            "tokens_after": session.get_visible_token_count(),
                            "threshold": context_threshold,
                        },
                    )
                return
        elif not group_id:
            turn.skip_summary = True
            skipped_turn_count_phase5 += 1
            if session.get_visible_token_count() <= context_threshold:
                if logger:
                    logger.info(
                        f"Skipped {len(skipped_group_ids)} summary groups ({skipped_turn_count_phase5} turns) to meet threshold",
                        context={
                            "skipped_groups": len(skipped_group_ids),
                            "skipped_turns": skipped_turn_count_phase5,
                            "tokens_after": session.get_visible_token_count(),
                            "threshold": context_threshold,
                        },
                    )
                return

    # Phase 6: advance window_start past summarized turns
    old_window_start = session.window_start
    max_start = len(session.turns) - 1
    while session.window_start < max_start:
        session.window_start += 1
        if session.get_visible_token_count() <= context_threshold:
            hidden_turns = session.window_start - old_window_start
            if logger:
                logger.info(
                    f"Window advanced: {old_window_start} -> {session.window_start} (hidden {hidden_turns} turns)",
                    context={
                        "old_window_start": old_window_start,
                        "new_window_start": session.window_start,
                        "hidden_turns": hidden_turns,
                    },
                )
            return


def create_ctx_compress_hook(
    compression_threshold: float = 0.8,
    merge_ratio: float = 0.2,
    small_turn_cap: int = 5000,
    keep_recent_turns: int = 3,
    compress_prompt: str = COMPRESS_PROMPT,
    compress_prefix: str = COMPRESS_PREFIX,
):

    async def check_compression_needed(ctx: HookContext):
        agent = ctx.agent
        session = agent.session
        max_context_tokens = agent.model.max_context_tokens
        threshold = int(max_context_tokens * compression_threshold)

        total_tokens = session.get_visible_token_count()
        needed = total_tokens >= threshold

        if needed:
            agent.logger.info(
                "Compression needed: %d/%d",
                total_tokens, threshold,
                context={"visible_tokens": total_tokens, "threshold": threshold, "ratio": round(total_tokens / max_context_tokens, 3)},
            )
        else:
            agent.logger.debug(
                "Compression not needed: %d/%d",
                total_tokens, threshold,
                context={"visible_tokens": total_tokens, "threshold": threshold, "ratio": round(total_tokens / max_context_tokens, 3)},
            )

        ctx.set('compression_needed', needed)

    async def execute_compression(ctx: HookContext):
        needed = ctx.get('compression_needed', False)
        if not needed:
            ctx.set('compression_result', 'skipped')
            ctx.agent.logger.debug("Compression execution skipped (not needed)")
            return

        agent = ctx.agent
        session = agent.session

        await compress_session(
            session=session,
            model=agent.model,
            compress_prompt=compress_prompt,
            logger=agent.logger,
            compression_threshold=compression_threshold,
            merge_ratio=merge_ratio,
            small_turn_cap=small_turn_cap,
            compress_prefix=compress_prefix,
            keep_recent_turns=keep_recent_turns,
        )

    return check_compression_needed, execute_compression
