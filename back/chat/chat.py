import anthropic
import json
import os
from pathlib import Path
from chat.prompts import COMPANION_CLAUDY_PROMPT

APP_NAME = "intvrface"
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME

client = anthropic.Anthropic()

def load_jsonl(path):
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f]

def save_msg(path, msg):
    with open(path, "a") as f:
        f.write(json.dumps(msg) + "\n")


def user_send_message(claudy_name: str, user_message):
    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    save_msg(claudy_dir / "stream_context.jsonl", user_message)
    stream_context.append(user_message)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=stream_context,
        system=COMPANION_CLAUDY_PROMPT
    )
    print (f"response model: {response.model}")
    
    claudy_message = {"role": "assistant", "content":response.content[0].text}

    save_msg(claudy_dir / "stream_context.jsonl", claudy_message)
    stream_context.append(claudy_message)

    return stream_context

def get_messages(claudy_name: str):
    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    return load_jsonl(claudy_dir / "stream_context.jsonl")