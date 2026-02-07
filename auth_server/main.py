"""
Simple Auth Server simulating an OAuth provider.
"""
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import uuid

app = FastAPI(title="Auth Server POC")

@app.get("/auth", response_class=HTMLResponse)
async def auth_page(state: str, callback: str):
    """
    Renders a simple login/approval page.
    """
    return f"""
    <html>
        <head>
            <title>Login - Auth Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; }}
                .card {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; width: 300px; }}
                h1 {{ margin-top: 0; color: #1a73e8; }}
                p {{ color: #5f6368; }}
                .btn {{ background-color: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 20px; font-weight: bold; border: none; cursor: pointer; }}
                .btn:hover {{ background-color: #1557b0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Auth Provider</h1>
                <p>The Assistant App wants to access your account.</p>
                <form action="/approve" method="post">
                    <input type="hidden" name="state" value="{state}">
                    <input type="hidden" name="callback" value="{callback}">
                    <button type="submit" class="btn">Approve Access</button>
                </form>
            </div>
        </body>
    </html>
    """

@app.post("/approve")
async def approve_auth(request: Request):
    """
    Handles the approval action and redirects back to the callback URL.
    """
    form_data = await request.form()
    state = form_data.get("state")
    callback = form_data.get("callback")
    
    # Generate a mock auth code
    code = f"AUTH-CODE-{uuid.uuid4().hex[:12].upper()}"
    
    # Redirect back to the callback URL with code and state
    redirect_url = f"{callback}?code={code}&state={state}"
    
    return RedirectResponse(url=redirect_url, status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
