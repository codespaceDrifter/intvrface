from typing import cast
import anthropic
from anthropic.types import MessageParam
from model import Model, KVCache
from prompt import CLAUDY_PROMPT, CONTEXT_SUMMARIZATION_PROMPT


class Claude(Model):
    """Claude API wrapper."""

    def __init__(self, model: str = "claude-opus-4-5-20251101"):
        self.model = model
        self.client = anthropic.Anthropic()

    def call(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=CLAUDY_PROMPT,
            messages=cast(list[MessageParam], messages),
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return text, None

    def summarize(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """Summarize context using CONTEXT_SUMMARIZATION_PROMPT."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=CONTEXT_SUMMARIZATION_PROMPT,
            messages=cast(list[MessageParam], messages),
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text
        return text, None
