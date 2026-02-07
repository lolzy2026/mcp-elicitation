from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
import os

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")

class MCPClientManager:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        # We use SSE transport
        # Note: FastMCP at /sse creates the SSE endpoint
        try:
            # We must enter the context managers
            # In a real long-running app this is tricky. We'll open it per request or keep a global session?
            # Standard mcp client is often used as a context manager.
            # For this POC, let's try to establish a persistent session or re-connect.
            pass
        except Exception as e:
            print(f"Connection error: {e}")
            raise

    async def list_tools(self):
        # Re-connect for each operation (simplest for avoiding stale connections in POC)
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await session.list_tools()

    async def call_tool(self, name: str, arguments: dict):
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)
