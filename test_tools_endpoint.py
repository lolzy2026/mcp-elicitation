
import requests
import sys

API_URL = "http://localhost:8000"

def test_tools_endpoint():
    print("Testing GET /tools endpoint...")
    try:
        resp = requests.get(f"{API_URL}/tools")
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Response: {data}")
            tools = data.get("tools", [])
            server_url = data.get("server_url")
            
            if not tools:
                print("FAILED: No tools found in response.")
                sys.exit(1)
            
            print(f"Found {len(tools)} tools.")
            print(f"Server URL: {server_url}")
            print("SUCCESS: /tools endpoint works.")
        else:
             print(f"FAILED: Unexpected status code {resp.status_code}")
             print(resp.text)
             sys.exit(1)
    except Exception as e:
        print(f"FAILED: Connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_tools_endpoint()
