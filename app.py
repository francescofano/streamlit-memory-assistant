#streamlit torch bug fix
import streamlit as st
from gui import AssistantGUI
from assistant import Assistant
from dotenv import load_dotenv
import logging
from langchain_openai import ChatOpenAI
import uuid
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3


def main():
    st.set_page_config(page_title="Assistant", page_icon=":shark:", layout="wide")
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Initialize checkpoint connection (Moved here and shared)
    conn = sqlite3.connect("checkpoints.sqlite")
    saver = SqliteSaver(conn)

    # Initialize LLM once
    if "llm" not in st.session_state:
        st.session_state.llm = ChatOpenAI(model="gpt-4")

    # Get or create assistant using checkpoints
    if "assistant" not in st.session_state:
        
        # First check if there are any checkpoints in the database
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM checkpoints")
            count = cur.fetchone()[0]
            
            if count > 0:
                # Get the most recent checkpoint
                cur.execute("SELECT thread_id FROM checkpoints ORDER BY ROWID DESC LIMIT 1")
                thread_id = cur.fetchone()[0]
                
                st.session_state.assistant = Assistant(
                    llm=st.session_state.llm,
                    thread_id=thread_id
                )
                
                # Store current session in session state
                st.session_state.current_session = {
                    "id": thread_id,
                }
            else:
                # Create new session with proper thread_id linkage
                thread_id = str(uuid.uuid4())
                st.session_state.assistant = Assistant(
                    llm=st.session_state.llm,
                    thread_id=thread_id
                )
                
                # Store current session in session state
                st.session_state.current_session = {
                    "id": thread_id,
                }
        except sqlite3.OperationalError as e:
            # Handle case where table doesn't exist yet
            thread_id = str(uuid.uuid4())
            st.session_state.assistant = Assistant(
                llm=st.session_state.llm,
                thread_id=thread_id
            )
            
            # Store current session in session state
            st.session_state.current_session = {
                "id": thread_id,
            }

    gui = AssistantGUI(st.session_state.assistant, conn)  # Pass connection
    gui.render()

   

if __name__ == "__main__":
    main()
