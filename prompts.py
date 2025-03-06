# System prompts for the assistant
MEMORY_SYSTEM_PROMPT = """You are an helpful assistant with memory.
Here is the summary of the conversation earlier: {summary}. 
Continue the conversation from the last message."""

INITIAL_SYSTEM_PROMPT = """You are an helpful assistant."""

# Summarization prompts
SUMMARY_WITH_EXISTING = """
This is a summary of the conversation up to this point: {summary}.\n\n
Create a NEW comprehensive summary that INCORPORATES BOTH the existing summary 
and the latest messages. PRESERVE ALL IMPORTANT DETAILS from the existing summary 
while adding new information from the recent messages.
"""

INITIAL_SUMMARY_PROMPT = """Create a comprehensive summary of the conversation up to this point. Include all key details and facts about the user."""

# Title generation prompt
TITLE_GENERATION_PROMPT = """
Based on this first message from a user, create a very short title that captures the essence of what they're asking about:

Message: {message_content}

Title:
"""
