from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json

from py.database import (
    register_user, authenticate_user, create_chat,
    save_message, get_chat_history, get_user_chats
)
from py.generation import generate_response, generate_stream_response

app = FastAPI(title="MewAI Backend")

# --- Models ---
class UserRegister(BaseModel):
    nickname: str
    password: str
    contact: str

class UserLogin(BaseModel):
    nickname: str
    password: str

class ChatCreate(BaseModel):
    user_id: str
    title: str = "New Chat"

class MessageRequest(BaseModel):
    user_id: str
    chat_id: str
    content: str
    mode: str = "fast"  # 'fast' or 'thinking'
    stream: bool = True

# --- Routes ---

@app.post("/auth/register")
async def auth_register(user: UserRegister):
    result = register_user(user.nickname, user.password, user.contact)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/auth/login")
async def auth_login(user: UserLogin):
    result = authenticate_user(user.nickname, user.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid nickname or password")
    return result

@app.post("/chats")
async def chat_create(chat: ChatCreate):
    result = create_chat(chat.user_id, chat.title)
    if not result:
        raise HTTPException(status_code=500, detail="Could not create chat")
    return result

@app.get("/chats/{user_id}")
async def chat_list(user_id: str):
    return get_user_chats(user_id)

@app.get("/chat/history/{chat_id}")
async def chat_history(chat_id: str):
    return get_chat_history(chat_id)

@app.post("/chat/generate")
async def chat_generate(req: MessageRequest):
    # 1. Save user message to DB
    save_message(req.chat_id, "user", req.content)

    # 2. Prepare messages for AI (fetch history)
    history = get_chat_history(req.chat_id)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    if req.stream:
        # Return a streaming response
        def event_stream():
            full_response = ""
            for chunk in generate_stream_response(req.user_id, messages, req.mode):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Save AI response to DB after stream finishes
            save_message(req.chat_id, "assistant", full_response)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        # Single response
        result = generate_response(req.user_id, messages, req.mode)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Save AI response to DB
        save_message(req.chat_id, "assistant", result["content"], result["tokens"])

        return {
            "content": result["content"],
            "tokens": result["tokens"]
        }

@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    try:
        # Use internal database a helper or direct query
        from py.database import supabase
        res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/{user_id}")
async def get_stats(user_id: str):
    # Return total tokens used and other metrics from the profile
    try:
        from py.database import supabase
        res = supabase.table("profiles").select("total_tokens_used").eq("id", user_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User not found")
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
