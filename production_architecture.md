# Production Architecture Recommendation (FastAPI + React)

## Executive Summary

For a **React + FastAPI** production environment, we recommend a **WebSocket-first architecture**.

This approach provides the best user experience for an AI assistant that requires real-time interaction (typing indicators, tool execution updates, interruptions) and server-driven elicitation (forms, auth flows).

### Why WebSockets?
| Feature | REST (Current) | WebSocket (Recommended) |
| :--- | :--- | :--- |
| **Real-time Typing** | Requires complex SSE/Streaming | Native |
| **Server-Initiated Elicitation** | Requires Polling or Hanging GET | Server Pushes Event |
| **Latency** | Medium (New TCP handshake per request) | Low (Persistent Connection) |
| **State Management** | Hard (Must ensure sticky sessions or distributed DB) | Easier (Connection holds context during session) |

## Proposed Architecture

### 1. Connection Lifecycle
1.  **React App** loads and generates a `session_id`.
2.  **React App** connects to `ws://api.domain.com/ws/{session_id}`.
3.  **FastAPI** accepts connection and spawns a `SessionManager` for that socket.
4.  Standard HTTP is used *only* for initial auth (Login) or large file uploads.

### 2. Protocol Design (JSON Events)

Communication happens via strictly typed JSON events.

**Client -> Server:**
```json
{ "type": "chat.message", "content": "Book a meeting", "id": "msg_123" }
{ "type": "elicitation.submit", "content": { "slot": "2pm" }, "reply_to": "evt_456" }
{ "type": "signal.stop", "content": {} }
```

**Server -> Client:**
```json
{ "type": "chat.token", "content": "Sure", "ref_id": "msg_123" }
{ "type": "tool.start", "content": { "tool": "calendar_api" } }
{ "type": "elicitation.start", "content": { "schema": {...}, "mode": "form" } }
{ "type": "chat.done", "content": { "final_text": "..." } }
```

## Backend Changes (FastAPI)

#### [MODIFY] [mcp_client_gen.py](file:///c:/Users/dipan/Documents/Projects/work_projects/new_elicitation/assistant_backend/mcp_client_gen.py)
*   Refactor `MCPClientManager` to support WebSocket handlers instead of just HTTP Streaming.
*   Add `WebSocketConnectionManager` to handle active sockets.
*   Implement `broadcast(session_id, message)` logic.

#### [NEW] [socket_manager.py](file:///c:/Users/dipan/Documents/Projects/work_projects/new_elicitation/assistant_backend/socket_manager.py)
*   Class to handle `FastAPI.WebSocket` connections.
*   Methods: `connect`, `disconnect`, `send_personal_message`.

#### [MODIFY] [main.py](file:///c:/Users/dipan/Documents/Projects/work_projects/new_elicitation/assistant_backend/main.py)
*   Add `@app.websocket("/ws/{session_id}")` endpoint.
*   Remove complex StreamingResponse logic in favor of `await websocket.send_json()`.

## Frontend Changes (React)

*(Conceptual - Code not in this repo)*

1.  **Custom Hook**: `useAssistantSocket(url)`
    *   Handles auto-reconnect.
    *   Exposes `sendMessage(text)` and `submitElicitation(data)`.
    *   Maintains `messages` state array.
2.  **Component**: `AgentInteractions`
    *   Renders chat bubbles.
    *   **Crucial**: Listens for `elicitation.start` to render a Form/Modal *inline* in the chat or as an overlay.

## Scaling (Redis) needed?
*   **Single Replica**: No Redis needed. Memory is fine.
*   **Multiple Replicas**: Yes.
    *   If User A is connected to Server 1 via WS.
    *   And an external webhook hits Server 2.
    *   Server 2 must publish to Redis Pub/Sub: `PUBLISH session_123 "{...}"`.
    *   Server 1 (subscribed to `session_123`) receives message and pushes to WS.
