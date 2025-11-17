import anthropic
import json
import os
from pathlib import Path
from agent.socket_manager import socket_manager
import asyncio


APP_NAME = "intvrface"
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME


def load_jsonl(path):
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f]

def save_msg(path, msg):
    with open(path, "a") as f:
        f.write(json.dumps(msg) + "\n")


def CREATE_message(claudy_name: str, user_message: dict):

    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    save_msg(claudy_dir / "stream_context.jsonl", user_message)
    stream_context.append(user_message)


def READ_message(claudy_name: str, claudy_message: dict):

    asyncio.create_task(
        socket_manager.get_connection().send_json({
            "response_type": "READ_message",
            "claudy_name": claudy_name,
            "message": claudy_message
        })
    )

def READ_messages(claudy_name: str):

    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    asyncio.create_task(
        socket_manager.get_connection().send_json({
            "response_type": "READ_messages",
            "claudy_name": claudy_name,
            "messages": stream_context
        })
    )

