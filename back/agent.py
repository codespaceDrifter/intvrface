import re
import asyncio
from context import Context
from model import Model
from container import Container
from prompt import COMMAND_ERROR_PROMPT


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
        self.chat_mode = False

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
        # 3+4. split response into text/command segments AND parse commands in one pass
        # finditer returns match objects with .start()/.end() positions + capture groups
        # group(0): full match for context logging, group(1): command name, group(2): raw params
        CMD_RE = re.compile(r'<func>(\w+)</func>((?:\s*<param>.*?</param>)*)', re.DOTALL)
        last_end = 0
        commands = []
        for match in CMD_RE.finditer(response):
            before = response[last_end:match.start()].strip()
            if before:
                self.context.add("assistant", content=before)
            self.context.add("command", content=match.group(0))
            last_end = match.end()
            commands.append((match.group(1).upper(), re.findall(r'<param>(.*?)</param>', match.group(2), re.DOTALL)))
        after = response[last_end:].strip()
        if after:
            self.context.add("assistant", content=after)

        # save kv cache
        self.context.save_kv(self._kv)

        # 5. execute commands, collect feedback
        if commands and self.container:
            had_input = False

            # minimum arg counts for file commands
            MIN_ARGS = {"READ": 1, "WRITE": 2, "EDIT": 4}
            # commands that do direct file I/O instead of going through the terminal
            FILE_COMMANDS = {"READ", "WRITE", "EDIT"}

            for cmd, args in commands:
                # file commands bypass terminal — direct file I/O
                # commands format: list[tuple[str,list[str]]
                if cmd in FILE_COMMANDS:
                    if len(args) < MIN_ARGS[cmd]:
                        self.context.add("environment", content=f"[SYSTEM]\n{COMMAND_ERROR_PROMPT}")
                        continue
                    if cmd == "READ":
                        self._handle_read(args)
                    elif cmd == "WRITE":
                        self._handle_write(args)
                    elif cmd == "EDIT":
                        self._handle_edit(args)
                    continue

                if cmd == "TYPE":
                    self.container.type_text(args[0] if args else "")
                    had_input = True

                elif cmd == "KEY":
                    # join with + for xdotool: each <param> is one key -> ctrl+shift+s
                    combo = '+'.join(args)
                    self.container.key(combo)
                    had_input = True

                elif cmd == "MOVE":
                    self.container.move(int(args[0]), int(args[1]))
                    had_input = True

                elif cmd == "LCLICK":
                    self.container.click(1)
                    had_input = True

                elif cmd == "RCLICK":
                    self.container.click(3)
                    had_input = True

                elif cmd == "DCLICK":
                    self.container.double_click()
                    had_input = True

                elif cmd == "LDOWN":
                    self.container.mousedown(1)
                    had_input = True

                elif cmd == "LUP":
                    self.container.mouseup(1)
                    had_input = True

                elif cmd == "RDOWN":
                    self.container.mousedown(3)
                    had_input = True

                elif cmd == "RUP":
                    self.container.mouseup(3)
                    had_input = True

                elif cmd == "SCROLLUP":
                    self.container.scroll("up")
                    had_input = True

                elif cmd == "SCROLLDOWN":
                    self.container.scroll("down")
                    had_input = True

                elif cmd == "LOOK":
                    self._add_screenshot()

                elif cmd == "TERM":
                    self._add_terminal()

                elif cmd == "WAIT":
                    secs = int(args[0]) if args else 5
                    await asyncio.sleep(secs)

            # 6. auto-feedback: check focused window to give relevant feedback
            if had_input:
                await asyncio.sleep(1)
                focused = self.container.run("xdotool getactivewindow getwindowclassname").strip()
                if focused == "XTerm":
                    self._add_terminal()
                else:
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

    def _handle_edit(self, args: list[str]):
        # args: [0] file path, [1] old text, [2] new text, [3] which occurrence: "all" or 0-indexed int
        assert self.container
        which = args[3]
        content = self.container.read_file(args[0])
        old, new = args[1], args[2]
        count = content.count(old)
        if count == 0:
            self.context.add("environment", content=f"[EDIT {args[0]}] text not found")
            return
        if which == "all":
            result = content.replace(old, new)
        else:
            n = int(which)
            if n >= count:
                self.context.add("environment", content=f"[ERROR. EDIT {args[0]}] occurrence {n} requested but only {count} found (0-indexed)")
                return
            # find the start index of the nth occurrence (0-indexed)
            idx = -1
            for _ in range(n + 1):
                idx = content.index(old, idx + 1)
            result = content[:idx] + new + content[idx + len(old):]
        self.container.write_file(args[0], result)
        self.context.add("environment", content=f"[EDIT {args[0]}] done")

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
