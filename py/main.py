from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles 
from fastapi.middleware.cors import CORSMiddleware  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
from pydantic import BaseModel
from typing import List, Optional
import json
from .database import (
    register_user, authenticate_user, create_chat,
    save_message, get_chat_history, get_user_chats
)
from .generation import generate_response, generate_stream_response

app = FastAPI(title="MewAI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------------

# --- Монтирование статических папок ---
import os
current_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Привязываем папку icons (поднимаемся из py/ на уровень выше и заходим в icons/)
icons_path = os.path.join(current_dir, "..", "icons")
if os.path.exists(icons_path):
    app.mount("/icons", StaticFiles(directory=icons_path), name="icons")

# 2. Привязываем папку html (поднимаемся из py/ на уровень выше и заходим в html/)
html_path = os.path.join(current_dir, "..", "html")
if os.path.exists(html_path):
    app.mount("/html", StaticFiles(directory=html_path), name="html")
    
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
@app.get("/", response_class=HTMLResponse)
def read_root():
    import os
    
    # 1. Находим папку, в которой лежит сам main.py (это папка py/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Поднимаемся на один уровень выше (в корень проекта) и находим index.html
    index_path = os.path.join(current_dir, "..", "index.html")
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, 
            detail=f"Файл index.html не найден по пути: {os.path.abspath(index_path)}"
        )
    
@app.post("/auth/register")
def auth_register(user: UserRegister):
    result = register_user(user.nickname, user.password, user.contact)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/auth/login")
def auth_login(user: UserLogin):
    result = authenticate_user(user.nickname, user.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid nickname or password")
    return result

@app.post("/chats")
def chat_create(chat: ChatCreate):
    result = create_chat(chat.user_id, chat.title)
    if not result:
        raise HTTPException(status_code=500, detail="Could not create chat")
    return result

@app.get("/chats/{user_id}")
def chat_list(user_id: str):
    return get_user_chats(user_id)

@app.get("/chat/history/{chat_id}")
def chat_history(chat_id: str):
    return get_chat_history(chat_id)

@app.post("/chat/generate")
def chat_generate(req: MessageRequest):
    # 1. Сохраняем сообщение пользователя в DB
    save_message(req.chat_id, "user", req.content)

    # 2. Получаем историю для ИИ
    history = get_chat_history(req.chat_id)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    if req.stream:
        def event_stream():
            full_response = ""
            for chunk in generate_stream_response(req.user_id, messages, req.mode):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Стрим завершился, токены уже обновлены внутри генератора.
            # Просто сохраняем текст ответа ассистента в историю.
            save_message(req.chat_id, "assistant", full_response)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        # Обычный короткий ответ
        result = generate_response(req.user_id, messages, req.mode)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Сохраняем ответ ассистента с посчитанными токенами
        save_message(req.chat_id, "assistant", result["content"], result["tokens"])

        return {
            "content": result["content"],
            "tokens": result["tokens"]
        }

@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    from .database import supabase  # Относительный импорт
    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/{user_id}")
def get_stats(user_id: str):
    from .database import supabase  # Относительный импорт
    try:
        res = supabase.table("profiles").select("total_tokens_used").eq("id", user_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User not found")
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
