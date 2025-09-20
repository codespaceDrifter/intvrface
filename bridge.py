import os
import json
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv


class MCP_bridge:
    def __init__(self):
        self.mcp_process = None
        self.request_id = 0
        self.initialized = False
        self.start_mcp_server()
        
    def start_mcp_server(self):
        """Start MCP server and complete handshake"""
        try:
            self.mcp_process = subprocess.Popen(
                ["python3", "mcp_server.py"],
                stdin=subprocess.PIPE, #PIPE stands for PIPELINE. meaning we can write to this
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # string mode not byte mode
                bufsize=0 # no buffering
            )
            
            # Initialize
            init_request = {
                "jsonrpc": "2.0", #json remote procedure call
                "id": self.get_next_id(), #id to prevent re-sending same request
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "claudy", "version": "1.0.0"}
                }
            }
            self.send_request(init_request)
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            self.send_request(initialized_notification)
            
            self.initialized = True
            print("MCP server initialized successfully")
            
        except Exception as e:
            print(f"Failed to start MCP server: {e}")
    
    def get_next_id(self):
        self.request_id += 1
        return self.request_id
    
    def send_request(self, request):
        """Send JSON-RPC request"""
        if not self.mcp_process:
            return {"error": "MCP server not running"}
            
        try:
            request_str = json.dumps(request) + "\n"
            self.mcp_process.stdin.write(request_str)
            self.mcp_process.stdin.flush()
            
            # Only read response for requests with IDs (not notifications)
            if "id" in request:
                response_str = self.mcp_process.stdout.readline()
                return json.loads(response_str)
            return {"success": True}
            
        except Exception as e:
            return {"error": f"MCP communication failed: {e}"}
    
    def call_tool(self, tool_name, arguments):
        """Call MCP tool"""
        if not self.initialized:
            return {"error": "MCP not initialized"}
            
        request = {
            "jsonrpc": "2.0",
            "id": self.get_next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
                # arguments gets unpacked from a:5, b:3 into a = 5, b = 3
            }
        }
        return self.send_request(request)

