import json
import base64
import torch
from pathlib import Path

# kv cache type - tuple of (key, value) per layer, or None for API models
KVCache = tuple[tuple[torch.Tensor, torch.Tensor], ...] | None

CONTEXT_ROOT = Path.home() / "intvrface" / "context"
MAX_WORDS = 30000
PRESERVE_LAST = 5


class Context:
    """
    Manages context for an agent session.

    Files in context/{name}/:
        original.jsonl   - full log, never deleted
        kv_cache.pt      - cached key/values for local models

    Context kept in memory (self.messages), loaded from original.jsonl on init.
    On summarization, in-memory is trimmed but original.jsonl only appends.
    Format matches Claude API exactly. Consecutive same-role messages collapsed.
    """

    def __init__(self, name: str):
        self.name = name
        self.folder = CONTEXT_ROOT / name
        self.folder.mkdir(parents=True, exist_ok=True)

        self.original_path = self.folder / "original.jsonl"
        self.kv_path = self.folder / "kv_cache.pt"

        self.original_path.touch(exist_ok=True)

        # load original into memory (triggers summarization if too long)
        self.messages: list[dict] = []
        text = self.original_path.read_text().strip()
        lines = text.split('\n') if text else []
        for line in lines:
            self.messages.append(json.loads(line))

    def add(self, role: str, content: str | None = None, image_bytes: bytes | None = None):
        """Add a message to context."""
        assert role in ("user", "assistant")
        assert content or image_bytes

        if image_bytes:
            img_data = base64.standard_b64encode(image_bytes).decode("utf-8")
            block = {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_data}
            }
        else:
            assert content
            block = {"type": "text", "text": content}

        # add to memory, collapsing same-role
        if self.messages and self.messages[-1]["role"] == role:
            self.messages[-1]["content"].append(block)
        else:
            self.messages.append({"role": role, "content": [block]})

        # append to disk, collapsing same-role
        text = self.original_path.read_text().strip()
        lines = text.split('\n') if text else []
        if lines:
            last_entry = json.loads(lines[-1])
            if last_entry["role"] == role:
                last_entry["content"].append(block)
                lines[-1] = json.dumps(last_entry)
                self.original_path.write_text('\n'.join(lines) + '\n')
                return
        with open(self.original_path, "a") as f:
            f.write(json.dumps({"role": role, "content": [block]}) + "\n")


    def count_words(self) -> int:
        """Count words in streaming context."""
        total = 0
        for msg in self.messages:
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    total += len(block.get("text", "").split())
                elif block.get("type") == "image":
                    total += 1000  # a picture is worth a thousand words
        return total

    def needs_summary(self) -> bool:
        """Check if context exceeds MAX_WORDS."""
        return self.count_words() >= MAX_WORDS

    def apply_summary(self, summary: str):
        """Replace in-memory context with summary + last N messages."""
        if len(self.messages) <= PRESERVE_LAST:
            return  # everything preserved anyway, summary would just add bloat
        last_msgs = self.messages[-PRESERVE_LAST:]

        summary_block = {"type": "text", "text": f"SUMMARIZED CONTEXT: {summary}"}

        # append summary to original (never delete from original)
        with open(self.original_path, "a") as f:
            f.write(json.dumps({"role": "assistant", "content": [summary_block]}) + "\n")

        # rebuild in-memory messages: summary + last N
        self.messages = [{"role": "assistant", "content": [summary_block]}]
        for msg in last_msgs:
            for block in msg["content"]:
                if self.messages[-1]["role"] == msg["role"]:
                    self.messages[-1]["content"].append(block)
                else:
                    self.messages.append({"role": msg["role"], "content": [block]})

    def load_kv(self) -> KVCache:
        if self.kv_path.exists():
            return torch.load(self.kv_path)
        return None

    def save_kv(self, kv: KVCache):
        if kv is None:
            self.kv_path.unlink(missing_ok=True)
        else:
            torch.save(kv, self.kv_path)
