# agent/worker.py
import asyncio
from pathlib import Path
import anthropic
from agent.prompts import CLAUDY_PROMPT, WORK_PROMPT
from agent.io import DATA_DIR, load_jsonl, save_msg, READ_message


# =========================
#  GLOBAL STATE: MULTI-CLAUDY
# =========================
# AGENTS[claudy_name] = {
#   "task": asyncio.Task,
#   "stop": asyncio.Event,
# }

AGENTS = {}

client = anthropic.Anthropic()

# one step of work. this is synchronous and must be called in a OS thread
def work_step(claudy_name: str):

    print(f"work_step: {claudy_name}")

    claudy_dir: Path = DATA_DIR / claudy_name
    claudy_dir.mkdir(parents=True, exist_ok=True)

    stream_context = load_jsonl(claudy_dir / "stream_context.jsonl")

    # Hacky way to keep it working
    stream_context.append({"role": "user", "content": WORK_PROMPT})

    print("api call start")

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=stream_context,
        system=CLAUDY_PROMPT,
    )

    print("api call end")

    if response.content:
        claudy_message = {
            "role": "assistant",
            "content": response.content[0].text,
        }
        save_msg(claudy_dir / "stream_context.jsonl", claudy_message)
        return claudy_message
    else:
        return None # stops the agent

# async loop per claudy
# returns True if the agent should continue, False if it should stop
async def _agent_loop(claudy_name: str, stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            # think of the OS thread as another computer (like a web call) that can be awaited
            # to let other awaited stuff run, but must be serial itself
            claudy_message = await asyncio.to_thread(work_step, claudy_name)

            if claudy_message is None:
                READ_message(claudy_name, {"role": "assistant", "content": "AGENT ENDED: NO CONTENT"})
                break
            READ_message(claudy_name, claudy_message)

            # prevents spamming the api
            await asyncio.sleep(0.1)
    finally:
        # Make sure the event is set if we exit for any reason
        stop_event.set()


# =========================
#  PUBLIC API (CALL FROM FRONTEND ROUTES)
# =========================

async def START_agent(claudy_name: str):

    print(f"START_agent: {claudy_name}")

    # Already running?
    state = AGENTS.get(claudy_name)
    if state is not None:
        task = state["task"]
        if not task.done():
            return  # this Claudy is already running

    stop_event = asyncio.Event()
    task = asyncio.create_task(_agent_loop(claudy_name, stop_event))

    AGENTS[claudy_name] = {
        "task": task,
        "stop": stop_event,
    }


async def STOP_agent(claudy_name: str):
    state = AGENTS.get(claudy_name)
    if state is None:
        return  # nothing to stop

    stop_event: asyncio.Event = state["stop"]
    task: asyncio.Task = state["task"]

    # Signal the loop to stop
    stop_event.set()

    # Wait for it to exit cleanly
    try:
        await task
    finally:
        # Remove from registry
        AGENTS.pop(claudy_name, None)


def is_agent_running(claudy_name: str) -> bool:
    """
    Helper for status endpoints / UI.
    """
    state = AGENTS.get(claudy_name)
    if state is None:
        return False
    task: asyncio.Task = state["task"]
    return not task.done()


def list_agents():
    """
    Return a simple view of all agents and whether they're running.
    """
    return {
        name: {"running": not state["task"].done()}
        for name, state in AGENTS.items()
    }
