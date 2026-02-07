
import requests
import json
import sys
import time

API_URL = "http://localhost:8000"

def test_legacy_flow():
    print("Testing 'ticket v1' Legacy Flow...")
    session_id = "test-legacy-1"
    
    # 1. Start Chat (Trigger v1)
    print("1. Sending chat request (message='ticket')...")
    elicitation_data = None
    
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "create ticket", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                    event = json.loads(line)
                    print(f"   Received: {event}")
                    
                    if event.get("type") == "elicitation":
                        content = event.get("content", {})
                        data = content.get("data", {})
                        if data.get("is_v1"):
                            print("   SUCCESS: Detected v1 elicitation")
                            elicitation_data = data
                            break
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    if not elicitation_data:
        print("   FAILED: No v1 elicitation received")
        sys.exit(1)

    # 2. Submit Form (Trigger v1 Re-call)
    print("\n2. Submitting v1 Form...")
    tool_name = elicitation_data.get("tool_name")
    
    # Payload matches v1 fields
    responses = {
        "reporter_name": "LegacyBot",
        "priority": "low",
        "description": "Legacy works too"
    }
    
    # Merge context_data if present (v1 requirement)
    context_data = elicitation_data.get("context_data", {})
    responses.update(context_data)
    
    submission = {
        "session_id": session_id,
        "response_data": responses,
        "is_v1": True,
        "tool_name": tool_name
    }
    
    start_time = time.time()
    success = False
    
    try:
        with requests.post(
            f"{API_URL}/submit_elicitation",
            json=submission,
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                    event = json.loads(line)
                    print(f"   Received: {event}")
                    if event.get("type") == "result":
                         content = event.get("content", "")
                         if "Ticket created" in content:
                             print("   SUCCESS: Ticket created via legacy flow")
                             success = True
                             break
                             
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)
        
    if not success:
         print("   FAILED: Did not receive success result")
         sys.exit(1)

if __name__ == "__main__":
    test_legacy_flow()
