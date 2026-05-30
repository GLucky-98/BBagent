"""
AskHuman tool - Allows the agent to ask the human user questions during execution.
"""
import asyncio
from typing import Callable, Optional

from ..core.tool import Tool


class AskHumanState:
    """Per-agent state shared between the ask_human tool and the backend transport."""

    def __init__(self):
        self.future: Optional[asyncio.Future] = None
        self.on_question: Callable[[str], None] = lambda q: None


def create_ask_human_tool() -> Tool:
    state = AskHumanState()

    async def ask_human(question: str) -> str:
        loop = asyncio.get_running_loop()
        state.future = loop.create_future()
        state.on_question(question)
        try:
            answer = await state.future
            return f"User answer: {answer}"
        except asyncio.CancelledError:
            return "Question cancelled: the agent was interrupted while waiting for an answer."

    tool = Tool(
        func=ask_human,
        name="ask_human",
        description="Ask the human user a question when you need clarification, additional information, or a decision. Use this when you are uncertain about something and need the user's input to proceed correctly.",
        source="built_in.ask_human",
    )
    tool._ask_human_state = state
    return tool
