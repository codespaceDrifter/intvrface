import sys, os
sys.path.append(os.path.dirname(__file__))
from mcp.server.fastmcp import FastMCP
from importlib import import_module


TOOLS = ["tools.add_test"]
mcp = FastMCP("intvrface_suite")
for tool in TOOLS:
    # returns actual module object to call functions inside it
    module = import_module(tool)
    module.register(mcp)

# Test it
if __name__ == "__main__":
    mcp.run()
