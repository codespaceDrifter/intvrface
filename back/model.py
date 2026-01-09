import torch

# (key, value) tensors per layer - for local transformer models
# each tensor is either a k or a v at a layer.
# each Tensor shape (batch, heads, seq_len, head_dim)
KVCache = tuple[tuple[torch.Tensor, torch.Tensor], ...] | None


class Model:
    """
    Base model wrapper. Subclass for API/local/remote models.
    """

    def call(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """
        Run inference.

        Args:
            messages: list of message dicts in Claude API format
            kv_cache: optional cached key/values from previous call

        Returns:
            (response_text, updated_kv_cache)
        """
        raise NotImplementedError

    def summarize(self, messages: list[dict], kv_cache: KVCache) -> tuple[str, KVCache]:
        """Summarize context for compression."""
        raise NotImplementedError
