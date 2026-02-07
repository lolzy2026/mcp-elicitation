import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("FastAPI or TestClient not installed. Skipping tests.")
    sys.exit(0)

from assistant_backend.main import app as assistant_app
from assistant_backend.mcp_client import MCPClientManager

# Mock Result Object from MCP SDK
class MockTextContent:
    def __init__(self, text):
        self.text = text

class MockToolResult:
    def __init__(self, text):
        self.content = [MockTextContent(text)]

class TestRefactoredFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(assistant_app)
        
    def test_simple_tool_flow(self):
        print("\nTesting Simple Tool Flow...")
        
        # Mock the MCP manager
        mock_manager = AsyncMock()
        mock_manager.call_tool.return_value = MockToolResult("Processed: hello")
        
        with patch('assistant_backend.main.mcp_manager', mock_manager):
            response = self.client.post("/chat", json={"message": "hello", "user_id": "test"})
            data = response.json()
            print(f"Response: {data}")
            
            self.assertEqual(data["type"], "message")
            self.assertEqual(data["content"], "Processed: hello")

    def test_create_ticket_elicitation(self):
        print("\nTesting Create Ticket Elicitation...")
        
        # Mock elicitation response
        elicitation_payload = {
            "type": "elicitation",
            "elicitation_type": "form",
            "message": "Fill form",
            "fields": []
        }
        mock_manager = AsyncMock()
        mock_manager.call_tool.return_value = MockToolResult(json.dumps(elicitation_payload))
        
        with patch('assistant_backend.main.mcp_manager', mock_manager):
            response = self.client.post("/chat", json={"message": "create ticket", "user_id": "test"})
            data = response.json()
            print(f"Response: {data}")
            
            self.assertEqual(data["type"], "elicitation")
            self.assertEqual(data["content"]["elicitation_type"], "form")

    def test_submit_elicitation(self):
        print("\nTesting Submit Elicitation...")
        
        # Mock result after submission
        mock_manager = AsyncMock()
        mock_manager.call_tool.return_value = MockToolResult(json.dumps({
            "type": "result",
            "text": "Ticket Created"
        }))
        
        with patch('assistant_backend.main.mcp_manager', mock_manager):
            response = self.client.post("/submit_elicitation", json={
                "session_id": "123",
                "response_data": {"reporter_name": "Test"}
            })
            data = response.json()
            print(f"Response: {data}")
            
            self.assertEqual(data["type"], "message")
            self.assertEqual(data["content"], "Ticket Created")

if __name__ == '__main__':
    unittest.main()
