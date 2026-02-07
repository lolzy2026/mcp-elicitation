import sys
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Add project root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_server.main import app as mcp_app
from assistant_backend.main import app as assistant_app
from assistant_backend.mcp_client import MCPClient

# Mocks
class MockMCPClient(MCPClient):
    def __init__(self, mcp_client):
        self.client = mcp_client
    
    def call_tool(self, name, arguments=None, session_id=None):
        payload = {
            "name": name,
            "arguments": arguments or {},
            "sessionId": session_id
        }
        response = self.client.post("/tools/call", json=payload)
        response.raise_for_status()
        return response.json()

    def continue_session(self, session_id, arguments=None):
        payload = {
            "arguments": arguments or {}
        }
        response = self.client.post(f"/sessions/{session_id}/continue", json=payload)
        response.raise_for_status()
        return response.json()

def test_simple_tool_flow():
    mcp_client = TestClient(mcp_app)
    
    # Patch the real MCPClient in assistant_backend with our Mock that calls the TestClient
    with patch('assistant_backend.main.mcp_client', MockMCPClient(mcp_client)):
        client = TestClient(assistant_app)
        
        # Test Chat
        response = client.post("/chat", json={"message": "hello", "user_id": "test"})
        data = response.json()
        
        assert data["type"] == "message"
        assert "Processed: hello" in data["content"]

def test_create_ticket_flow():
    mcp_client = TestClient(mcp_app)
    
    with patch('assistant_backend.main.mcp_client', MockMCPClient(mcp_client)):
        client = TestClient(assistant_app)
        
        # 1. Trigger Elicitation
        response = client.post("/chat", json={"message": "create ticket for broken printer", "user_id": "test"})
        data = response.json()
        
        assert data["type"] == "elicitation"
        assert data["content"]["type"] == "form"
        assert len(data["content"]["fields"]) == 3
        
        session_id = data["session_id"]
        
        # 2. Submit Elicitation
        form_data = {
            "reporter_name": "John Doe",
            "priority": "high",
            "description": "Printer is on fire"
        }
        
        response = client.post("/submit_elicitation", json={
            "session_id": session_id,
            "response_data": form_data
        })
        data = response.json()
        
        assert data["type"] == "message"
        assert "Ticket created successfully" in data["content"]
        assert "John Doe" in data["content"]

def test_auth_flow():
    mcp_client = TestClient(mcp_app)
    
    with patch('assistant_backend.main.mcp_client', MockMCPClient(mcp_client)):
        client = TestClient(assistant_app)
        
        # 1. Trigger Auth
        response = client.post("/chat", json={"message": "login please", "user_id": "test"})
        data = response.json()
        
        assert data["type"] == "elicitation"
        assert data["content"]["type"] == "url"
        
        session_id = data["session_id"]
        mcp_session_id = data["mcp_session_id"]
        url = data["content"]["url"]
        
        # Parse state from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        state = params['state'][0]
        
        # 2. Simulate Callback (hitting MCP directly as Auth Server would redirect)
        # Note: In real world, browser hits this. We simulate the request to MCP.
        callback_response = mcp_client.get(f"/oauth/callback?state={state}&code=TEST_CODE")
        assert callback_response.status_code == 200
        
        # 3. Continue Session (User clicks "I'm done" in UI)
        response = client.post("/submit_elicitation", json={
            "session_id": session_id,
            "response_data": {}
        })
        data = response.json()
        
        assert data["type"] == "message"
        assert "Authentication successful" in data["content"]
        assert "TEST_CODE" in data["content"]

if __name__ == "__main__":
    # If run directly, define a way to run it, but pytest is better
    print("Run with pytest")
