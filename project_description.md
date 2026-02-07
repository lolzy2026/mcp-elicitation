# MCP Integration POC for AI Assistant
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    UI Layer     │────▶│  Assistant      │────▶│    MCP          │
│  (Streamlit)    │◀────│  Backend        │◀────│    Gateway/     │
│                 │     │  (FastAPI)      │     │    Server       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                                  │
        │ User Interaction                                 | 
        │                                                  | 
        │                                                  |
┌─────────────────┐                                        | 
│    Auth Server  │                         
│   (FastAPI)     │  - - - - - - - - - - - - - - - - - - - -                                  

## Objective
Build an end-to-end POC demonstrating MCP (Model Context Protocol) integration with an AI assistant that supports tool calling with elicitation modes (form and URL).

## System Components

### 1. MCP Server (FastAPI)
Create a simple MCP server with 3 tools:
1. **simple_tool**: Basic tool that returns a message
2. **create_ticket** (Form Elicitation): Tool that requests additional form fields
3. **oauth_auth** (URL Elicitation): Tool that redirects to OAuth flow

### 2. Assistant Backend (FastAPI)
- REST API endpoint: `/chat`
- Integrates with LLM (use mock LLM for POC)
- MCP Client using `langchain-mcp-adapter`
- Handles elicitation flow between UI and MCP server
- Manages session state for multi-step tool calls

### 3. UI Layer (Streamlit)
- Chat interface
- Handles form rendering for elicitation
- Manages redirects for URL elicitation
- Maintains chat history

### 4. Auth Server (FastAPI)
- Simple OAuth-like authentication
- Callback endpoint for MCP server
- Token generation

## Detailed Requirements

### MCP Server Implementation
```python
# Tools specification:
1. simple_tool:
   - Input: message (string)
   - Output: Processed message

2. create_ticket:
   - Elicitation: form
   - Fields: reporter_name (string), priority (enum: low, medium, high), description (string)
   - Output: Ticket ID

3. oauth_auth:
   - Elicitation: url
   - Redirect to auth server
   - Callback to receive token


/project
  /mcp_server
    - main.py
    - Dockerfile
    - requirements.txt
  /assistant_backend
    - main.py
    - mcp_client.py
    - elicitation_handler.py
    - Dockerfile
    - requirements.txt
  /ui
    - app.py
    - Dockerfile
    - requirements.txt
  /auth_server
    - main.py
    - Dockerfile
    - requirements.txt
  docker-compose.yml
  README.md


## Implementation Details and Code Structure

Here's the detailed implementation plan for each component:

### 1. MCP Server (`mcp_server/main.py`)

```python
"""
Simple MCP server with three tools demonstrating different elicitation modes.
Uses HTTP transport as per MCP specification.
"""
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
import uvicorn
import json

app = FastAPI(title="MCP Server POC")

# Tool definitions
class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}

class ToolResult(BaseModel):
    content: List[Dict[str, Any]]
    is_error: bool = False

class ElicitationRequest(BaseModel):
    type: str  # "form" or "url"
    fields: Optional[List[Dict]] = None
    url: Optional[str] = None
    message: Optional[str] = None

class TicketCreateForm(BaseModel):
    reporter_name: str = Field(..., description="Name of the reporter")
    priority: str = Field(..., description="Priority level", enum=["low", "medium", "high"])
    description: str = Field(..., description="Detailed description of the issue")

# In-memory storage for POC
sessions = {}

