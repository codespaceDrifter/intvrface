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
import subprocess
import uvicorn

app = FastAPI()

# persisted to ~/intvrface/agents.json — {"agent_name": {"novnc_port": int}, ...}
# only saves config (novnc_port). runtime state (working, container_on, etc.) is reconstructed on startup
AGENTS_FILE = Path.home() / "intvrface" / "agents.json"

# active agents: name -> {"agent": Agent, "novnc_port": int, "container_on": bool, "working": bool}
agents: dict[str, dict] = {}

BASE_PORT = 6080

def next_port() -> int:
    # find first unused port starting from BASE_PORT
    used = {info["novnc_port"] for info in agents.values()}
    port = BASE_PORT
    while port in used:
        port += 1
    return port

# connected websocket clients
clients: list[WebSocket] = []


def save_agents():
    """Save agent configs to disk."""
    AGENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    configs = {name: {"novnc_port": info["novnc_port"]} for name, info in agents.items()}
    AGENTS_FILE.write_text(json.dumps(configs))


def is_container_running(name: str) -> bool:
    """Check if a docker container is actually running."""
    result = subprocess.run(
        # ps: list processes, -q: only print container ids not the full table, -f: filter, ^{}$: regex full match
        ["docker", "ps", "-q", "-f", f"name=^{name}$"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def load_agents():
    """Load agent configs from disk on startup."""
    if not AGENTS_FILE.exists():
        return
    configs = json.loads(AGENTS_FILE.read_text())
    for name, cfg in configs.items():
        novnc_port = cfg["novnc_port"]
        model = Claude()
        agent = Agent(name, model, use_container=True, novnc_port=novnc_port)
        # check actual docker state — container may still be running from last session
        container_on = is_container_running(name)
        if container_on:
            agent.container._running = True
        agents[name] = {"agent": agent, "novnc_port": novnc_port, "container_on": container_on, "working": False}


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


# returns everything in agents except the agent objects for the frontend
def get_agents_info() -> dict:
    return {name: {"container_on": info["container_on"], "working": info["working"], "novnc_port": info["novnc_port"]} for name, info in agents.items()}


async def work_loop(name: str, info: dict):
    # loops agent.turn() until info["working"] is set to False
    agent = info["agent"]
    if not agent.context.messages:
        agent.context.add("user", content="start working")
    while info["working"]:
        try:
            await agent.turn()
            await broadcast({"type": "context", "name": name, "messages": agent.context.messages})
        except asyncio.CancelledError:
            break
        except asyncio.TimeoutError:
            print(f"[work_loop] {name} API TIMEOUT — retrying in 5s")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[work_loop] {name} error: {e}")
            await asyncio.sleep(5)


@app.websocket("/ws")
# inbound: browser sends JSON to port 8000 → OS → uvicorn → FastAPI routes /ws here → ws.receive_text()
# outbound: ws.send_text() writes to the open TCP socket → OS → browser
# both sides store a ws object with the same 4-tuple (IP, port, IP, port) — local/remote depends on perspective
# browser port is NOT 8000 — OS assigns a random port (e.g. 52847) when the browser opens the connection
# once accepted, both sides can send anytime without the other asking
#
# connection setup: browser sends HTTP upgrade request → OS → uvicorn parses raw text into headers →
# FastAPI wraps it in a WebSocket python object → calls this function → ws.accept() completes the handshake
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    # send current agents list on connect
    await ws.send_text(json.dumps({"type": "agents", "agents": get_agents_info()}))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            cmd = msg.get("cmd")

            if cmd == "list":
                await ws.send_text(json.dumps({"type": "agents", "agents": get_agents_info()}))

            elif cmd == "create":
                name = msg.get("name")
                novnc_port = next_port()

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
                }

                save_agents()
                await broadcast({"type": "agents", "agents": get_agents_info()})

            elif cmd == "start":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                # container.start() has blocking subprocess.run() calls — can't run on main thread or event loop freezes
                # to_thread spawns a separate OS thread so the main thread keeps processing websockets/tasks
                #
                # kernel
                # ├── python process
                # │   ├── OS thread 1 (main) ← event loop, websockets, asyncio tasks (switch at await)
                # │   └── OS thread 2 (to_thread) ← blocked waiting on subprocess.run
                # ├── docker process (spawned by subprocess.run, not under any thread)
                # └── ...
                #
                # await (asyncio tasks): non-blocking for external I/O (network, API calls). shares one thread, switches at await
                # threading (to_thread): non-blocking for non-python blocking code (subprocess, C calls, GPU). GIL blocks python-on-python
                # multiprocessing: truly parallel python. separate processes, separate GILs, but no shared memory
                if not info["container_on"]:
                    agent = info["agent"]
                    if agent.container and not agent.container._running:
                        # GIL in python means only one thread within a process can execute python code at one time, however container.start calls OS to spawn subprocess blocking code which is a different thread
                        await asyncio.to_thread(agent.container.start)
                    info["container_on"] = True

                # start work loop if not working
                if not info["working"]:
                    info["working"] = True
                    info["work_loop"] = asyncio.create_task(work_loop(name, info))

                await broadcast({"type": "agents", "agents": get_agents_info()})

            elif cmd == "pause":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                if info["working"]:
                    info["working"] = False
                    if info.get("work_loop") and not info["work_loop"].done():
                        info["work_loop"].cancel()
                        info["work_loop"] = None

                await broadcast({"type": "agents", "agents": get_agents_info()})

            elif cmd == "delete":
                name = msg.get("name")
                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                info["working"] = False
                if info["agent"].container:
                    await asyncio.to_thread(info["agent"].container.destroy)

                del agents[name]
                save_agents()
                await broadcast({"type": "agents", "agents": get_agents_info()})

            elif cmd == "chat_mode":
                name = msg.get("name")
                enabled = msg["enabled"]

                if name not in agents:
                    await ws.send_text(json.dumps({"type": "error", "msg": f"agent {name} not found"}))
                    continue

                info = agents[name]
                info["agent"].chat_mode = enabled
                if enabled:
                    # entering chat mode: cancel work loop immediately
                    if info["working"]:
                        info["working"] = False
                        if info.get("work_loop") and not info["work_loop"].done():
                            info["work_loop"].cancel()
                            info["work_loop"] = None
                else:
                    # leaving chat mode: cancel pending chat turn, restart work loop
                    if info.get("chat_task") and not info["chat_task"].done():
                        info["chat_task"].cancel()
                        info["chat_task"] = None
                    if info["container_on"] and not info["working"]:
                        info["working"] = True
                        info["work_loop"] = asyncio.create_task(work_loop(name, info))

                await broadcast({"type": "agents", "agents": get_agents_info()})

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

                # add user message to context — agent sees it next turn
                info["agent"].context.add("user", content=text)
                await broadcast({"type": "context", "name": name, "messages": info["agent"].context.messages})
                if info["agent"].chat_mode:
                    agent = info["agent"]
                    async def do_chat_turn(_name=name, _agent=agent):
                        try:
                            print(f"[chat_mode] calling turn for {_name}")
                            await _agent.turn()
                            await broadcast({"type": "context", "name": _name, "messages": _agent.context.messages})
                        except Exception as e:
                            print(f"[chat_mode] ERROR: {e}")
                    info["chat_task"] = asyncio.create_task(do_chat_turn())

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

# serves index.html when browser hits localhost:8000
@app.get("/")
async def index():
    return FileResponse(FRONT_DIR / "index.html")

# serves app.js, style.css, etc. when index.html requests them via <script>/<link> tags
@app.get("/{filename}")
async def static_file(filename: str):
    path = FRONT_DIR / filename
    if path.exists():
        return FileResponse(path)
    return {"error": "not found"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
