"""
Parses commands from model output.

Format: <func>COMMAND</func><param>arg1</param><param>arg2</param>
Commands with no args: <func>COMMAND</func>

File commands (READ, WRITE, EDIT) bypass the terminal — agent handles them
directly via file I/O. not strictly needed, model could use nano/vim,
but avoids expensive screenshot loops.
"""

import re

# commands that do direct file I/O instead of going through the terminal
FILE_COMMANDS = {"READ", "WRITE", "EDIT"}


def parse_commands(text: str) -> list[tuple[str, list[str]]]:
    """
    Parse <func>COMMAND</func><param>...</param> from model output.
    Returns list of (command, [args]).
    """
    pattern = r'<func>(\w+)</func>((?:\s*<param>.*?</param>)*)'
    return [
        (cmd.upper(), re.findall(r'<param>(.*?)</param>', params, re.DOTALL))
        for cmd, params in re.findall(pattern, text, re.DOTALL)
    ]
