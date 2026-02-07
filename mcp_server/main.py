"""
MCP Server using the official MCP SDK (FastMCP).
"""
from typing import Any, Dict, List, Optional
import uuid
import json
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import Response
import traceback
import sys

# Initialize FastMCP Server
mcp = FastMCP("MCP Server POC", host="0.0.0.0")

# In-memory storage for POC context
sessions = {}

# Tool Definitions using Decorators

@mcp.tool()
async def simple_tool(message: str) -> str:
    """
    A simple tool that echoes the input message.
    """
    return f"Processed: {message}"

@mcp.tool()
async def create_ticket(
    initial_description: str,
    reporter_name: str = None,
    priority: str = None,
    description: str = None,
    context_id: str = None
) -> str:
    """
    Create a new support ticket (v1).
    """
    if reporter_name and priority and description:
        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        return json.dumps({
            "type": "result",
            "text": f"Ticket created successfully!\nID: {ticket_id}\nReporter: {reporter_name}\nPriority: {priority}\nDescription: {description}"
        })
    
    elicitation_req = {
        "type": "elicitation",
        "elicitation_type": "form",
        "message": "Please provide ticket details",
        "fields": [
            {
                "name": "reporter_name",
                "description": "Name of the reporter",
                "type": "string",
                "required": True
            },
            {
                "name": "priority",
                "description": "Priority level",
                "type": "string",
                "enum": ["low", "medium", "high"],
                "required": True
            },
            {
                "name": "description",
                "description": "Detailed description",
                "type": "string",
                "required": True
            }
        ],
        "context_data": {
            "initial_description": initial_description
        }
    }
    return json.dumps(elicitation_req)

auth_store = {}

@mcp.custom_route("/oauth/callback", methods=["GET"])
async def oauth_callback(request: Request):
    query_params = request.query_params
    code = query_params.get("code")
    state = query_params.get("state")
    
    if code and state:
        auth_store[state] = code
        return Response(content="<html><body><h1>Authentication Successful</h1><p>You can close this tab and return to the chat.</p></body></html>", media_type="text/html")
    return Response(content="Missing code or state", status_code=400)

@mcp.tool()
async def oauth_auth(
    auth_code: str = None,
    state: str = None
) -> str:
    """
    Authenticate via OAuth (v1).
    """
    if auth_code:
        return json.dumps({
            "type": "result",
            "text": "Authentication successful! You have been logged in."
        })

    if state:
        if state in auth_store:
            code = auth_store.pop(state)
            return json.dumps({
                "type": "result",
                "text": "Authentication successful! You have been logged in."
            })
        else:
            return json.dumps({
                "type": "result",
                "text": "Authentication failed: We could not verify your login details. Please try again."
            })

    oauth_state = str(uuid.uuid4())
    callback_url = "http://localhost:8001/oauth/callback"
    auth_url = f"http://localhost:8002/auth?state={oauth_state}&callback={callback_url}"
    
    elicitation_req = {
        "type": "elicitation", 
        "elicitation_type": "url",
        "message": "Please authenticate via OAuth",
        "url": auth_url,
        "method": "GET",
        "context_data": {
            "state": oauth_state
        }
    }
    return json.dumps(elicitation_req)

# --- v2 Tools (Server-Driven Elicitation) ---

@mcp.tool()
async def create_ticket_v2(ctx: Context, initial_description: str) -> str:
    """
    Create a ticket (v2) using Server-Driven Elicitation (Form).
    """
    print(f"DEBUG: create_ticket_v2 called with {initial_description}")
    try:
        class TicketDetails(BaseModel):
            reporter_name: str
            priority: str
            description: str

        # Elicit!
        # Pass .model_json_schema() instead of class
        print(f"DEBUG: Calling elicit_form with schema: {TicketDetails.model_json_schema()}")
        result = await ctx.session.elicit_form(
            "Please provide additional ticket details for v2.",
            requestedSchema=TicketDetails.model_json_schema()
        )
        print(f"DEBUG: elicit_form result received: {result}")

        # result.content (not data) matches schema
        data = result.content
        if not data:
             raise ValueError("No data returned from elicitation")
             
        model_data = TicketDetails(**data)
        
        ticket_id = f"TICKET-V2-{uuid.uuid4().hex[:8].upper()}"
        return f"Ticket created! ID: {ticket_id}, Reporter: {model_data.reporter_name}, Priority: {model_data.priority}, Description: {model_data.description}"
    except Exception as e:
        print(f"ERROR: Exception in create_ticket_v2: {e}")
        traceback.print_exc()
        raise e

@mcp.tool()
async def login_v2(ctx: Context) -> str:
    """
    Login (v2) using Server-Driven Elicitation (URL).
    """
    session_id = uuid.uuid4().hex
    callback_url = "http://localhost:8001/oauth/callback"
    auth_url = f"http://localhost:8002/auth?state={session_id}&callback={callback_url}"
    
    result = await ctx.session.elicit_url(
        "Please authenticate to continue (v2 flow).",
        url=auth_url,
        elicitation_id=session_id
    )
    
    if session_id in auth_store:
        code = auth_store.pop(session_id)
        return "Authentication successful (v2)! You have been logged in."
    else:
        return "Authentication failed (v2): We could not verify your login details."

@mcp.tool()
async def book_appointment_v2(ctx: Context) -> str:
    """
    Book appointment using multiple elicitation steps.
    """
    class NameModel(BaseModel):
        name: str
        
    name_result = await ctx.session.elicit_form("What is the patient's name?", requestedSchema=NameModel.model_json_schema())
    name_data = NameModel(**name_result.content)
    name = name_data.name
    
    class DateModel(BaseModel):
        date: str
        
    date_result = await ctx.session.elicit_form(f"Thanks {name}. What date would you like to book?", requestedSchema=DateModel.model_json_schema())
    date_data = DateModel(**date_result.content)
    date = date_data.date
    
    return f"Appointment booked for {name} on {date}!"

@mcp.tool()
async def debug_elicitation(ctx: Context) -> str:
    """
    Simple debug tool for elicitation.
    """
    print("DEBUG: debug_elicitation called", file=sys.stderr)
    try:
        result = await ctx.session.elicit_form(
            "Debug Prompt",
            requestedSchema={"type": "object", "properties": {"foo": {"type": "string"}}}
        )
        print(f"DEBUG: result={result}", file=sys.stderr)
        # Use result.content
        return f"Debug Result: {result.content.get('foo') if result.content else 'None'}"
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise e

if __name__ == "__main__":
    import uvicorn
    # Enable access log
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8001, access_log=True)
