
import asyncio
import logging
import json
import traceback
from typing import Dict, Any, Optional

# mcp imports
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import ElicitResult

# Pydantic models for events
from pydantic import BaseModel

class ElicitationEvent(BaseModel):
    type: str = "elicitation" # start, elicitation
    content: Any

class MCPClientManager:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.exit_stack = None
        self.connection_ready = asyncio.Event()
        
        # For managing the single active tool execution
        self.current_tool_future: Optional[asyncio.Future] = None
        
        # Queue for events to send to UI stream
        self.event_queue = asyncio.Queue()
        
        # Store for elicitation submission
        self.submission_future: Optional[asyncio.Future] = None
        
        # Start connection loop in background
        asyncio.create_task(self._connect())

    async def _connect(self):
        """
        Background task to maintain SSE connection.
        """
        async def connection_loop():
            try:
                # infinite retry loop? or just one shot for POC
                async with sse_client(self.server_url) as streams:
                    async with ClientSession(
                        streams[0], 
                        streams[1],
                        elicitation_callback=self._elicitation_handler
                    ) as session:
                        self.session = session
                        await session.initialize()
                        self.connection_ready.set()
                        print("DEBUG: MCP Session Connected")
                        # Keep alive
                        await asyncio.Future()
            except Exception as e:
                import traceback
                print(f"DEBUG: MCP Connection Error: {e}")
                traceback.print_exc()
                self.session = None
                self.connection_ready.clear()
            finally:
                print("DEBUG: Connection Loop Iteration Finished (or crashed)")
        
        await connection_loop()

    async def _elicitation_handler(self, context, params):
        """
        Callback when Server requests elicitation (Form or URL).
        """
        print(f"DEBUG: Received Elicitation Request: {params}")
        
        # Extract details based on params type (Union)
        # We handle both Form and URL similarly for the UI: send event -> wait result
        
        # Create a future to wait for UI submission
        self.submission_future = asyncio.Future()
        
        # Construct event payload
        # params is ElicitRequestParams (Form or URL)
        elicitation_type = params.mode # "form" or "url"
        
        # We need to serialise params to dict for JSON
        # types.ElicitRequestFormParams or URLParams
        data = params.model_dump(mode='json')
        
        event = ElicitationEvent(
            type="elicitation",
            content={
                "elicitation_type": elicitation_type,
                "data": data
            }
        )
        
        # Put on queue
        await self.event_queue.put(event)
        
        # Wait for future
        result_data = await self.submission_future
        
        # Prepare Response expected by Server (ElicitResult)
        from mcp.types import ElicitResult
        
        if elicitation_type == "url":
             # URL acceptance has no content
             return ElicitResult(action="accept")
        else:
             # Form acceptance has 'content' (not 'data')
             return ElicitResult(action="accept", content=result_data)

    async def ensure_connected(self):
        if not self.session:
             await self.connection_ready.wait()

    async def start_tool_task(self, tool_name: str, arguments: Dict[str, Any]):
        """
        Called by FastAPI to start a tool execution.
        """
        try:
            await self.ensure_connected()
        except Exception as e:
            print(f"DEBUG: ensure_connected failed: {e}")
            raise e
        
        # Clear previous queue
        self.event_queue = asyncio.Queue() 
        
        async def wrapped_call():
            try:
                print(f"DEBUG: calling tool {tool_name}...")
                # call_tool blocks until elicitation finishes!
                result = await self.session.call_tool(tool_name, arguments)
                print(f"DEBUG: tool {tool_name} returned: {result}")
                
                # If finished successfully
                await self.event_queue.put(ElicitationEvent(
                    type="result",
                    content=str(result.content[0].text) if result.content else "No content"
                ))
            except Exception as e:
                import traceback
                error_msg = f"Error executing tool {tool_name}: {e}\n{traceback.format_exc()}"
                print(error_msg) # Log to container stdout
                await self.event_queue.put(ElicitationEvent(
                    type="error",
                    content=error_msg
                ))
            finally:
                # Signal stream end
                await self.event_queue.put(None)

        # Fire and forget (task runs in background)
        self.current_tool_future = asyncio.create_task(wrapped_call())

    async def attach_to_running_task(self):
        """
        Generator for StreamingResponse.
        """
        while True:
            event = await self.event_queue.get()
            if event is None:
                break
            # Yield as SSE data
            yield json.dumps(event.model_dump()) + "\n"

    async def submit_response(self, response_data: Dict[str, Any]):
        """
        Called by UI to submit form data.
        """
        if self.submission_future and not self.submission_future.done():
            self.submission_future.set_result(response_data)
        else:
            print("WARNING: No active elicitation to submit to.")

    async def list_tools(self):
        """
        List available tools from the connected MCP server.
        """
        await self.ensure_connected()
        result = await self.session.list_tools()
        return result
