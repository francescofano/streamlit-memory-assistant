import streamlit as st
import logging
from assistant import Assistant
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import uuid

class AssistantGUI:
    def __init__(self, assistant, conn):
        self.assistant = assistant
        self.conn = conn
        self.saver = SqliteSaver(self.conn)
        self._update_state_from_assistant()

    def _update_state_from_assistant(self):
        """Sync session state with assistant's current state"""
        st.session_state.current_session = {
            "id": self.assistant.thread_id,
        }

    def _get_session_messages(self, thread_id: str) -> list:
        """Retrieve full message history from checkpoints"""
        
        # Use the LangGraph API to get checkpoint history
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            # Get the state history for this thread
            checkpoints = list(self.assistant.graph.get_state_history(config))
            
            
            if not checkpoints:
                return []
            
            # The latest checkpoint should have all messages
            latest_checkpoint = checkpoints[0]  # First one is the most recent
            
            # Combine full_history with current messages
            result = []
            
            # First add the full history if it exists
            if "full_history" in latest_checkpoint.values:
                full_history = latest_checkpoint.values["full_history"]
                result.extend(full_history)
            
            # Then add current messages
            if "messages" in latest_checkpoint.values:
                messages = latest_checkpoint.values["messages"]
                result.extend(messages)
                
            return result
            
        except Exception as e:
            print(f"ERROR: Failed to retrieve checkpoint data: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def render_sidebar(self):
        with st.sidebar:
            # Fixed header section
            fixed_header = st.container()
            with fixed_header:
                st.header("Chat Sessions")
                
                # Create New Chat button - full width
                if st.button("New Chat", key="new_chat", use_container_width=True):
                    # Generate a new thread ID
                    new_thread_id = str(uuid.uuid4())
                    
                    # Create a new assistant with this thread ID
                    st.session_state.assistant = Assistant(
                        llm=st.session_state.llm,
                        thread_id=new_thread_id
                    )
                    
                    # Update GUI state
                    self.assistant = st.session_state.assistant
                    self._update_state_from_assistant()
                    
                    # Store current session in session state
                    st.session_state.current_session = {
                        "id": new_thread_id,
                    }
                    
                    # Force a rerun to refresh the UI
                    st.rerun()
                
                st.divider()
            
            # Get all unique thread IDs from the database
            try:
                cur = self.conn.cursor()
                
                # Check if the checkpoints table exists
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
                table_exists = cur.fetchone()
                
                if not table_exists:
                    # Table doesn't exist, display info message and return
                    st.info("No previous chats found")
                    return
                
                # Get thread_id and order by most recent
                cur.execute("SELECT thread_id, MAX(ROWID) FROM checkpoints GROUP BY thread_id ORDER BY MAX(ROWID) DESC")
                thread_data = cur.fetchall()
                
                # Current thread ID
                current_thread_id = self.assistant.thread_id
                
                # Create a list of all thread IDs to display
                all_thread_ids = []
                
                # Add current thread ID first if it's not in the database yet
                if current_thread_id not in [t[0] for t in thread_data]:
                    all_thread_ids.append((current_thread_id, None))
                
                # Add all thread IDs from the database
                all_thread_ids.extend(thread_data)
                
                if not all_thread_ids:
                    st.info("No previous chats found")
                else:
                    # Display all chats in a clean list
                    for thread_id, _ in all_thread_ids:
                  
                        
                        # Default preview
                        preview = "New chat"
                        
                        # For threads in the database, get title from state
                        if thread_id in [t[0] for t in thread_data]:
                            # Get the state for this thread
                            config = {"configurable": {"thread_id": thread_id}}
                            try:
                                checkpoints = list(self.assistant.graph.get_state_history(config))
                                if checkpoints:
                                    # Try to get the title from state
                                    if "title" in checkpoints[0].values and checkpoints[0].values["title"]:
                                        preview = checkpoints[0].values["title"]
                                    else:
                                        # Fallback to first message preview
                                        messages = []
                                        if "messages" in checkpoints[0].values:
                                            messages = checkpoints[0].values["messages"]
                                        elif "full_history" in checkpoints[0].values:
                                            messages = checkpoints[0].values["full_history"]
                                        
                                        # Find first human message for preview
                                        for msg in messages:
                                            if isinstance(msg, HumanMessage):
                                                preview = msg.content[:40] + "..." if len(msg.content) > 40 else msg.content
                                                break
                            except Exception as e:
                                print(f"Error loading chat preview: {str(e)}")
                        
                        # Create a row with chat button and delete button
                        col1, col2 = st.columns([5, 1])
                        
                        # Chat button in first column
                        with col1:
                            if st.button(f"{preview}", 
                                        key=f"chat_{thread_id}", 
                                        use_container_width=True):
                                # Switch to this thread
                                st.session_state.assistant = Assistant(
                                    llm=st.session_state.llm,
                                    thread_id=thread_id
                                )
                                
                                # Update GUI state
                                self.assistant = st.session_state.assistant
                                self._update_state_from_assistant()
                                
                                # Force a rerun to refresh the UI
                                st.rerun()
                        
                        # Delete button in second column
                        with col2:
                            if st.button("🗑️", key=f"delete_{thread_id}"):
                                # Delete this thread from the database
                                try:
                                    # Delete all checkpoints for this thread
                                    cur.execute("DELETE FROM checkpoints WHERE thread_id=?", (thread_id,))
                                    self.conn.commit()
                                    
                                    # If we deleted the current thread, create a new one
                                    if thread_id == current_thread_id:
                                        # Generate a new thread ID
                                        new_thread_id = str(uuid.uuid4())
                                        
                                        # Create a new assistant with this thread ID
                                        st.session_state.assistant = Assistant(
                                            llm=st.session_state.llm,
                                            thread_id=new_thread_id
                                        )
                                        
                                        # Update GUI state
                                        self.assistant = st.session_state.assistant
                                        self._update_state_from_assistant()
                                    
                                    # Force a rerun to refresh the UI
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting chat: {str(e)}")
                                    print(f"ERROR deleting chat: {str(e)}")
                        
                   
            except Exception as e:
                # Handle the error gracefully
                st.info("No previous chats found")

    def handle_user_input(self):
        user_input = st.chat_input("Type here...", key="input")
        if user_input and user_input.strip() != "":
            # Display user message immediately
            with st.chat_message("human"):
                st.markdown(user_input)
            
            try:
                # Get response through LangGraph's checkpoint system
                response_generator = self.get_response(user_input)
                
                # Display AI response
                with st.chat_message("ai"):
                    response_container = st.empty()
                    full_response = ""
                    for chunk in response_generator:
                        content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        full_response += content
                        response_container.markdown(full_response + "▌")
                    response_container.markdown(full_response)
                
                # Check if this was the first message (title might have been generated)
                config = {"configurable": {"thread_id": self.assistant.thread_id}}
                checkpoints = list(self.assistant.graph.get_state_history(config))
                
                # If we have a title now, force a rerun to update the sidebar
                if checkpoints and checkpoints[0].values.get("title"):
                    st.rerun()

            except Exception as e:
                st.error(f"Error generating response: {str(e)}")
                logging.exception("Response generation failed")

    def get_response(self, user_input):
        return self.assistant.get_response(user_input)
    
    def set_state(self, key, value):
        st.session_state[key] = value

    def display_messages(self):
        """Display all messages from checkpoint history"""
        messages = self._get_session_messages(self.assistant.thread_id)
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                with st.chat_message("human"):
                    st.markdown(msg.content)
            elif isinstance(msg, AIMessage):
                with st.chat_message("ai"):
                    st.markdown(msg.content)
            elif isinstance(msg, SystemMessage):  # Handle system message display
                with st.chat_message("ai"):
                    st.markdown(msg.content)

    def render(self):
        self.render_sidebar()
        self.display_messages()
        self.handle_user_input()
      
