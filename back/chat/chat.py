import anthropic
import json
import os
from pathlib import Path
from chat.prompts import COMPANION_CLAUDY_PROMPT, AGENT_CONTINUE_PROMPT, CONTEXT_SUMMARIZATION_PROMPT
from chat.socket_manager import socket_manager
import asyncio


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


def CREATE_message(data_dict: dict):
    claudy_name = data_dict['claudy_name']
    user_message = data_dict['message']

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
    
    claudy_message = {"role": "assistant", "content":response.content[0].text}
    save_msg(claudy_dir / "stream_context.jsonl", claudy_message)
    READ_message(data_dict)


def READ_message(data_dict: dict):

    claudy_name = data_dict['claudy_name']
    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    asyncio.create_task(
        socket_manager.get_connection().send_json({
            "type": "READ_message",
            "claudy_name": claudy_name,
            "message": stream_context[-1]
        })
    )

def READ_messages(data_dict: dict):

    claudy_name = data_dict['claudy_name']
    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    asyncio.create_task(
        socket_manager.get_connection().send_json({
            "type": "READ_messages",
            "claudy_name": claudy_name,
            "messages": stream_context
        })
    )




def agent_continue(claudy_name: str):

    print (f"agent continue: {claudy_name}")

    claudy_dir = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)
    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    #hacky way for it to continue thikning
    stream_context.append({"role": "user", "content": AGENT_CONTINUE_PROMPT})

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=stream_context,
        system=COMPANION_CLAUDY_PROMPT
    )
    if response.content: 
        claudy_message = {"role": "assistant", "content":response.content[0].text}
        save_msg(claudy_dir / "stream_context.jsonl", claudy_message)
        READ_message(claudy_name, claudy_message["content"])
    else:
        READ_message(claudy_name, "AGENT ENDED: NO CONTENT")
