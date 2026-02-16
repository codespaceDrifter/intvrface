"""
WebSocket server for agent management.

Commands (client -> server):
    {"cmd": "list"}
    {"cmd": "create", "name": "agent_1", "novnc_port": 6080}
    {"cmd": "start", "name": "agent_1"}
{"cmd": "delete", "name": "agent_1"}
    {"cmd": "chat", "name": "agent_1", "text": "do this task"}
    {"cmd": "get_context", "name": "agent_1"}

Responses (server -> client):
    {"type": "agents", "agents": [{"name": "agent_1", "running": true, "novnc_port": 6080}, ...]}
    {"type": "context", "name": "agent_1", "messages": [...]}
    {"type": "response", "name": "agent_1", "text": "ok I will..."}
    {"type": "error", "msg": "..."}

Run: uvicorn server:app --reload --port 8000
"""

import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agent import Agent
from models.claude import Claude

app = FastAPI()

# persisted to ~/intvrface/agents.json
AGENTS_FILE = Path.home() / "intvrface" / "agents.json"

# active agents: name -> {"agent": Agent, "novnc_port": int, "container_on": bool, "working": bool}
agents: dict[str, dict] = {}

# connected websocket clients
clients: list[WebSocket] = []


def save_agents():
    """Save agent configs to disk."""
    AGENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    configs = [{"name": name, "novnc_port": info["novnc_port"]} for name, info in agents.items()]
    AGENTS_FILE.write_text(json.dumps(configs))


def is_container_running(name: str) -> bool:
    """Check if a docker container is actually running."""
    import subprocess
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{name}$"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def load_agents():
    """Load agent configs from disk on startup."""
    if not AGENTS_FILE.exists():
        return
    configs = json.loads(AGENTS_FILE.read_text())
    for cfg in configs:
        name, novnc_port = cfg["name"], cfg["novnc_port"]
        model = Claude()
        agent = Agent(name, model, use_container=True, novnc_port=novnc_port)
        # check actual docker state — container may still be running from last session
        container_on = is_container_running(name)
        if container_on:
            agent.container._running = True
        agents[name] = {"agent": agent, "novnc_port": novnc_port, "container_on": container_on, "working": False, "chat_mode": False}


# load saved agents on startup
load_agents()


async def broadcast(msg: dict):
    """Send message to all connected clients."""
    text = json.dumps(msg)
    for client in clients:
        try:
            await client.send_text(text)
        except:
            pass


def get_agents_list() -> list[dict]:
    """Get list of agents with their status."""
    return [
        {"name": name, "container_on": info["container_on"], "working": info["working"], "novnc_port": info["novnc_port"]}
        for name, info in agents.items()
    ]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    # send current agents list on connect
    await ws.send_text(json.dumps({"type": "agents", "agents": get_agents_list()}))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            cmd = msg.get("cmd")

            if cmd == "list":
                await ws.send_text(json.dumps({"type": "agents", "agents": get_agents_list()}))

            elif cmd == "create":
                name = msg.get("name")
                novnc_port = msg.get("novnc_port", 6080)

                if not name:
                    await ws.send_text(json.dumps({"type": "error", "msg": "name required"}))
                    continue

                if name in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} already exists"}))
                    continue

                model = Claude()
                agent = Agent(name, model, use_container=True, novnc_port=novnc_port)

                agents[name] = {
                    "agent": agent,
                    "novnc_port": novnc_port,
                    "container_on": False,
                    "working": False,
                    "chat_mode": False,
                }

                save_agents()
                await broadcast({"type": "agents", "agents": get_agents_list()})

            elif cmd == "start":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                # start container if not on (run in thread — docker blocks)
                if not info["container_on"]:
                    await asyncio.to_thread(info["agent"].start)
                    info["container_on"] = True

                # start work loop if not working
                if not info["working"]:
                    info["working"] = True

                    async def on_turn(response, messages, _name=name):
                        await broadcast({"type": "context", "name": _name, "messages": messages})

                    asyncio.create_task(info["agent"].work(on_turn))

                await broadcast({"type": "agents", "agents": get_agents_list()})

            elif cmd == "pause":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                if info["working"]:
                    info["agent"].pause()
                    info["working"] = False

                await broadcast({"type": "agents", "agents": get_agents_list()})

            elif cmd == "delete":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                info["agent"].pause()
                if info["agent"].container:
                    await asyncio.to_thread(info["agent"].container.destroy)

                del agents[name]
                save_agents()
                await broadcast({"type": "agents", "agents": get_agents_list()})

            elif cmd == "chat_mode":
                name = msg.get("name")
                enabled = msg.get("enabled", False)

                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                info["chat_mode"] = enabled
                info["agent"].chat_mode = enabled
                if enabled:
                    # entering chat mode: pause work loop
                    if info["working"]:
                        info["agent"].pause()
                        info["working"] = False
                else:
                    # leaving chat mode: restart work loop
                    if info["container_on"] and not info["working"]:
                        info["working"] = True
                        async def on_turn(response, messages, _name=name):
                            await broadcast({"type": "context", "name": _name, "messages": messages})
                        asyncio.create_task(info["agent"].work(on_turn))

                await broadcast({"type": "agents", "agents": get_agents_list()})

            elif cmd == "chat":
                name = msg.get("name")
                text = msg.get("text", "")

                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                if not info["container_on"]:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not running"}))
                    continue

                info["agent"].chat(text)
                await broadcast({"type": "context", "name": name, "messages": info["agent"].context.messages})
                if info["chat_mode"]:
                    agent = info["agent"]
                    async def do_chat_turn(_name=name, _agent=agent):
                        try:
                            print(f"[chat_mode] calling turn for {_name}")
                            await _agent.turn()
                            print(f"[chat_mode] turn done for {_name}")
                            await broadcast({"type": "context", "name": _name, "messages": _agent.context.messages})
                        except Exception as e:
                            print(f"[chat_mode] ERROR: {e}")
                    asyncio.create_task(do_chat_turn())

            elif cmd == "get_context":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                messages = agents[name]["agent"].context.messages
                await ws.send_text(json.dumps({"type": "context", "name": name, "messages": messages}))

            else:
                await ws.send_text(json.dumps({"type": "error", "msg": f"unknown command: {cmd}"}))

    except WebSocketDisconnect:
        clients.remove(ws)
    except Exception as e:
        clients.remove(ws)
        print(f"WebSocket error: {e}")


# serve frontend static files
FRONT_DIR = Path(__file__).parent.parent / "front"

@app.get("/")
async def index():
    return FileResponse(FRONT_DIR / "index.html")

@app.get("/{filename}")
async def static_file(filename: str):
    path = FRONT_DIR / filename
    if path.exists():
        return FileResponse(path)
    return {"error": "not found"}

# serve noVNC if it exists
NOVNC_DIR = Path(__file__).parent.parent / "front" / "novnc"
if NOVNC_DIR.exists():
    app.mount("/novnc", StaticFiles(directory=NOVNC_DIR), name="novnc")
