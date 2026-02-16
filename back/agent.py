import re
import asyncio
from command import parse_commands, FILE_COMMANDS
from context import Context
from model import Model
from container import Container
from prompt import COMMAND_ERROR_PROMPT

# matches a full command block: <func>CMD</func> optionally followed by <param>...</param> siblings
CMD_BLOCK_RE = re.compile(r'<func>\w+</func>(?:\s*<param>.*?</param>)*', re.DOTALL)


class Agent:
    """
    Orchestrates model + context + bridge + docker.

    Turn structure:
        1. model reads streaming context, outputs response
        2. output added to streaming + original context
        3. output parsed for <func>COMMANDS</func>
        4. commands executed in docker
        5. feedback (TERM/LOOK) added to context
        6. check for summarization
    """

    def __init__(self, name: str, model: Model, use_container: bool = True, novnc_port: int = 6080):
        # name used for context/{name}/ and workspace/{name}/
        self.name = name
        self.model = model
        self.context = Context(name)
        self.container = Container(name, novnc_port=novnc_port) if use_container else None

        # kv cache persists across turns for local models
        self._kv = self.context.load_kv()
        self._working = False
        self.chat_mode = False

    def start(self):
        """Start container if not running, start work loop if not working."""
        if self.container and not self.container._running:
            self.container.start()

    def pause(self):
        """Stop the model work loop. Container keeps running (desktop still viewable)."""
        self._working = False

    async def work(self, on_turn=None):
        """Loop turns until stopped. Calls on_turn(response, messages) after each."""
        self._working = True
        # need at least one message to start
        if not self.context.messages:
            self.context.add("user", content="start working")
        while self._working:
            response = await self.turn()
            if on_turn:
                await on_turn(response, self.context.messages)

    def chat(self, text: str):
        """Add user message to context. Agent sees it next turn."""
        self.context.add("user", content=text)


    async def turn(self, user_input: str | None = None) -> str:
        """
        Run one turn.

        Args:
            user_input: optional user message to add before model runs

        Returns:
            model's response text
        """
        # 1. add user input if provided
        if user_input:
            self.context.add("user", content=user_input)

        # 2. model reads marshaled context (environment -> user), outputs response
        response, self._kv = await self.model.call(self.context.marshal(), self._kv)

        if self.chat_mode:
            # chat mode: plain response, no commands
            self.context.add("assistant", content=response)
            self.context.save_kv(self._kv)
            return response

        # 3. split response into text segments (assistant) and command segments (command)
        last_end = 0
        for match in CMD_BLOCK_RE.finditer(response):
            before = response[last_end:match.start()].strip()
            if before:
                self.context.add("assistant", content=before)
            self.context.add("command", content=match.group(0))
            last_end = match.end()
        after = response[last_end:].strip()
        if after:
            self.context.add("assistant", content=after)

        # save kv cache
        self.context.save_kv(self._kv)

        # 4. parse commands from response
        commands = parse_commands(response)

        # 5. execute commands, collect feedback
        if commands and self.container:
            had_keyboard = False  # TYPE or KEY
            had_mouse = False     # MOVE, LDOWN, LUP, etc.

            # minimum arg counts for file commands
            MIN_ARGS = {"READ": 1, "WRITE": 2, "EDIT": 3}

            for cmd, args in commands:
                # file commands bypass terminal — direct file I/O
                if cmd in FILE_COMMANDS:
                    if len(args) < MIN_ARGS[cmd]:
                        self.context.add("environment", content=f"[SYSTEM]\n{COMMAND_ERROR_PROMPT}")
                        continue
                    if cmd == "READ":
                        self._handle_read(args)
                    elif cmd == "WRITE":
                        self._handle_write(args)
                    elif cmd == "EDIT":
                        replace_all = len(args) > 3 and args[3] == "-all"
                        self._handle_edit(args, replace_all)
                    continue

                if cmd == "TYPE":
                    self.container.type_text(args[0] if args else "")
                    had_keyboard = True

                elif cmd == "KEY":
                    # join with + for xdotool: ctrl shift s -> ctrl+shift+s
                    combo = '+'.join(args[0].split()) if args else ""
                    self.container.key(combo)
                    had_keyboard = True

                elif cmd == "MOVE":
                    self.container.move(int(args[0]), int(args[1]))
                    had_mouse = True

                elif cmd == "LCLICK":
                    self.container.click(1)
                    had_mouse = True

                elif cmd == "RCLICK":
                    self.container.click(3)
                    had_mouse = True

                elif cmd == "LDOWN":
                    self.container.mousedown(1)
                    had_mouse = True

                elif cmd == "LUP":
                    self.container.mouseup(1)
                    had_mouse = True

                elif cmd == "RDOWN":
                    self.container.mousedown(3)
                    had_mouse = True

                elif cmd == "RUP":
                    self.container.mouseup(3)
                    had_mouse = True

                elif cmd == "SCROLLUP":
                    self.container.scroll("up")
                    had_mouse = True

                elif cmd == "SCROLLDOWN":
                    self.container.scroll("down")
                    had_mouse = True

                elif cmd == "LOOK":
                    self._add_screenshot()

                elif cmd == "TERM":
                    self._add_terminal()

                elif cmd == "WAIT":
                    secs = int(args[0]) if args else 5
                    await asyncio.sleep(secs)

            # 6. auto-feedback: TERM after keyboard, LOOK after mouse
            # wait for commands to execute and xterm to flush log
            await asyncio.sleep(1)
            if had_keyboard:
                self._add_terminal()
            if had_mouse:
                self._add_screenshot()

        # 7. check for summarization
        if self.context.needs_summary():
            summary, _ = await self.model.summarize(self.context.marshal(), self._kv)
            self.context.apply_summary(summary)
            self._kv = None  # invalidate cache after context change

        return response

    def _handle_read(self, args: list[str]):
        """Read file and add contents with line numbers to context."""
        assert self.container
        content = self.container.read_file(args[0])
        lines = content.split('\n')
        start = int(args[1]) - 1 if len(args) > 1 else 0
        end = int(args[2]) if len(args) > 2 else len(lines)
        numbered = [f"{i + 1 + start:4d}| {line}" for i, line in enumerate(lines[start:end])]
        self.context.add("environment", content=f"[READ {args[0]}]\n" + '\n'.join(numbered))

    def _handle_write(self, args: list[str]):
        """Write content to file."""
        assert self.container
        self.container.write_file(args[0], args[1])
        self.context.add("environment", content=f"[WRITE {args[0]}] {len(args[1])} chars written")

    def _handle_edit(self, args: list[str], replace_all: bool):
        """Replace text in file. replace_all=True replaces all instances."""
        assert self.container
        content = self.container.read_file(args[0])
        old, new = args[1], args[2]
        count = content.count(old)
        if replace_all:
            result = content.replace(old, new)
        else:
            result = content.replace(old, new, 1)
            count = min(count, 1)
        self.container.write_file(args[0], result)
        self.context.add("environment", content=f"[EDIT {args[0]}] {count} replacement(s)")

    def _add_screenshot(self):
        """Take screenshot and add to context as environment feedback."""
        assert self.container
        path = self.container.screenshot()
        with open(path, "rb") as f:
            self.context.add("environment", image_bytes=f.read())

    def _add_terminal(self):
        """Get terminal output and add to context as environment feedback."""
        assert self.container
        log_path = self.container.workspace / "term.log"
        output = log_path.read_text()[-5000:] if log_path.exists() else "[no terminal output]"
        self.context.add("environment", content=f"[TERM]\n{output}")