@app.post("/tools/list")
async def list_tools():
    """List available tools"""
    tools = [
        {
            "name": "simple_tool",
            "description": "A simple tool that echoes the input",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to process"}
                },
                "required": ["message"]
            }
        },
        {
            "name": "create_ticket",
            "description": "Create a new support ticket (requires form elicitation)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "initial_description": {"type": "string", "description": "Initial issue description"}
                }
            }
        },
        {
            "name": "oauth_auth",
            "description": "Authenticate via OAuth (requires URL elicitation)",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    return {"tools": tools}

@app.post("/tools/call")
async def call_tool(request: Request):
    """Call a tool with elicitation support"""
    data = await request.json()
    tool_name = data.get("name")
    arguments = data.get("arguments", {})
    session_id = data.get("sessionId")
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Initialize session if not exists
    if session_id not in sessions:
        sessions[session_id] = {
            "state": "initial",
            "data": {},
            "created_at": datetime.now()
        }
    
    session = sessions[session_id]
    
    # Handle different tools
    if tool_name == "simple_tool":
        # Simple tool - no elicitation needed
        message = arguments.get("message", "No message provided")
        return {
            "result": {
                "content": [{"type": "text", "text": f"Processed: {message}"}]
            },
            "sessionId": session_id
        }
    
    elif tool_name == "create_ticket":
        if session["state"] == "initial":
            # First call - request form elicitation
            session["state"] = "awaiting_form"
            session["data"]["initial_description"] = arguments.get("initial_description", "")
            
            elicitation = {
                "type": "form",
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
                ]
            }
            return {
                "elicitation": elicitation,
                "sessionId": session_id
            }
        elif session["state"] == "awaiting_form":
            # Form submitted - create ticket
            reporter_name = arguments.get("reporter_name")
            priority = arguments.get("priority")
            description = arguments.get("description")
            
            # Create mock ticket
            ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
            
            # Clear session
            del sessions[session_id]
            
            return {
                "result": {
                    "content": [{
                        "type": "text", 
                        "text": f"Ticket created successfully!\nID: {ticket_id}\nReporter: {reporter_name}\nPriority: {priority}\nDescription: {description}"
                    }]
                },
                "sessionId": session_id
            }
    
    elif tool_name == "oauth_auth":
        if session["state"] == "initial":
            # Request URL elicitation
            session["state"] = "awaiting_oauth"
            
            # Generate OAuth state
            oauth_state = str(uuid.uuid4())
            session["data"]["oauth_state"] = oauth_state
            
            elicitation = {
                "type": "url",
                "message": "Please authenticate via OAuth",
                "url": f"http://auth-server:8002/auth?state={oauth_state}&callback=http://mcp-server:8001/oauth/callback",
                "method": "GET"
            }
            return {
                "elicitation": elicitation,
                "sessionId": session_id
            }
    
    raise HTTPException(status_code=400, detail=f"Unknown tool or invalid state: {tool_name}")

@app.get("/oauth/callback")
async def oauth_callback(state: str, code: str, request: Request):
    """Handle OAuth callback from auth server"""
    # Find session by state
    session_id = None
    for sid, session_data in sessions.items():
        if session_data.get("data", {}).get("oauth_state") == state:
            session_id = sid
            break
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid state")
    
    session = sessions[session_id]
    session["state"] = "authenticated"
    session["data"]["auth_code"] = code
    
    # For POC, we'll return a simple HTML page that notifies completion
    html_content = """
    <html>
        <head>
            <title>Authentication Complete</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 40px; text-align: center; }
        .success { color: green; font-size: 24px; margin-bottom: 20px; }
        .message { color: #666; margin-top: 20px; }
    </style>
    </head>
    <body>
        <div class="success">✓ Authentication Successful!</div>
        <div class="message">You can now return to the chat application.</div>
        <script>
        // Notify parent window if in iframe
        if (window.parent !== window) {
            window.parent.postMessage({
                type: 'oauth_complete',
                state: '%s',
                code: '%s'
            }, '*');
        }
        </script>
    </body>
    </html>
    """ % (state, code)
    
    return Response(content=html_content, media_type="text/html")

@app.post("/sessions/{session_id}/continue")
async def continue_session(session_id: str, request: Request):
    """Continue a session after elicitation"""
    data = await request.json()
    arguments = data.get("arguments", {})
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    if session["state"] == "authenticated":
        # OAuth completed
        auth_code = session["data"].get("auth_code")
        
        # Clear session
        del sessions[session_id]
        
        return {
            "result": {
                "content": [{
                    "type": "text", 
                    "text": f"Authentication successful! Auth code: {auth_code[:10]}..."
                }]
            },
            "sessionId": session_id
        }
    
    raise HTTPException(status_code=400, detail="Invalid session state")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)