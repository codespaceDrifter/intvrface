from typing import cast
import asyncio
import anthropic
from anthropic.types import MessageParam
from model import Model, KVCache
from prompt import CLAUDY_PROMPT, CONTEXT_SUMMARIZATION_PROMPT

# seconds before API call is considered hung
API_TIMEOUT = 180


class Claude(Model):
    """Claude API wrapper (async)."""

    def __init__(self, model: str = "claude-opus-4-6"):
        self.model = model
        self.client = anthropic.AsyncAnthropic()

    async def call(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        response = await asyncio.wait_for(
            self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                system=CLAUDY_PROMPT,
                messages=cast(list[MessageParam], messages),
            ),
            timeout=API_TIMEOUT,
        )

        text = "".join(block.text for block in response.content if block.type == "text")
        return text, None

    async def summarize(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """Summarize context using CONTEXT_SUMMARIZATION_PROMPT."""
        response = await asyncio.wait_for(
            self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                system=CONTEXT_SUMMARIZATION_PROMPT,
                messages=cast(list[MessageParam], messages),
            ),
            timeout=API_TIMEOUT,
        )

        text = "".join(block.text for block in response.content if block.type == "text")
        return text, None
