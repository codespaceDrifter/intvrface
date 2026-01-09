import re
from context import Context
from model import Model
from container import Container


def parse_commands(text: str) -> list[tuple[str, list[str]]]:
    """
    Parse >>>COMMAND args<<< from model output.
    Returns list of (command, [args]).
    """

    # >>> literal match
    # (\w+) word characters. () capture group 1. 
    #\s* whitespace zero or more  
    # (.*?) anything. zero or more. non greedy. matches as little as possible. () capture group 2
    # <<< literal match
    pattern = r'>>>(\w+)\s*(.*?)<<<' 

    #DOTALL means . matches everything including \n. to allow typing multiline arguments.
    matches = re.findall(pattern, text, re.DOTALL)


    commands = []
    for cmd, args_str in matches:
        # split args by space, but keep it simple
        args = args_str.split() if args_str.strip() else []
        commands.append((cmd.upper(), args))

    return commands


class Agent:
    """
    Orchestrates model + context + bridge + docker.

    Turn structure:
        1. model reads streaming context, outputs response
        2. output added to streaming + original context
        3. output parsed by bridge for >>>COMMANDS<<<
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

    def start(self):
        """Start the container."""
        if self.container:
            self.container.start()

    def stop(self):
        """Stop the container (preserves state)."""
        self._working = False
        if self.container:
            self.container.stop()

    def work(self, on_turn=None):
        """Loop turns until stopped. Calls on_turn(response, messages) after each."""
        self._working = True
        # need at least one message to start
        if not self.context.messages:
            self.context.add("user", content="start working")
        while self._working:
            response = self.turn()
            if on_turn:
                on_turn(response, self.context.messages)

    def chat(self, text: str):
        """Add user message to context. Agent sees it next turn."""
        self.context.add("user", content=text)

    def turn(self, user_input: str | None = None) -> str:

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

        # 2. model reads context, outputs response
        response, self._kv = self.model.call(self.context.messages, self._kv)

        # 3. add response to context
        self.context.add("assistant", content=response)

        # save kv cache
        self.context.save_kv(self._kv)

        # 4. parse commands from response
        commands = parse_commands(response)

        # 5. execute commands, collect feedback
        if commands and self.container:
            had_keyboard = False  # TYPE or KEY
            had_mouse = False     # MOVE, LDOWN, LUP, etc.

            for cmd, args in commands:
                if cmd == "TYPE":
                    # TYPE joins all args as the text to type
                    text = ' '.join(args)
                    self.container.type_text(text)
                    had_keyboard = True

                elif cmd == "KEY":
                    # KEY args are space-separated keys/modifiers
                    # join with + for xdotool: ctrl shift s -> ctrl+shift+s
                    combo = '+'.join(args)
                    self.container.key(combo)
                    had_keyboard = True

                elif cmd == "MOVE":
                    x, y = int(args[0]), int(args[1])
                    self.container.move(x, y)
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
                    # explicit LOOK - take screenshot now
                    self._add_screenshot()

                elif cmd == "TERM":
                    # explicit TERM - get terminal output now
                    self._add_terminal()

                elif cmd == "WAIT":
                    # TODO: implement wait/pause logic
                    pass

            # 6. auto-feedback: TERM after keyboard, LOOK after mouse
            if had_keyboard:
                self._add_terminal()
            if had_mouse:
                self._add_screenshot()

        # 7. check for summarization
        if self.context.needs_summary():
            summary, _ = self.model.summarize(self.context.messages, self._kv)
            self.context.apply_summary(summary)
            self._kv = None  # invalidate cache after context change

        return response

    def _add_screenshot(self):
        """Take screenshot and add to context as base64."""
        assert self.container
        path = self.container.screenshot()
        with open(path, "rb") as f:
            self.context.add("user", image_bytes=f.read())

    def _add_terminal(self):
        """Get terminal output and add to context."""
        assert self.container
        log_path = self.container.workspace / "term.log"
        output = log_path.read_text()[-5000:] if log_path.exists() else "[no terminal output]"
        self.context.add("user", content=f"[TERM]\n{output}")
