import os
import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from postgrest.exceptions import APIError
from dotenv import load_dotenv
import bcrypt
import uuid

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Using service role for backend ops

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def register_user(nickname: str, password: str, contact: str) -> Dict[str, Any]:
    """
    Registers a new user without Supabase Auth — stores directly in profiles table.
    """
    try:
        # Проверяем что никнейм не занят
        existing = supabase.table("profiles").select("id").eq("nickname", nickname).execute()
        if existing.data:
            raise Exception("Nickname already taken")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_id = str(uuid.uuid4())

        profile_data = {
            "id": user_id,
            "nickname": nickname,
            "contact_info": contact,
            "password_hash": hashed,
            "total_tokens_used": 0
        }

        supabase.table("profiles").insert(profile_data).execute()

        profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return {"user": profile.data}

    except Exception as e:
        print(f"Registration error: {e}")
        raise Exception(f"Registration failed: {str(e)}")

def authenticate_user(nickname: str, password: str) -> Optional[Dict[str, Any]]:

    try:
        profile = supabase.table("profiles").select("*").eq("nickname", nickname).single().execute()
        if not profile.data:
            return None
        hashed = profile.data.get("password_hash", "")
        if not bcrypt.checkpw(password.encode(), hashed.encode()):
            return None
        return {"user": profile.data}
    except Exception as e:
        print(f"Auth error: {e}")
    return None

def create_chat(user_id: str, name: str = "New Chat") -> Dict[str, Any]:
    """
    Creates a new chat session for a user.
    """
    data = {
        "user_id": user_id,
        "title": name
    }
    response = supabase.table("chats").insert(data).execute()
    return response.data[0] if response.data else {}

def get_user_chats(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all chat sessions for a specific user.
    """
    try:
        response = supabase.table("chats").select("*").eq("user_id", user_id).order("created_at", descending=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching user chats: {e}")
        return []
    
def save_message(chat_id: str, role: str, content: str, tokens: int = 0) -> Dict[str, Any]:
    """
    Saves a message to a chat and tracks token usage.
    """
    data = {
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "tokens": tokens
    }
    response = supabase.table("messages").insert(data).execute()
    return response.data[0] if response.data else {}

def get_chat_history(chat_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves the history of messages for a specific chat.
    """
    response = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
    return response.data

def update_user_tokens(user_id: str, tokens_added: int):
    """
    Increments the total tokens used by a user.
    """
    profile = supabase.table("profiles").select("total_tokens_used").eq("id", user_id).single().execute()
    current_tokens = profile.data.get("total_tokens_used", 0) if profile.data else 0

    supabase.table("profiles").update({"total_tokens_used": current_tokens + tokens_added}).eq("id", user_id).execute()

def update_token_usage(token_id: str, tokens_added: int):
    """
    Increments the token usage for a specific API key.
    """
    key_data = supabase.table("api_keys_usage").select("tokens_used").eq("token_id", token_id).single().execute()
    current_usage = key_data.data.get("tokens_used", 0) if key_data.data else 0

    supabase.table("api_keys_usage").update({"tokens_used": current_usage + tokens_added}).eq("token_id", token_id).execute()

def get_available_api_key() -> Optional[str]:
    """
    Implements the rotating logic for 25 API keys.
    1. Loads tokens from .env.
    2. Checks for keys that need a reset (older than 7 days).
    3. Selects the key with the lowest usage under the 1M limit.
    """

    # Load tokens from .env
    tokens = {}
    for i in range(1, 26):
        key_name = f"TOKEN_{i}"
        val = os.environ.get(key_name)
        if val:
            tokens[f"token_{i}"] = val

    if not tokens:
        print("No tokens found in .env")
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    seven_days_ago = now - datetime.timedelta(days=7)

    # 1. Find keys that need resetting in DB
    keys_to_reset = supabase.table("api_keys_usage").select("token_id").lt("last_reset_at", seven_days_ago.isoformat()).execute()

    for key in keys_to_reset.data:
        supabase.table("api_keys_usage").update({
            "tokens_used": 0,
            "last_reset_at": now.isoformat()
        }).eq("token_id", key["token_id"]).execute()

    # 2. Get usage stats for all tokens in our .env list
    token_ids = list(tokens.keys())
    response = supabase.table("api_keys_usage").select("token_id, tokens_used").in_("token_id", token_ids).execute()

    usage_map = {row['token_id']: row['tokens_used'] for row in response.data}

    # Find the best token (lowest usage, under 1M)
    best_token_id = None
    min_usage = float('inf')

    for tid in token_ids:
        usage = usage_map.get(tid, 0)
        if usage < 1000000 and usage < min_usage:
            min_usage = usage
            best_token_id = tid

    if best_token_id:
        return tokens[best_token_id]

    # Fallback to first token if all are over limit
    return list(tokens.values())[0] if tokens else None
