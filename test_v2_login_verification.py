
import requests
import json
import sys
import time

API_URL = "http://localhost:8000"

def test_v2_login_verification():
    print("Testing 'login v2' Verification Flow...")
    session_id = "test-v2-login-verify"
    
    # 1. Start Chat (Trigger v2 Login)
    print("1. Sending chat request (message='login v2')...")
    elicitation_received = False
    
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "login v2", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                    event = json.loads(line)
                    print(f"   Received: {event}")
                    
                    if event.get("type") == "elicitation":
                        # v2 elicitation is type=elicitation, content={elicitation_type: url, ...}
                        content = event.get("content", {})
                        if content.get("elicitation_type") == "url":
                            print("   SUCCESS: Detected v2 URL elicitation")
                            elicitation_received = True
                            break # Stop stream, simulating pause
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    if not elicitation_received:
        print("   FAILED: No v2 URL elicitation received")
        sys.exit(1)

    # 2. Submit Completion (Resume WITHOUT handling callback)
    # This simulates clicking "I have completed" without logging in
    print("\n2. Submitting v2 Completion (Expecting Failure)...")
    
    # v2 submission just resumes the future
    submission = {
        "session_id": session_id,
        "response_data": {} # URL completion has empty data
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
                         print(f"   Result Content: {content}")
                         if "Authentication failed (v2)" in content:
                             print("   SUCCESS: Correctly received failure message")
                             success = True
                             break
                         elif "successful" in content:
                             print("   FAILED: Received success message but shoud have failed!")
                             sys.exit(1)
                             
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)
        
    if not success:
         print("   FAILED: Did not receive expected failure result")
         sys.exit(1)

if __name__ == "__main__":
    test_v2_login_verification()
