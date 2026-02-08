
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
        
        # Pool of Sessions: {session_id: ClientSession}
        self.sessions: Dict[str, ClientSession] = {}
        
        # Pool of Event Queues: {session_id: asyncio.Queue}
        self.event_queues: Dict[str, asyncio.Queue] = {}
        
        # Pool of Futures for Submission: {session_id: asyncio.Future}
        self.submission_futures: Dict[str, asyncio.Future] = {}
        
        # Lock to prevent race conditions during connection
        self.connect_lock = asyncio.Lock()

    async def get_or_create_session(self, session_id: str) -> ClientSession:
        """
        Get existing session or create a new one for the user.
        """
        async with self.connect_lock:
            if session_id in self.sessions:
                return self.sessions[session_id]
            
            # Start background connection for this user
            # We need to wait for it to be ready
            ready_event = asyncio.Event()
            
            # We must spawn the connection loop properly
            asyncio.create_task(self._connect_user(session_id, ready_event))
            
            await ready_event.wait()
            return self.sessions[session_id]

    async def _connect_user(self, session_id: str, ready_event: asyncio.Event):
        """
        Background task to maintain SSE connection for a specific user.
        """
        print(f"DEBUG: Starting new MCP connection for session {session_id}")
        try:
            async with sse_client(self.server_url) as streams:
                # We need to bind the session_id to the callback
                async def bound_callback(context, params):
                    return await self._elicitation_handler(session_id, context, params)

                async with ClientSession(
                    streams[0], 
                    streams[1],
                    elicitation_callback=bound_callback
                ) as session:
                    self.sessions[session_id] = session
                    await session.initialize()
                    
                    ready_event.set()
                    print(f"DEBUG: MCP Session Connected for {session_id}")
                    
                    # Keep alive
                    await asyncio.Future()
        except Exception as e:
            print(f"DEBUG: MCP Connection Error for {session_id}: {e}")
            traceback.print_exc()
        finally:
            print(f"DEBUG: Connection Loop Finished for {session_id}")
            # Cleanup
            if session_id in self.sessions:
                del self.sessions[session_id]
            # Do not delete queue, it belongs to active request
            ready_event.set() # Unblock if failed

    async def _elicitation_handler(self, session_id: str, context, params):
        """
        Callback when Server requests elicitation (Form or URL).
        """
        print(f"DEBUG: Received Elicitation Request for {session_id}: {params}")
        
        # Create a future to wait for UI submission SPECIFIC TO THIS SESSION
        self.submission_futures[session_id] = asyncio.Future()
        
        # Construct event payload
        try:
            elicitation_type = params.mode # "form" or "url"
            data = params.model_dump(mode='json')
            
            event = ElicitationEvent(
                type="elicitation",
                content={
                    "elicitation_type": elicitation_type,
                    "data": data
                }
            )
            
            # Put on queue for this user
            if session_id in self.event_queues:
                print(f"DEBUG: Putting Elicitation Event on queue for {session_id}")
                await self.event_queues[session_id].put(event)
            else:
                 print(f"ERROR: No event queue for {session_id}")
                 return # Should raise error
            
            # Wait for future
            result_data = await self.submission_futures[session_id]
            
            # Cleanup future
            if session_id in self.submission_futures:
                del self.submission_futures[session_id]

            # Prepare Response
            if elicitation_type == "url":
                 return ElicitResult(action="accept")
            else:
                 return ElicitResult(action="accept", content=result_data)
        except Exception as e:
             traceback.print_exc()
             raise e

    def start_tool_task(self, session_id: str, tool_name: str, arguments: Dict[str, Any]):
        """
        Called by FastAPI to start a tool execution for a user.
        WARNING: This MUST be synchronous to ensure queue is created before response stream begins.
        """
        # 1. FORCE reset queue for new run immediately (Synchronous)
        # This guarantees attach_to_running_task finds it.
        self.event_queues[session_id] = asyncio.Queue()
        
        async def wrapped_call():
            try:
                # 2. Connect Session (Async)
                # Catch connection errors here so we can report them to the UI
                try:
                    session = await self.get_or_create_session(session_id)
                except Exception as e:
                    error_msg = f"Failed to get/create session for {session_id}: {e}"
                    print(f"DEBUG: {error_msg}")
                    if session_id in self.event_queues:
                         await self.event_queues[session_id].put(ElicitationEvent(
                            type="error",
                            content=error_msg
                        ))
                    return # Stop here

                print(f"DEBUG: calling tool {tool_name} for {session_id}...")
                result = await session.call_tool(tool_name, arguments)
                print(f"DEBUG: tool {tool_name} returned for {session_id}: {result}")
                
                # Check if queue still exists (might have been cleaned up if session died)
                if session_id in self.event_queues:
                    await self.event_queues[session_id].put(ElicitationEvent(
                        type="result",
                        content=str(result.content[0].text) if result.content else "No content"
                    ))
            except Exception as e:
                import traceback
                error_msg = f"Error executing tool {tool_name}: {e}\n{traceback.format_exc()}"
                print(error_msg)
                if session_id in self.event_queues:
                    await self.event_queues[session_id].put(ElicitationEvent(
                        type="error",
                        content=error_msg
                    ))
            finally:
                # Signal stream end
                if session_id in self.event_queues:
                    await self.event_queues[session_id].put(None)

        # Fire and forget task
        asyncio.create_task(wrapped_call())

    async def attach_to_running_task(self, session_id: str):
        """
        Generator for StreamingResponse.
        """
        if session_id not in self.event_queues:
             # If no queue, maybe session died or never started
             yield json.dumps({"type": "error", "content": "Session not found"}) + "\n"
             return

        print(f"DEBUG: attach_to_running_task started for {session_id}")
        queue = self.event_queues[session_id]
        while True:
            event = await queue.get()
            if event is None:
                print(f"DEBUG: attach_to_running_task finished for {session_id} (None event)")
                break
            print(f"DEBUG: attach_to_running_task yielding event for {session_id}: {event.type}")
            yield json.dumps(event.model_dump()) + "\n"

    async def submit_response(self, session_id: str, response_data: Dict[str, Any]):
        """
        Called by UI to submit form data.
        """
        if session_id in self.submission_futures:
            future = self.submission_futures[session_id]
            if not future.done():
                future.set_result(response_data)
            else:
                print(f"WARNING: Future for {session_id} already done.")
        else:
            print(f"WARNING: No active elicitation to submit to for {session_id}.")

    async def list_tools(self):
        """
        List available tools. Uses a temporary or default session.
        For POC we just create a temp session or use a 'system' session.
        """
        # We can use a 'system' session for tool listing
        session = await self.get_or_create_session("system_tool_lister")
        return await session.list_tools()
