
import requests
import json
import sys
import time
from urllib.parse import urlparse, parse_qs

API_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8001" # For callback access if needed, though browser does it.

def test_v2_login_success():
    print("Testing 'login v2' Success Flow...")
    session_id = "test-v2-login-success"
    
    # 1. Start Chat
    print("1. Sending Request...")
    elicitation_data = None
    
    try:
        with requests.post(
            f"{API_URL}/chat", 
            json={"message": "login v2", "user_id": "verifier", "session_id": session_id},
            stream=True
        ) as r:
            for line in r.iter_lines():
                if line:
                    event = json.loads(line)
                    if event.get("type") == "elicitation":
                        content = event.get("content", {})
                        if content.get("elicitation_type") == "url":
                            print("   SUCCESS: Received URL Elicitation")
                            elicitation_data = content.get("data", {})
                            break
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    if not elicitation_data:
        sys.exit(1)

    url = elicitation_data.get("url")
    print(f"   Auth URL: {url}")
    
    # 2. Simulate User Authentication
    # The URL points to auth-server (8002). 
    # We simply GET it. It usually redirects to callback (8001).
    # We must follow redirects so 8001 gets hit.
    print("2. Simulating Auth (Following Redirects)...")
    try:
        # We need to replace localhost with container names if running inside docker?
        # But we are running from host.
        # However, 8002 is auth-server. 8001 is mcp-server.
        # Ensure ports are mapped.
        auth_resp = requests.get(url, allow_redirects=True)
        print(f"   Auth Response Code: {auth_resp.status_code}")
        print(f"   Auth Response History: {[r.url for r in auth_resp.history]}")
        
        if auth_resp.status_code == 200 and "Authentication Successful" in auth_resp.text:
             print("   SUCCESS: Callback hit and processed.")
        else:
             print(f"   WARNING: Unexpected auth response: {auth_resp.text}")
             # We might still proceed if side-effect happened.
    except Exception as e:
        print(f"   FAILED: Auth request error: {e}")
        # If 8002/8001 not exposed, this fails.
        # Assuming they are exposed via docker-compose ports.
        sys.exit(1)

    # 3. Submit Completion
    print("3. Submitting Completion...")
    submission = {
        "session_id": session_id,
        "response_data": {}
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
                         if "Authentication successful (v2)" in content:
                             print("   SUCCESS: Validated successful login!")
                             success = True
                             break
                         
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)
        
    if not success:
         print("   FAILED: Did not receive success message.")
         sys.exit(1)

if __name__ == "__main__":
    test_v2_login_success()
