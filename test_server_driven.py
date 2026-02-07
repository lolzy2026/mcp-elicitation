import requests
import json
import sys
import asyncio
from mcp import ClientSession

# MCP Direct Client for debugging
from mcp.client.sse import sse_client

API_URL = "http://localhost:8000"
MCP_URL = "http://localhost:8001/sse"

async def test_connectivity():
    print("Testing Basic Connectivity (List Tools)...")
    try:
        # We need to install `mcp` in the environment running this script
        # Assuming venv has `mcp` installed.
        async with sse_client(MCP_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.list_tools()
                tool_names = [t.name for t in result.tools]
                print(f"   Tools Found: {tool_names}")
                
                if "create_ticket_v2" in tool_names:
                    print("   SUCCESS: v2 tools detected.")
                else:
                    print("   WARNING: v2 tools NOT detected.")
                    return False
                return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   FAILED: Connection Error to MCP Server directly: {e}")
        return False

def test_debug_elicitation():
    print("\nTesting 'debug_elicitation' flow...")
    session_id = "test-debug-1"
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "debug elicitation", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            elicitation_received = False
            for line in r.iter_lines():
                if line:
                    try:
                        event = json.loads(line)
                        print(f"   Received Data: {event}")
                        if event.get("type") == "elicitation":
                            print("   SUCCESS: Received Elicitation Request")
                            elicitation_received = True
                            break
                        elif event.get("type") == "error":
                             print(f"   RECEIVED ERROR: {event.get('content')}")
                    except:
                        pass
            
            if not elicitation_received:
                print("   FAILED: Did not receive elicitation event.")
                sys.exit(1)

        # Submit
        print("   Submitting debug form...")
        with requests.post(
            f"{API_URL}/submit_elicitation",
            json={"session_id": session_id, "response_data": {"foo": "bar"}},
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                     print(f"   Received Resumed Data: {line}")
                     event = json.loads(line)
                     if event.get("type") == "result":
                         print("   SUCCESS: Final Result Received")

    except Exception as e:
         print(f"   FAILED: Request Error: {e}")
         sys.exit(1)

def test_v2_flow():
    print("\nTesting 'ticket v2' flow via Backend...")
    
    session_id = "test-verification-1"
    
    # 1. Start Chat (Streaming)
    print("1. Sending chat request...")
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "ticket v2", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            elicitation_received = False
            for line in r.iter_lines():
                if line:
                    try:
                        event = json.loads(line)
                        print(f"   Received Data: {event}")
                        if event.get("type") == "elicitation":
                            print("   SUCCESS: Received Elicitation Request")
                            elicitation_received = True
                            break # Stop consuming, simulate UI pause
                        elif event.get("type") == "error":
                             print("   RECEIVED ERROR EVENT")
                    except:
                        pass
            
            if not elicitation_received:
                print("   FAILED: Did not receive elicitation event.")
                sys.exit(1)

        # 2. Submit Form
        print("\n2. Submitting Elicitation Payload...")
        payload = {
            "reporter_name": "VerificationBot",
            "priority": "high",
            "description": "System verified."
        }
        
        # Submit and Resume Stream
        with requests.post(
            f"{API_URL}/submit_elicitation",
            json={"session_id": session_id, "response_data": payload},
            stream=True
        ) as r:
            final_result_received = False
            for line in r.iter_lines():
                if line:
                    try:
                        event = json.loads(line)
                        print(f"   Received Resumed Data: {event}")
                        content = event.get("content", "")
                        if event.get("type") == "result" and "Ticket created" in str(content):
                            print("   SUCCESS: Received Final Result")
                            final_result_received = True
                    except:
                        pass
                        
            if not final_result_received:
                print("   FAILED: Did not receive final ticket confirmation.")
                sys.exit(1)

        print("\nVerification Complete: Server-Driven Elicitation V2 works!")
    except Exception as e:
         print(f"   FAILED: Request Error: {e}")
         sys.exit(1)

if __name__ == "__main__":
    if asyncio.run(test_connectivity()):
        test_debug_elicitation() 
        test_v2_flow()
    else:
        print("Skipping v2 flow due to connectivity failure.")
        sys.exit(1)
