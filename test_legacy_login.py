
import requests
import json
import sys
import time

API_URL = "http://localhost:8000"

def test_legacy_login():
    print("Testing 'login v1' Legacy Flow (URL)...")
    session_id = "test-legacy-login-1"
    
    # 1. Start Chat (Trigger v1 Login)
    print("1. Sending chat request (message='login')...")
    elicitation_data = None
    
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "login", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                    event = json.loads(line)
                    print(f"   Received: {event}")
                    
                    if event.get("type") == "elicitation":
                        content = event.get("content", {})
                        data = content.get("data", {})
                        if data.get("is_v1") and data.get("elicitation_type") == "url":
                            print("   SUCCESS: Detected v1 URL elicitation")
                            elicitation_data = data
                            break
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    if not elicitation_data:
        print("   FAILED: No v1 URL elicitation received")
        sys.exit(1)

    # 2. Submit Completion (Simulate 'I have completed action')
    print("\n2. Submitting v1 Completion...")
    tool_name = elicitation_data.get("tool_name")
    context_data = elicitation_data.get("context_data", {})
    
    # Initial response_data is empty for URL flow completion
    responses = {} 
    # Merge context_data (critical: contains 'state')
    responses.update(context_data)
    
    submission = {
        "session_id": session_id,
        "response_data": responses,
        "is_v1": True,
        "tool_name": tool_name
    }
    
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
                         if "Authentication" in content or "logged in" in content:
                             print("   SUCCESS: Login completed via legacy flow")
                             success = True
                             break
                             
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)
        
    if not success:
         print("   FAILED: Did not receive success result")
         sys.exit(1)

if __name__ == "__main__":
    test_legacy_login()
