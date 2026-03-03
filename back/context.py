import json
import base64
import torch
from pathlib import Path
from prompt import WORK_MSG

# outer tuple: one entry per layer (...  means repeat N layers)
# inner tuple: (key_tensor, value_tensor) for that layer
# each tensor shape: (batch, heads, seq_len, head_dim)
# None for API models that don't expose kv cache
KVCache = tuple[tuple[torch.Tensor, torch.Tensor], ...] | None


CONTEXT_ROOT = Path.home() / "intvrface" / "context"
MAX_WORDS = 64000
PRESERVE_LAST = 5

class Context:
    """
    Manages context for an agent session.

    Messages are stored uncollapsed — each add() creates a new entry.
    Only marshal() collapses consecutive same-role messages for the API.

    Files in context/{name}/:
        original.jsonl   - full log, append-only archive (never read at runtime)
        working.jsonl    - current working memory (loaded on startup)
        kv_cache.pt      - cached key/values for local models
    """

    def __init__(self, name: str):
        self.name = name
        self.folder = CONTEXT_ROOT / name
        self.folder.mkdir(parents=True, exist_ok=True)

        self.original_path = self.folder / "original.jsonl"
        self.working_path = self.folder / "working.jsonl"
        self.kv_path = self.folder / "kv_cache.pt"

        self.original_path.touch(exist_ok=True)
        self.working_path.touch(exist_ok=True)
        self.messages: list[dict] = [json.loads(line) for line in self.working_path.read_text().strip().splitlines()]

    def marshal(self) -> list[dict]:
        """
        Convert messages to Claude API format.
        environment → user, command → assistant (API only has user/assistant).
        Collapses consecutive same-role messages.
        If last message is assistant/command, adds WORK_MSG first.
        """
        if self.messages and self.messages[-1]["role"] in ("assistant", "command"):
            self.add("environment", content=f"[SYSTEM]\n{WORK_MSG}")
        # API only has user/assistant — map our 4 roles to 2
        role_map = {
            "user": "user",
            "environment": "user",
            "assistant": "assistant",
            "command": "assistant",
        }
        out = []
        for msg in self.messages:
            role = role_map[msg["role"]]
            block = msg["content"][0]
            # collapse consecutive same-role for API
            if out and out[-1]["role"] == role:
                out[-1]["content"].append(block)
            else:
                out.append({"role": role, "content": [block]})
        return out

    def add(self, role: str, content: str | None = None, image_bytes: bytes | None = None):
        """Add a message to context. Always creates a new entry (uncollapsed)."""
        assert role in ("user", "assistant", "environment", "command")
        assert content or image_bytes

        if image_bytes:
            # original: 0-255 (8 bit as a unit)
            # base64: 6 bit as a unit mappable to ASCII character then to its 8 bit code
            # utf8: typecasts the byte data to string, actual data stays the same
            img_data = base64.standard_b64encode(image_bytes).decode("utf-8")
            block = {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_data}
            }
        else:
            assert content
            block = {"type": "text", "text": content}

        msg = {"role": role, "content": [block]}
        self.messages.append(msg)
        with open(self.original_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        with open(self.working_path, "a") as f:
            f.write(json.dumps(msg) + "\n")



    def needs_summary(self) -> bool:
        """Count words in streaming context."""
        """Check if context exceeds MAX_WORDS."""
        total = 0
        for msg in self.messages:
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    total += len(block.get("text", "").split())
                elif block.get("type") == "image":
                    total += 1000  # a picture is worth a thousand words
        return total >= MAX_WORDS

    def apply_summary(self, summary: str):
        """Replace working memory with summary + last N messages."""
        if len(self.messages) <= PRESERVE_LAST:
            return  # everything preserved anyway, summary would just add bloat

        summary_msg = {"role": "assistant", "content": [{"type": "text", "text": f"SUMMARIZED CONTEXT: {summary}"}]}

        # archive summary to original
        with open(self.original_path, "a") as f:
            f.write(json.dumps(summary_msg) + "\n")

        # rebuild in-memory: summary + last N
        self.messages = [summary_msg] + self.messages[-PRESERVE_LAST:]

        # overwrite working.jsonl
        self.working_path.write_text(
            '\n'.join(json.dumps(msg) for msg in self.messages) + '\n'
        )

    def load_kv(self) -> KVCache:
        if self.kv_path.exists():
            return torch.load(self.kv_path)
        return None

    def save_kv(self, kv: KVCache):
        if kv is None:
            self.kv_path.unlink(missing_ok=True)
        else:
            torch.save(kv, self.kv_path)
