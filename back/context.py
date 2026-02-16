import json
import base64
import torch
from pathlib import Path

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

    Files in context/{name}/:
        original.jsonl   - full log, append-only archive (never read at runtime)
        working.jsonl    - current working memory (loaded on startup)
        kv_cache.pt      - cached key/values for local models

    On startup, loads working.jsonl (compact). Falls back to original.jsonl if no working.jsonl.
    On summarization, working.jsonl is overwritten with summary + last N messages.
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

    def _collapse_append(self, lst: list[dict], role: str, block: dict):
        """Append a content block to a message list, collapsing consecutive same-role."""
        if lst and lst[-1]["role"] == role:
            lst[-1]["content"].append(block)
        else:
            lst.append({"role": role, "content": [block]})

    def _append_to_file(self, path: Path, role: str, block: dict):
        """Append a content block to a jsonl file, collapsing consecutive same-role."""
        text = path.read_text().strip()
        lines = text.split('\n') if text else []
        if lines:
            last_entry = json.loads(lines[-1])
            if last_entry["role"] == role:
                last_entry["content"].append(block)
                lines[-1] = json.dumps(last_entry)
                path.write_text('\n'.join(lines) + '\n')
                return
        with open(path, "a") as f:
            f.write(json.dumps({"role": role, "content": [block]}) + "\n")

    def marshal(self) -> list[dict]:
        """
        Convert messages to Claude API format.
        environment → user, command → assistant (API only has user/assistant).
        If last message is assistant/command, adds WORK_MSG as [SYSTEM] environment
        to actual context (stored + visible in frontend).
        """
        from prompt import WORK_MSG
        if self.messages and self.messages[-1]["role"] in ("assistant", "command"):
            self.add("environment", content=f"[SYSTEM]\n{WORK_MSG}")
        out = []
        for msg in self.messages:
            r = msg["role"]
            role = "user" if r == "environment" else "assistant" if r == "command" else r
            for block in msg["content"]:
                self._collapse_append(out, role, block)
        return out

    def add(self, role: str, content: str | None = None, image_bytes: bytes | None = None):
        """Add a message to context."""
        assert role in ("user", "assistant", "environment", "command")
        assert content or image_bytes

        if image_bytes:
            # original: 0-255 (8 bit as a unit)
            # base64: 6 bit as a unit mappable to ASCII character then to it's 8 bit code
            # utf8: typecasts the byte data to string, actual data stays the same
            img_data = base64.standard_b64encode(image_bytes).decode("utf-8")
            block = {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_data}
            }
        else:
            assert content
            block = {"type": "text", "text": content}

        self._collapse_append(self.messages, role, block)
        self._append_to_file(self.original_path, role, block)
        self._append_to_file(self.working_path, role, block)


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
        """Replace working memory with summary + last N messages."""
        if len(self.messages) <= PRESERVE_LAST:
            return  # everything preserved anyway, summary would just add bloat
        last_msgs = self.messages[-PRESERVE_LAST:]

        summary_block = {"type": "text", "text": f"SUMMARIZED CONTEXT: {summary}"}

        # archive summary to original
        self._append_to_file(self.original_path, "assistant", summary_block)

        # rebuild in-memory: summary + last N
        self.messages = [{"role": "assistant", "content": [summary_block]}]
        for msg in last_msgs:
            for block in msg["content"]:
                self._collapse_append(self.messages, msg["role"], block)

        # overwrite working.jsonl with current in-memory state
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
