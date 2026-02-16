"""
Bash tools baked into the container image.
Model uses these via TYPE command into terminal.

Arguments are "" delimited. Use \" to escape quotes inside arguments.
    read "file" "start" "end"
    write "file" "content"
    edit "file" "old" "new" -all
"""

# view file with line numbers. omit start/end for entire file.
READ_TOOL = r"""#!/usr/bin/env python3
import sys, re

args = re.findall(r'"((?:[^"\\]|\\.)*)"', ' '.join(sys.argv[1:]))
assert len(args) >= 1, 'usage: read "file" ["start"] ["end"]'

path = args[0]
start = int(args[1]) if len(args) > 1 else 1
end = int(args[2]) if len(args) > 2 else None

with open(path) as f:
    lines = f.readlines()

end = end or len(lines)
for i in range(start - 1, min(end, len(lines))):
    print(f"{i + 1:4d} | {lines[i]}", end="")
"""

# overwrite entire file with content
WRITE_TOOL = r"""#!/usr/bin/env python3
import sys, re

args = re.findall(r'"((?:[^"\\]|\\.)*)"', ' '.join(sys.argv[1:]))
assert len(args) == 2, 'usage: write "file" "content"'

path, content = args[0], args[1].replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
with open(path, 'w') as f:
    f.write(content)
print(f"wrote {len(content)} chars to {path}")
"""

# replace first instance of old with new. -all replaces all.
EDIT_TOOL = r"""#!/usr/bin/env python3
import sys, re

raw = ' '.join(sys.argv[1:])
args = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
assert len(args) == 3, 'usage: edit "file" "old" "new" [-all]'

path = args[0]
old = args[1].replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
new = args[2].replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
replace_all = '-all' in raw.split('"')[-1]

with open(path) as f:
    text = f.read()

assert old in text, f"string not found in {path}"

if replace_all:
    count = text.count(old)
    text = text.replace(old, new)
else:
    count = 1
    text = text.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(text)
print(f"replaced {count} occurrence(s) in {path}")
"""
