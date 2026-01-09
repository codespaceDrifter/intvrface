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

agent parses >>>COMMAND<<< from model output. the model will be given a computer through docker + xvfb to inhabit. commands are embedded in the model's normal outputtokens formated as >>>command arguments <<<. commands are the following:

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
- KEY special_key + char . ' ' space as seperator (i.e. enter i.e. ctrl shift s ). both take a single string as argument.  

perception commands:

- LOOK (takes a screenshot of the screen puts it into model input stream)
- TERM (copies latest terminal output as raw text puts it into model input stream)

special commands:

- WAIT (pauses the model thinking, perhaps to wait for external events)

auto-feedback: agent automatically adds TERM once after all keyboard commands (TYPE/KEY) and LOOK once after all mouse commands in a response. model doesn't need to explicitly request perception - it's always provided after actions complete.

CUA models such as in the CUALDO repo will just view screen as streaming video and have their weights directly decoded as keystrokes and mouse moves if so we interpret those model numerical outputs with agent as the intvrface still into the computer.


## bash tools

we code a series of python scripts added to bashrc for the model to more easily use a computer. these will be triggered with the TYPE command into terminal. scripts are following:

read "file" "start" "end" (views file with line numbers. no start / end view entire)
write "file" "content" overwrite whole file
edit "file" "old" "new" -all (replaces the first instance of string old with string new. -all flag replaces all instances of old with new)

we use "" to seperate arguments. we use \" to escape double quotes inside the arguments

maybe true AGI will use a actual editor like vim with streaming video and won't use this.

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

jsonl format (matches Claude API exactly):

```json
{"role": "user", "content": [{"type": "text", "text": "complete this task"}]}
{"role": "assistant", "content": [{"type": "text", "text": "ok i will begin >>>TYPE cd ~/Desktop<<<"}]}
{"role": "user", "content": [{"type": "text", "text": "[TERM]\n~/Desktop"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}]}
```

consecutive same-role messages are collapsed into one. images are base64 encoded inline (PNG only). only user/assistant roles - env feedback is user.

streaming context gets trimmed when summary limit is reached. original context only adds, never deletes.

## agent

orchestrates model, context, and container. parses >>>COMMANDS<<< from model output.
each turn ends with model outputing EOS or reaching max_tokens:

1: model reads context and outputs
2: output added to context (memory + original.jsonl)
3: output parsed for >>>COMMANDS<<<
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

## ui
card like aesthetic. deleted now find in git history

## todo

- [ ] clean up frontend websocket code
- [ ] multi-agent project pages (parallel/serial task graph)
- [ ] persistent conversational agent with user notes
