import torch

# outer tuple: one entry per layer (... means repeat N layers)
# inner tuple: (key_tensor, value_tensor) for that layer
# each tensor shape: (batch, heads, seq_len, head_dim)
# None for API models that don't expose kv cache
KVCache = tuple[tuple[torch.Tensor, torch.Tensor], ...] | None


class Model:
    """
    Base model wrapper. Subclass for API/local/remote models.
    """

    async def call(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """
        Run inference.

        Args:
            messages: list of message dicts in Claude API format
            kv_cache: optional cached key/values from previous call

        Returns:
            (response_text, updated_kv_cache)
        """
        raise NotImplementedError

    async def summarize(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """Summarize context for compression."""
        raise NotImplementedError
