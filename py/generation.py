import os
import datetime
from typing import List, Dict, Any, Optional
from ollama import Client
from py.database import get_available_api_key, update_token_usage, update_user_tokens

# Configuration
DEFAULT_MODEL = 'gemma4:31b-cloud'

def generate_response(user_id: str, messages: List[Dict[str, str]], mode: str = 'fast') -> Dict[str, Any]:
    """
    Generates an AI response based on user messages and a selected mode.

    Args:
        user_id: ID of the user requesting generation.
        messages: List of messages in the conversation.
        mode: 'fast' or 'thinking'.

    Returns:
        A dictionary containing the response content and token usage.
    """
    # 1. Get the best available API token from our rotated list
    api_token = get_available_api_key()
    if not api_token:
        return {"error": "No available API tokens at the moment. Please try again later."}

    # 2. Determine the token identifier for usage tracking
    # Since get_available_api_key returns the value, we need a way to map it back
    # or just find which TOKEN_X it corresponds to in .env.
    token_id = None
    for i in range(1, 26):
        if os.environ.get(f"TOKEN_{i}") == api_token:
            token_id = f"token_{i}"
            break

    # 3. Adjust prompt based on mode
    # "Fast" is concise, "Thinking" is deep and detailed
    system_prompt = "You are MewAI, a helpful and intelligent AI assistant."
    if mode == 'thinking':
        system_prompt += " Please provide a very detailed, step-by-step analysis. Think deeply and explain your reasoning before giving the final answer."
    elif mode == 'fast':
        system_prompt += " Please be concise and provide the most direct answer possible."

    # Add system prompt to messages
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        # Initialize Ollama Client with the rotated token
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': f'Bearer {api_token}'}
        )

        # Generate response (non-streaming for the backend API logic,
        # though we can support streaming in the main app)
        response = client.chat(
            model=DEFAULT_MODEL,
            messages=full_messages,
            stream=False
        )

        content = response['message']['content']

        # Estimate tokens (very rough estimation: 1 token ~ 4 characters for English)
        # In a production environment, use a proper tokenizer like tiktoken.
        tokens_used = len(content) // 4 if content else 0
        # Add a small amount for the prompt
        prompt_tokens = sum(len(m['content']) // 4 for m in full_messages)
        total_tokens = tokens_used + prompt_tokens

        # 4. Update token usage in Database
        if token_id:
            update_token_usage(token_id, total_tokens)

        update_user_tokens(user_id, total_tokens)

        return {
            "content": content,
            "tokens": total_tokens,
            "token_used": token_id
        }

    except Exception as e:
        print(f"Generation error: {e}")
        return {"error": f"AI generation failed: {str(e)}"}

def generate_stream_response(user_id: str, messages: List[Dict[str, str]], mode: str = 'fast'):
    """
    Generator for streaming responses.
    """
    api_token = get_available_api_key()
    if not api_token:
        yield "Error: No available API tokens."
        return

    token_id = None
    for i in range(1, 26):
        if os.environ.get(f"TOKEN_{i}") == api_token:
            token_id = f"token_{i}"
            break

    system_prompt = "You are MewAI, a helpful and intelligent AI assistant."
    if mode == 'thinking':
        system_prompt += " Please provide a very detailed, step-by-step analysis. Think deeply and explain your reasoning before giving the final answer."
    elif mode == 'fast':
        system_prompt += " Please be concise and provide the most direct answer possible."

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': f'Bearer {api_token}'}
        )

        total_content = ""
        for part in client.chat(model=DEFAULT_MODEL, messages=full_messages, stream=True):
            chunk = part['message']['content']
            total_content += chunk
            yield chunk

        # Update usage after stream finishes
        tokens_used = len(total_content) // 4
        prompt_tokens = sum(len(m['content']) // 4 for m in full_messages)
        total_tokens = tokens_used + prompt_tokens

        if token_id:
            update_token_usage(token_id, total_tokens)
        update_user_tokens(user_id, total_tokens)

    except Exception as e:
        print(f"Streaming error: {e}")
        yield f"Error: {str(e)}"
