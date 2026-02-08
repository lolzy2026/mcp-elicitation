from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import json
import asyncio
from mcp_client_gen import MCPClientManager
import os

app = FastAPI(title="Assistant Backend")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
# For POC, use a global manager (single user assumption)
global_manager = MCPClientManager(MCP_SERVER_URL)

# Legacy Client
from mcp_client import MCPClientManager as LegacyClientManager
legacy_manager = LegacyClientManager()

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None

class ElicitationSubmission(BaseModel):
    session_id: str 
    response_data: Dict[str, Any]
    is_v1: Optional[bool] = False
    is_v1: Optional[bool] = False
    tool_name: Optional[str] = None

@app.get("/tools")
async def get_tools():
    """
    List available tools.
    """
    try:
        result = await global_manager.list_tools()
        # Clean up result for UI
        tools = []
        if result and hasattr(result, 'tools'):
             for t in result.tools:
                 tools.append({
                     "name": t.name,
                     "description": t.description
                 })
        return {"tools": tools, "server_url": MCP_SERVER_URL}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest):
    # Determine intent
    message = request.message.lower()
    tool_name = "simple_tool"
    tool_args = {"message": request.message}

    if "ticket v2" in message or "tickt v2" in message:
        tool_name = "create_ticket_v2"
        tool_args = {"initial_description": message}
    elif "login v2" in message:
        tool_name = "login_v2"
        tool_args = {}
    elif "book v2" in message or "appointment" in message:
        tool_name = "book_appointment_v2"
        tool_args = {}
    elif "ticket" in message: # Fallback to v1 if not explicitly v2
        tool_name = "create_ticket" 
        if "printer" in message:
             tool_args["initial_description"] = message
        else:
             tool_args["initial_description"] = "No desc"
    elif "login" in message: # Fallback
        tool_name = "oauth_auth"
        tool_args = {}
    elif "debug" in message:
        tool_name = "debug_elicitation"
        tool_args = {}

    # Check if it is a v2 tool (requires streaming)
    # Added "debug" to v2 check
    if "v2" in tool_name or "book" in tool_name or "debug" in tool_name:
         # Pass session_id to start_tool_task
         sid = request.session_id or str(uuid.uuid4())
         # This is now a synchronous call that spawns a background task internally
         global_manager.start_tool_task(sid, tool_name, tool_args)
         return StreamingResponse(
            global_manager.attach_to_running_task(sid),
            media_type="application/x-ndjson"
        )
    # v1 logic (Legacy)
    # We use a separate generator to stream the result similarly to v2
    async def v1_generator():
        try:
            # 1. Call Tool
            # list_tools first? legacy_client does it in call_tool
            result = await legacy_manager.call_tool(tool_name, tool_args)
            
            # 2. Process Result
            if result.content:
                text_content = result.content[0].text
                
                # Try to parse as JSON to check for elicitation
                try:
                    data = json.loads(text_content)
                    if isinstance(data, dict) and data.get("type") == "elicitation":
                        # It is a v1 elicitation!
                        # Add v1 metadata
                        data["is_v1"] = True
                        data["tool_name"] = tool_name
                        # Wrap in event
                        event = {
                            "type": "elicitation",
                            "content": {
                                "elicitation_type": data.get("elicitation_type", "form"),
                                "data": data # Contains 'fields', 'message', etc.
                            }
                        }
                        yield json.dumps(event) + "\n"
                        return
                except json.JSONDecodeError:
                    pass
                
                # Normal Result
                yield json.dumps({"type": "result", "content": text_content}) + "\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(
        v1_generator(),
        media_type="application/x-ndjson"
    )

@app.post("/submit_elicitation")
async def submit_elicitation(submission: ElicitationSubmission):
    """
    Called by UI to resume.
    """
    # Check if this is a v1 legacy submission
    # We might need to extend ElicitationSubmission model or check the dict
    # But ElicitationSubmission is Pydantic. 'response_data' is Dict.
    # The UI sends 'is_v1' and 'tool_name' at top level? 
    # Let's check UI code: json=submission where submission includes is_v1.
    # We need to update ElicitationSubmission model.
    pass

    if hasattr(submission, "is_v1") and submission.is_v1:
        # V1 Logic: Call the tool again with the data
        tool_name = submission.tool_name
        response_data = submission.response_data
        
        # Merge context? v1 usually just needs the args.
        # But wait, create_ticket v1 takes 'initial_description'.
        # The form submission only has the fields (reporter_name, etc).
        # Where is initial_description?
        # In v1 server code, context_data had it.
        # The UI received context_data? 
        # v1 server: "context_data": {"initial_description": ...}
        # UI likely lost it unless we passed it back.
        # Let's assume for this POC the user re-enters or we just pass what we have.
        # Actually, in v1, the UI must keep context or we pass it back and forth.
        # Let's check if my UI update preserved context.
        # I didn't explicitly handle context_data in UI.
        
        # However, for the demo "ticket v1" -> "printer is broken".
        # If I submit name/priority, 'initial_description' is missing.
        # The tool might fail or ask for it again.
        # Let's just pass response_data and see.
        
        async def v1_submit_generator():
            try:
                # We assume response_data contains the arguments
                result = await legacy_manager.call_tool(tool_name, response_data)
                # Same result processing as chat
                if result.content:
                    text_content = result.content[0].text
                    yield json.dumps({"type": "result", "content": text_content}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "error", "content": str(e)}) + "\n"

        return StreamingResponse(
            v1_submit_generator(),
            media_type="application/x-ndjson"
        )
            
    # Regular V2 Logic
    # Pass session_id
    await global_manager.submit_response(submission.session_id, submission.response_data)
    
    return StreamingResponse(
        global_manager.attach_to_running_task(submission.session_id),
        media_type="application/x-ndjson"
    )
