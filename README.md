# intvrface

wrapper for AI models to interact with the world. computer control, UI for human interaction and monitoring, potential robot control

## ~/intvrface/ folder structure

```
~/intvrface/
├── agents.json              # [{"name": "agent_1", "novnc_port": 6080}, ...]
├── docker_build/
│   └── Dockerfile           # generated dockerfile for sandbox image
├── context/
│   └── {agent_name}/
│       ├── original.jsonl   # full conversation log (never deleted)
│       └── kv_cache.pt      # cached key/values for local models
└── workspace/
    └── {agent_name}/        # mounted to /home/agent in container
        ├── term.log         # terminal output log
        ├── screenshots/
        │   └── screen.png   # latest screenshot
        └── ...              # agent's work files (code, projects, etc)
```

primy (see the primy repo) will use this. since the model can only modify weights and do IO it needs a bridge with the world.

we assume model is AGI level and use computers like a human. so no specialized MCPs or web navigators.

runs in docker + xvfb for sandboxing.

overall structure:

model -> (output) -> context -> agent -> (interpreted actions) -> enviroment
model <- (in-memory messages + kv cache) <- context <- agent <- (LOOK/TERM) <- enviroment

## commands (parsed by agent)

agent parses `<func>COMMAND</func>` from model output. the model will be given a computer through docker + xvfb to inhabit. commands are embedded in the model's normal output tokens as `<func>COMMAND</func>` with arguments in `<param>...</param>` tags. content inside `<param>` is literal — no escaping needed. commands are the following:

mouse commands:

- MOVE x y (move cursor to position)
- LCLICK (left click at current position)
- RCLICK (right click at current position)
- LDOWN (push down left mouse)
- LUP (release left mouse)
- RDOWN
- RUP
- SCROLLUP
- SCROLLDOWN

keyboard commands:

- TYPE text (type string. literal characters can be as long or short as model want)
- KEY special_key + char . ' ' space as seperator (i.e. Return i.e. ctrl shift s ). uses X11 keysym names: Return, BackSpace, Tab, Escape, Delete, Up, Down, Left, Right, Home, End, Page_Up, Page_Down, etc.

perception commands:

- LOOK (takes a screenshot of the screen puts it into model input stream)
- TERM (copies latest terminal output as raw text puts it into model input stream)

special commands:

- WAIT (pauses the model thinking, perhaps to wait for external events)

auto-feedback: agent automatically adds TERM once after all keyboard commands (TYPE/KEY) and LOOK once after all mouse commands in a response. model doesn't need to explicitly request perception - it's always provided after actions complete.

CUA models such as in the CUALDO repo will just view screen as streaming video and have their weights directly decoded as keystrokes and mouse moves if so we interpret those model numerical outputs with agent as the intvrface still into the computer.


## file commands

native `<func>` commands handled directly by the agent via file I/O on the mounted workspace. these bypass the terminal entirely — no escaping issues. parsed by `command.py`, executed by `agent.py`. arguments use `<param>...</param>` tags — content inside is literal, no escaping needed for quotes, newlines, etc.

- `<func>READ</func><param>file</param>` (view file with line numbers)
- `<func>READ</func><param>file</param><param>start</param><param>end</param>` (view line range)
- `<func>WRITE</func><param>file</param><param>content</param>` (overwrite whole file)
- `<func>EDIT</func><param>file</param><param>old</param><param>new</param>` (replace first instance)
- `<func>EDIT</func><param>file</param><param>old</param><param>new</param><param>-all</param>` (replace all instances)

not strictly needed — model could use nano/vim via TYPE, but that requires expensive screenshot loops for every edit. maybe true AGI with streaming video will just use an editor directly.

## model

model.py defines base Model class. subclasses (claude.py, llama.py, etc) implement `call(messages, kv_cache) -> (response_text, kv_cache)`. messages are in Claude API format - claude.py uses directly, other models convert as needed.

everything below model level includes weights, activations, learning functions.

## context (for token-limited models)

in a human brain, all memory is stored as activations (neuron depoloarization levels) and weights (neuron synaptic connection strength). however in a llm memory is stored as either past kv cache or tokens. maybe true AGI would also have memory be model level rather than context level. but for llm we manage context like this:

context:
- context.messages — in memory list, loaded from original.jsonl on init
- original.jsonl — full log on disk, never deleted (only appends)

when context hits ~30k words, model summarizes everything. in-memory context becomes "SUMMARIZED CONTEXT: ..." + last 5 messages. summary is assistant role (model wrote it). summary appended to original.jsonl (original keeps full history).

context folder format:

```
original.jsonl
kv_cache.pt
```

four roles in storage:
- **user** — human messages (chat input)
- **assistant** — model thinking/text output
- **command** — parsed `<func>...</func>` blocks from model output (marshaled back to assistant for API)
- **environment** — auto-feedback from the computer (TERM output, LOOK screenshots)

jsonl format:

```json
{"role": "user", "content": [{"type": "text", "text": "complete this task"}]}
{"role": "assistant", "content": [{"type": "text", "text": "ok i will begin <func>TYPE cd ~/Desktop</func>"}]}
{"role": "environment", "content": [{"type": "text", "text": "[TERM]\n~/Desktop"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}]}
```

consecutive same-role messages are collapsed into one. images are base64 encoded inline (PNG only).

`context.marshal()` converts messages to Claude API format before sending — environment → user, command → assistant (API only supports user/assistant). consecutive same-role messages are re-collapsed after conversion. if the last marshaled message is assistant, WORK_MSG is appended as user (API requires user last). this injection is API-only — not stored in context or shown in frontend.

streaming context gets trimmed when summary limit is reached. original context only adds, never deletes.

## memory

NOT IMPLEMENTED YET

this is long term memory whereas context is working memory. in a human brain or AGI this would be weight change through online learning. in a current frozen weight LLM this could simply be file edits of a memory documents maybe in a folder strucutre it can read and write from.  
perhaps this could be useful in thoughtgraph the app? or just more useful for talking to users in general. where the idea is the model learns about the user through each conversation and project and gets a compprehensive view of the user. and for thoughtgraph it's more explicit like the user can visually see the thoughts being gathered and how they relate to each other. so maybe the memory would be in a relational database that can be nicely displayed.  

## agent

orchestrates model, context, and container. parses `<func>COMMANDS</func>` from model output.
each turn ends with model outputing EOS or reaching max_tokens:

1: model reads context and outputs
2: output added to context (memory + original.jsonl)
3: output parsed for <func>COMMANDS</func>
4: commands executed in container
5: auto-feedback: TERM after keyboard, LOOK after mouse
6: check for summarization, if needed summarize (replace in-memory with summary + last 5)

RL/value model integration goes here - reward signals after actions, value estimates for planning, etc. programs in container write value to /home/agent/ (workspace), agent reads from host side.  

## data storage

all agent data stored in `~/intvrface/` (see folder structure at top)

## frontend  

we can create, start, stop, and delete agents. each come with a docker.  

we view each agent in the following layout (cycle between them with arrow keys):  
screen viewing and control with noVNC    
original context on the right side (scrollable)  
type box on the bottom (type to model)  
start/stop button on button right.



## tech stack

frontend: html/css/js
backend: python + fastapi
database: jsonl
sandboxing: docker

