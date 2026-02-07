import streamlit as st
import requests
import uuid
import os
import json

# Configuration
ASSISTANT_API_URL = os.getenv("ASSISTANT_API_URL", "http://localhost:8000")
API_URL = ASSISTANT_API_URL # Alias

st.set_page_config(page_title="AI Assistant v2", page_icon="🤖")
st.title("AI Assistant - Server Driven Elicitation")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "elicitation_active" not in st.session_state:
    st.session_state.elicitation_active = False
if "elicitation_data" not in st.session_state:
    st.session_state.elicitation_data = None

# Sidebar
with st.sidebar:
    st.header("MCP Server Info")
    st.write(f"**Backend API:** `{API_URL}`")
    
    if st.button("Refresh Tools"):
        st.session_state.pop("tools_info", None)
        
    if "tools_info" not in st.session_state:
        try:
            with st.spinner("Fetching tools..."):
                resp = requests.get(f"{API_URL}/tools")
                if resp.status_code == 200:
                    st.session_state.tools_info = resp.json()
                else:
                    st.error(f"Failed to fetch tools: {resp.status_code}")
        except Exception as e:
            st.error(f"Connection error: {e}")
            
    if "tools_info" in st.session_state:
        info = st.session_state.tools_info
        st.write(f"**MCP Server:** `{info.get('server_url', 'Unknown')}`")
        
        st.subheader("Available Tools")
        tools = info.get("tools", [])
        for tool in tools:
            with st.expander(tool.get("name")):
                st.write(tool.get("description"))
    else:
        st.warning("Tools not loaded.")

# Styles
st.markdown("""
<style>
.stChatMessage {
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

def handle_stream(response):
    """
    Consumes the stream from Backend.
    Updates chat history with 'message' or 'result'.
    If 'elicitation', sets session state and returns, stopping the stream consumption.
    """
    full_response = ""
    message_placeholder = st.empty()
    
    # Iterate over lines
    for line in response.iter_lines():
        if line:
            try:
                # Backend sends NDJSON
                event = json.loads(line)
                type = event.get("type")
                content = event.get("content")
                
                if type == "result" or type == "message":
                    full_response = str(content)
                    message_placeholder.markdown(full_response)
                    
                elif type == "error":
                    st.error(f"Error: {content}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {content}"})
                    return

                elif type == "elicitation":
                    # CRITICAL: We received an elicitation request.
                    st.session_state.elicitation_active = True
                    st.session_state.elicitation_data = event["content"] # {elicitation_type, data}
                    
                    # We do NOT append the partial response to history yet?
                    # Or we do.
                    # message_placeholder.empty() # Clear the "Thinking..." or partial?
                    # Actually, we should probably keep the context?
                    
                    st.rerun() # Force rerun to render form
                    return

            except json.JSONDecodeError:
                pass
    
    # Stream finished (Result)
    if full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Elicitation Form Rendering
if st.session_state.get("elicitation_active"):
    data = st.session_state.elicitation_data
    elicitation_type = data.get("elicitation_type")
    payload = data.get("data", {})
    
    with st.container(border=True):
        st.info("Input Required")
        
        if elicitation_type == "url":
            message = payload.get("message", "Please authenticate")
            url = payload.get("url")
            st.write(message)
            st.link_button("Authenticate", url)
            
            if st.button("I have completed the action"):
                 with st.spinner("Resuming..."):
                    try:
                        submission = {
                            "session_id": st.session_state.session_id, 
                            "response_data": {}
                        }
                        
                        is_v1 = payload.get("is_v1", False)
                        tool_name = payload.get("tool_name", "")

                        if is_v1:
                            submission["is_v1"] = True
                            submission["tool_name"] = tool_name
                            context_data = payload.get("context_data", {})
                            submission["response_data"].update(context_data)

                        response = requests.post(
                            f"{API_URL}/submit_elicitation",
                            json=submission,
                            stream=True
                        )
                        st.session_state.elicitation_active = False
                        st.session_state.elicitation_data = None
                        handle_stream(response) # Resume stream!
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        else: # Form
            message = payload.get("message", "Please details")
            # v2 uses requestedSchema, v1 uses fields
            schema = payload.get("requestedSchema", {})
            fields = payload.get("fields", [])
            is_v1 = payload.get("is_v1", False)
            tool_name = payload.get("tool_name", "")

            st.write(message)
            
            with st.form("elicitation_form"):
                responses = {}
                
                if schema:
                    # v2 Schema
                    props = schema.get("properties", {})
                    for key, info in props.items():
                        title = info.get("title", key)
                        responses[key] = st.text_input(title)
                elif fields:
                    # v1 Fields
                    for field in fields:
                        name = field.get("name")
                        desc = field.get("description", name)
                        responses[name] = st.text_input(desc)
                    
                if st.form_submit_button("Submit"):
                     with st.spinner("Submitting..."):
                        try:
                            # Submission payload
                            submission = {
                                "session_id": st.session_state.session_id, 
                                "response_data": responses
                            }
                            # Add v1 specific flags if needed by backend
                            if is_v1:
                                submission["is_v1"] = True
                                submission["tool_name"] = tool_name
                                # Merge context_data (critical for v1 tools like create_ticket)
                                context_data = payload.get("context_data", {})
                                submission["response_data"].update(context_data)

                            response = requests.post(
                                f"{API_URL}/submit_elicitation",
                                json=submission,
                                stream=True
                            )
                            st.session_state.elicitation_active = False
                            st.session_state.elicitation_data = None
                            handle_stream(response) # Resume stream!
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

else:
    # Standard Chat Input
    if prompt := st.chat_input("Start a workflow... (e.g., 'book v2', 'login v2')"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(
                        f"{API_URL}/chat",
                        json={"message": prompt, "user_id": "user1", "session_id": st.session_state.session_id},
                        stream=True
                    )
                    handle_stream(response)
                except Exception as e:
                    st.error(f"Connection Error: {e}")
