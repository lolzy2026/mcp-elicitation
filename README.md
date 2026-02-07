# MCP Server-Driven Elicitation POC

This project is a Proof of Concept (POC) demonstrating **Server-Driven Elicitation** using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It showcases how an MCP Server can pause tool execution to request additional information (forms or generic data) from the client/user, and resume execution once the information is provided.

It also demonstrates **Legacy Support**, enabling older "tool-driven" elicitation patterns (stateless) to coexist with the new v2 "server-driven" patterns (stateful).

## Features

### 1. Server-Driven Elicitation (v2)
- **Stateful Execution**: Tools pause execution on the server side using `ctx.session.elicit_form()` or `ctx.session.elicit_url()`.
- **Protocol-Native**: Uses standard MCP `elicitation/request` and `elicitation/result` messages.
- **Tools**:
    - `create_ticket_v2`: Pauses to request ticket details (Reporter, Priority, Description) via a Pydantic schema.
    - `login_v2`: Pauses to request OAuth authentication via a URL.
    - `book_appointment_v2`: Demonstrates multi-step elicitation (Name -> Date).

### 2. Legacy Support (v1)
- **Stateless Execution**: Tools return a JSON payload with `type: elicitation`.
- **Client-Managed**: The "Client" (Assistant Backend) detects this payload and renders a form.
- **Re-Execution**: Upon submission, the tool is called *again* with the original arguments merged with the new user input.
- **Tools**:
    - `create_ticket`: Uses the legacy `fields` array for form definition.
    - `oauth_auth`: Uses the legacy URL flow.

## Architecture

The project consists of four main services orchestrated via Docker Compose:

1.  **MCP Server** (`mcp_server/`)
    -   Runs the FastMCP server.
    -   Host: `0.0.0.0:8001` (SSE).
    -   Defines all tools (v1 and v2).

2.  **Assistant Backend** (`assistant_backend/`)
    -   FastAPI application acting as the **MCP Client**.
    -   Host: `0.0.0.0:8000`.
    -   Manages connections to the MCP Server.
    -   Handles SSE streaming to the UI.
    -   Proxies elicitation requests and submissions.

3.  **Authentication Server** (`auth_server/`)
    -   Simple mock OAuth provider.
    -   Host: `0.0.0.0:8002`.
    -   Endpoints: `/auth` (Redirects to callback).

4.  **UI** (`ui/`)
    -   Streamlit application.
    -   Host: `localhost:8501`.
    -   Connects to Assistant Backend.
    -   Renders Chat interface and Dynamic Forms.

## Setup & Running

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development/testing)

### Run with Docker Compose
```bash
docker-compose up --build
```

Access the UI at [http://localhost:8501](http://localhost:8501).

### Verification Scripts
Several scripts are included to verify functionality without the UI:
- `test_server_driven.py`: Verifies v2 flow (connectivity, debug, ticket).
- `test_legacy_flow.py`: Verifies v1 legacy flow (create_ticket).
- `test_v2_login_verification.py`: Verifies v2 login validation logic.
- `test_legacy_login.py`: Verifies v1 login flow.

## Usage

### Chat Commands
Type these commands in the UI chat input:

| Command | Description | Flow Version |
| :--- | :--- | :--- |
| `ticket v2` | Triggers `create_ticket_v2`. Pauses for form input. | **v2** (Server-Driven) |
| `login v2` | Triggers `login_v2`. Pauses for URL auth. | **v2** (Server-Driven) |
| `book v2` | Triggers multi-step appointment booking. | **v2** (Server-Driven) |
| `ticket` | Triggers legacy `create_ticket`. | **v1** (Legacy) |
| `login` | Triggers legacy `oauth_auth`. | **v1** (Legacy) |
| `debug` | Triggers basic raw schema elicitation. | **v2** |

### Sidebar
The UI sidebar displays:
- Connection status.
- MCP Server URL.
- List of available tools fetched dynamically from the server.
