from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from langgraph.graph import MessagesState
from typing import List
import logging
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from prompts import (
    MEMORY_SYSTEM_PROMPT, 
    INITIAL_SYSTEM_PROMPT, 
    SUMMARY_WITH_EXISTING, 
    INITIAL_SUMMARY_PROMPT,
    TITLE_GENERATION_PROMPT
)


load_dotenv()


class AssistantState(MessagesState):
    summary: str
    full_history: List = []
    title: str = ""


class Assistant:
    def __init__(self, llm, thread_id=None, memoryLenght=10 ):
        self.conn = sqlite3.connect("checkpoints.sqlite",check_same_thread=False)
        self.memory = SqliteSaver(self.conn)
        self.llm = llm 
        self.thread_id = thread_id 
        self.memoryLenght = memoryLenght
        self.graph = self._init_graph()
        self.config = {
            "configurable": {"thread_id": self.thread_id}
        }
      

    def _init_graph(self):
        builder = StateGraph(AssistantState)
        
        builder.add_node("chat", self._chat)
        builder.add_node("summarize_conversation", self._summarize_conversation)

        builder.add_edge(START, "chat")
        builder.add_conditional_edges("chat", self._should_summarize)
        builder.add_edge("summarize_conversation", END)

        self.graph = builder.compile(
            checkpointer=self.memory,
        )
        with open("graph.png", "wb") as f:
            f.write(self.graph.get_graph().draw_mermaid_png())
        return self.graph

    def _chat(self, state: AssistantState):
        summary = state.get("summary", "")
        if summary:
            system_prompt = MEMORY_SYSTEM_PROMPT.format(summary=summary)
            messages = [SystemMessage(content=system_prompt)] + state["messages"]
        else:
            messages = [SystemMessage(content=INITIAL_SYSTEM_PROMPT)] + state["messages"]

        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def _summarize_conversation(self, state: AssistantState):
        summary = state.get("summary", "")
        
        # Store the full conversation history before removing messages
        full_history = state.get("full_history", [])
        # Add current messages to full history (excluding the last 2 we'll keep)
        full_history.extend([m for m in state["messages"][:-2]])
        
        if summary:
            summary_prompt = SUMMARY_WITH_EXISTING.format(summary=summary)
        else:
            summary_prompt = INITIAL_SUMMARY_PROMPT

        messages = state["messages"] + [HumanMessage(content=summary_prompt)]
        response = self.llm.invoke(messages)

        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        
        return {
            "summary": f"{summary}\n{response.content}".strip(), 
            "messages": delete_messages,
            "full_history": full_history
        }

    # conditional edge that sends to summary only of more than 6 messages
    def _should_summarize(self, state: AssistantState):
        """
        Check if we should summarize the conversation.
        """
        messages = state["messages"]
        if len(messages) > self.memoryLenght:
            return "summarize_conversation"
        return END

    def generate_title(self, message_content):
        """Generate a short title based on the first message"""
        title_prompt = TITLE_GENERATION_PROMPT.format(message_content=message_content)
        
        # Create a simple message list for the title generation
        messages = [HumanMessage(content=title_prompt)]
        
        # Get title from LLM
        response = self.llm.invoke(messages)
        
        # Clean up the title (remove quotes, newlines, etc.)
        title = response.content.strip().strip('"\'').strip()
        
        # Limit length
        if len(title) > 40:
            title = title[:37] + "..."
        
        return title

    def get_response(self, user_input):
        """Generate streaming response for user input"""
        try:
            input_message = HumanMessage(content=user_input)
            
            # Check if this is the first message (no title yet)
            config = {"configurable": {"thread_id": self.thread_id}}
            checkpoints = list(self.graph.get_state_history(config))
            
            # Generate title if this is the first message
            if not checkpoints or (checkpoints and not checkpoints[0].values.get("title")):
                # Generate a title
                title = self.generate_title(user_input)
                
                # The response will include the title in the state
                response = self.graph.invoke(
                    {"messages": [input_message], "title": title}, 
                    config=self.config
                )
            else:
                # Normal response without changing title
                response = self.graph.invoke(
                    {"messages": [input_message]}, 
                    config=self.config
                )
            
            ai_response = response["messages"][-1].content

            def response_generator():
                yield ai_response
            
            return response_generator()
            
        except Exception as e:
            logging.error(f"Response generation failed: {str(e)}")
            raise

