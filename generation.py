import os
import re
import time
import base64
import requests
import itertools
from ollama import Client
from dotenv import load_dotenv

load_dotenv()

# ── API ключи (round-robin) ──────────────────────────────────
_raw_keys  = [os.getenv(f"OLLAMA_API_KEY_{i}") for i in range(1, 11)]
API_KEYS   = [k for k in _raw_keys if k]
_key_cycle = itertools.cycle(API_KEYS) if API_KEYS else None

def _next_key() -> str:
    if not _key_cycle:
        raise RuntimeError("No OLLAMA_API_KEY_* keys found in .env")
    return next(_key_cycle)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are MewAI — a chill AI companion living inside Telegram.

PERSONALITY:
- Friendly, witty, a little playful. Like texting a smart friend.
- Use kaomoji naturally: (◕‿◕) (￣ω￣) (ᵔᴥᵔ) ヽ(・∀・)ﾉ (¬‿¬) ٩(˘◡˘۶) — pick ones that fit the mood, don't overdo it.
- Match the user's vibe — casual when they're casual, focused when they need help.
- Slightly opinionated. It's okay to say "honestly, X is better".

RESPONSE STYLE:
- Keep it SHORT. One idea = one short paragraph. No walls of text.
- Only go long when it's genuinely needed (code, step-by-step explanations).
- No filler: no "Great question!", "Of course!", "Certainly!", "As an AI...".
- Don't greet unless they greeted you first.
- Don't repeat what the user just said.

FORMATTING (Telegram MarkdownV2):
- *bold* for key terms only — not decoration.
- `inline code` for variables, commands, short snippets.
- ```language blocks``` for any code longer than one line.
- Bullet points only for actual lists — not every response.
- Never use headers (#) — this is a chat, not a document.

WHAT YOU CAN DO:
- Chat on any topic: tech, life, ideas, opinions.
- Help with code: write, review, debug.
- Analyze images the user sends.
- Give honest, concise answers without padding.

WHAT YOU DON'T DO:
- Mention Purrs, tokens, or the economy unless the user asks.
- Pretend to have deep feelings or be overly enthusiastic.
- Write an essay when a sentence will do."""


# ============================================================
# MARKDOWN → MARKDOWNV2
# ============================================================

def md_to_v2(text: str) -> str:
    """Конвертирует обычный Markdown в Telegram MarkdownV2."""
    ESCAPE  = r'_[]()~>#+=|{}.!-'
    pattern = re.compile(r'(```[\s\S]*?```|`[^`]+`)', re.MULTILINE)
    parts   = pattern.split(text)
    result  = []

    for part in parts:
        # Код-блоки не трогаем
        if part.startswith('```') or (part.startswith('`') and part.endswith('`')):
            result.append(part)
            continue

        out = ""
        i   = 0
        while i < len(part):
            # **bold** → *bold*
            if part[i:i+2] == '**':
                end = part.find('**', i + 2)
                if end != -1:
                    inner = ''.join(f'\\{c}' if c in ESCAPE else c for c in part[i+2:end])
                    out  += f'*{inner}*'
                    i     = end + 2
                    continue
            # *italic* → _italic_
            if part[i] == '*' and part[i+1:i+2] != '*' and (i == 0 or part[i-1] != '*'):
                end = part.find('*', i + 1)
                if end != -1 and part[end-1:end] != '*':
                    inner = ''.join(f'\\{c}' if c in ESCAPE else c for c in part[i+1:end])
                    out  += f'_{inner}_'
                    i     = end + 1
                    continue
            c    = part[i]
            out += f'\\{c}' if c in ESCAPE else c
            i   += 1

        result.append(out)

    return ''.join(result)


def split_smart(text: str, max_len: int) -> list[str]:
    """Режет текст на части по границам строк."""
    chunks = []
    while len(text) > max_len:
        cut = text.rfind('\n', 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip('\n')
    if text:
        chunks.append(text)
    return chunks


# ============================================================
# ФОТО → BASE64
# ============================================================

def get_image_base64(bot, token: str, file_id: str) -> str | None:
    """Скачивает фото из Telegram и возвращает base64."""
    try:
        file_info = bot.get_file(file_id)
        url       = f"https://api.telegram.org/file/bot{token}/{file_info.file_path}"
        response  = requests.get(url, timeout=15)
        return base64.b64encode(response.content).decode("utf-8")
    except Exception as e:
        print(f"❌ Image download failed: {e}")
        return None


# ============================================================
# ГЕНЕРАЦИЯ + СТРИМИНГ
# ============================================================

def generate_and_stream(bot, chat_id: int, msg_id: int, messages: list) -> str | None:
    """
    Генерирует ответ с эффектом стриминга — редактирует сообщение по ходу.
    Пробует все API ключи по очереди.
    Возвращает полный raw-текст или None при ошибке.
    """
    STREAM_INTERVAL = 1.2   # секунд между обновлениями
    MAX_STREAM_LEN  = 3800  # лимит для промежуточных сообщений

    for attempt in range(len(API_KEYS)):
        api_key = _next_key()
        try:
            client = Client(
                host="https://ollama.com",
                headers={"Authorization": f"Bearer {api_key}"}
            )

            full_response  = ""
            last_update_at = time.time()

            for part in client.chat(
                "gemma4:31b-cloud",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                stream=True
            ):
                chunk = part["message"]["content"]
                if not chunk:
                    continue

                full_response += chunk

                # Обновляем сообщение по таймеру
                now = time.time()
                if now - last_update_at >= STREAM_INTERVAL:
                    display = full_response
                    if len(display) > MAX_STREAM_LEN:
                        display = "…" + display[-MAX_STREAM_LEN:]
                    try:
                        bot.edit_message_text(display + " █", chat_id, msg_id)
                    except Exception:
                        pass
                    last_update_at = now

            if full_response.strip():
                return full_response

        except Exception as e:
            print(f"⚠️ Key #{attempt + 1} failed: {e}")
            continue

    return None


# ============================================================
# ФИНАЛЬНАЯ ОТПРАВКА
# ============================================================

async def send_ai_response(bot, chat_id: int, msg_id: int, text: str, cost: int):
    """
    Заменяет стриминговое сообщение на финальный отформатированный ответ.
    Пробует MarkdownV2 → при ошибке plain text.
    Длинные ответы разбивает на части.
    """
    MAX_LEN     = 4000
    cost_suffix = f"\n\n💰 \\-{cost} Purrs"
    converted   = md_to_v2(text.strip())

    if len(converted) <= MAX_LEN:
        try:
            await bot.edit_message_text(
                converted + cost_suffix, chat_id, msg_id, parse_mode="MarkdownV2"
            )
        except Exception:
            await bot.edit_message_text(
                text.strip() + f"\n\n💰 -{cost} Purrs", chat_id, msg_id
            )
        return

    # Длинный ответ — режем на части
    parts = split_smart(converted, MAX_LEN)

    try:
        await bot.edit_message_text(parts[0], chat_id, msg_id, parse_mode="MarkdownV2")
    except Exception:
        await bot.edit_message_text(text[:MAX_LEN], chat_id, msg_id)

    for idx in range(1, len(parts)):
        chunk = parts[idx]
        if idx == len(parts) - 1:
            chunk += cost_suffix
        try:
            await bot.send_message(chat_id, chunk, parse_mode="MarkdownV2")
        except Exception:
            await bot.send_message(chat_id, chunk)