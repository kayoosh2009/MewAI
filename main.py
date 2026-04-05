import os
import re
import itertools
import base64
import requests
import html
import datetime
import sqlite3
 
import telebot
from telebot import types
from dotenv import load_dotenv
from ollama import Client

# ── Загрузка переменных из .env ─────────────────────────────
load_dotenv()
 
TOKEN    = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# ── Инициализация бота ───────────────────────────────────────
bot = telebot.TeleBot(TOKEN)

LOG_CHAT_ID = 3722531501
def send_log(tag: str, message_text: str):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    payload = f"🕒 `{now}`\n{message_text}\n\n#{tag}"
    try:
        bot.send_message(LOG_CHAT_ID, payload, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Лог не отправлен: {e}")

API_KEYS   = [os.getenv(f'OLLAMA_API_KEY_{i}') for i in range(1, 11)]
API_KEYS   = [k for k in API_KEYS if k]
_key_cycle = None

def get_next_key() -> str:
    global _key_cycle
    if _key_cycle is None:
        _key_cycle = itertools.cycle(API_KEYS)
    return next(_key_cycle)
    
# ── Каналы для подписки (earn) ───────────────────────────────
CHANNELS_TO_SUB = [
    {
        "id":   "-1003826745366",
        "link": "https://t.me/ne1roneko_community",
        "name": "MewAI Community"
    },
    {
        "id":   "-1003414162996",
        "link": "https://t.me/kayoosh_channel",
        "name": "Окровавленная комнатка Кая"
    },
]





# ── Инициализация основной БД ────────────────────────────────
def init_db():
    conn = sqlite3.connect('mewai.db')
    c = conn.cursor()
 
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            uid        TEXT PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            join_date  TEXT
        )
    ''')
 
    c.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            uid        TEXT PRIMARY KEY,
            streak     INTEGER DEFAULT 0,
            last_login TEXT,
            total_msgs INTEGER DEFAULT 0,
            FOREIGN KEY (uid) REFERENCES users(uid)
        )
    ''')
 
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            uid       TEXT,
            role      TEXT,
            content   TEXT,
            timestamp TEXT,
            FOREIGN KEY (uid) REFERENCES users(uid)
        )
    ''')
 
    c.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            tx_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_uid  TEXT,
            receiver_uid TEXT,
            amount      INTEGER,
            tx_type     TEXT,
            timestamp   TEXT
        )
    ''')
 
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_pool (
            id           INTEGER PRIMARY KEY,
            total_purrs  INTEGER DEFAULT 100000000000
        )
    ''')
    c.execute("SELECT COUNT(*) FROM global_pool")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO global_pool (total_purrs) VALUES (100000000000)")
 
    conn.commit()
    conn.close()
 
 
# ── Инициализация БД для датасета ───────────────────────────
def init_dataset_db():
    """
    Отдельная база — только для обучения ИИ.
    Хранит анонимные пары: вопрос пользователя → ответ модели.
    """
    conn = sqlite3.connect('dataset.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS training_data (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_query TEXT,
            ai_response TEXT,
            timestamp  TEXT
        )
    ''')
    conn.commit()
    conn.close()
 
# ── Запускаем создание таблиц при старте
init_db()
init_dataset_db()
 
# ── Оптимизация БД при старте
def repair_database():
    """
    Запускается один раз при старте.
    WAL-режим решает 90% проблем с блокировками на хостингах.
    VACUUM убирает мусор и сжимает файл.
    """
    for db_name in ['mewai.db', 'dataset.db']:
        try:
            conn = sqlite3.connect(db_name)
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA temp_store=MEMORY;")
            c.execute("VACUUM;")
            # Чистим старые чаты — оставляем только последние 2000 записей
            if db_name == 'mewai.db':
                c.execute('''
                    DELETE FROM chats
                    WHERE id NOT IN (
                        SELECT id FROM chats ORDER BY id DESC LIMIT 2000
                    )
                ''')
            conn.commit()
            conn.close()
            print(f"✅ {db_name} оптимизирована")
        except Exception as e:
            print(f"❌ Ошибка {db_name}: {e}")
 
 
# ── Универсальный запрос к БД ────────────────────────────────
def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    """
    Один метод для всех запросов к mewai.db.
    Сам открывает и закрывает соединение — не надо думать об этом везде.
    """
    conn = sqlite3.connect('mewai.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:  return c.fetchone()
        if fetchall:  return c.fetchall()
        if commit:    conn.commit()
    finally:
        conn.close()
 
def save_to_dataset(query: str, response: str):
    """Анонимно сохраняет пару вопрос→ответ в датасет для обучения."""
    try:
        conn = sqlite3.connect('dataset.db')
        c = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO training_data (user_query, ai_response, timestamp) VALUES (?, ?, ?)",
            (query, response, now)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Dataset error: {e}")
 
 
# ── Работа с пользователями ──────────────────────────────────
def register_user(uid: str, username: str, first_name: str):
    """Создаёт профиль и статистику для нового пользователя."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    db_query(
        "INSERT OR IGNORE INTO users (uid, username, first_name, join_date) VALUES (?, ?, ?, ?)",
        (uid, username, first_name, today), commit=True
    )
    db_query(
        "INSERT OR IGNORE INTO stats (uid, streak, last_login, total_msgs) VALUES (?, 1, ?, 0)",
        (uid, today), commit=True
    )
 
def get_user(uid: str):
    """Возвращает (username, first_name, join_date) или None."""
    return db_query(
        "SELECT username, first_name, join_date FROM users WHERE uid = ?",
        (uid,), fetchone=True
    )
 
def get_stats(uid: str):
    """Возвращает (streak, last_login, total_msgs) или None."""
    return db_query(
        "SELECT streak, last_login, total_msgs FROM stats WHERE uid = ?",
        (uid,), fetchone=True
    )
 
def increment_msg_count(uid: str):
    """Добавляет +1 к счётчику сообщений пользователя."""
    db_query(
        "UPDATE stats SET total_msgs = total_msgs + 1 WHERE uid = ?",
        (uid,), commit=True
    )
 
def update_streak(uid: str):
    """
    Проверяет и обновляет стрик при входе.
    Возвращает (new_streak, daily_reward) — сколько Purrs начислить.
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
 
    stats = get_stats(uid)
    if not stats:
        return 0, 0
 
    streak, last_login, _ = stats
 
    if last_login == today:
        return streak, 0  # Уже заходил сегодня — ничего не делаем
 
    new_streak = streak + 1 if last_login == yesterday else 1
    daily_reward = min(new_streak, 50)  # Максимум 50 Purrs за один день
 
    db_query(
        "UPDATE stats SET streak = ?, last_login = ? WHERE uid = ?",
        (new_streak, today, uid), commit=True
    )
    return new_streak, daily_reward
 
 # ── История чатов ────────────────────────────────────────────
def save_message(uid: str, role: str, content: str):
    """Сохраняет одно сообщение в историю чата."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_query(
        "INSERT INTO chats (uid, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (uid, role, content, now), commit=True
    )
 
def get_chat_history(uid: str, limit: int = 10) -> list:
    """
    Возвращает последние N сообщений для передачи в модель.
    Формат: [{'role': ..., 'content': ...}, ...]
    """
    rows = db_query(
        "SELECT role, content FROM chats WHERE uid = ? ORDER BY id DESC LIMIT ?",
        (uid, limit), fetchall=True
    )
    # Разворачиваем — в БД последнее первое, модели нужно хронологически
    return [{"role": r[0], "content": r[1]} for r in reversed(rows or [])]
 
def clear_chat_history(uid: str):
    """Удаляет всю историю чатов пользователя."""
    db_query("DELETE FROM chats WHERE uid = ?", (uid,), commit=True)
 
 
# ── Экономика (Purrs) ────────────────────────────────────────
def get_balance(uid: str) -> int:
    """
    Считает баланс как разницу входящих и исходящих транзакций.
    Надёжнее чем хранить число — история не теряется.
    """
    incoming = db_query(
        "SELECT SUM(amount) FROM ledger WHERE receiver_uid = ?",
        (uid,), fetchone=True
    )[0] or 0
    outgoing = db_query(
        "SELECT SUM(amount) FROM ledger WHERE sender_uid = ?",
        (uid,), fetchone=True
    )[0] or 0
    return int(incoming - outgoing)
 
 
def make_transaction(sender: str, receiver: str, amount: int, tx_type: str = 'transfer') -> bool:
    """
    Проводит транзакцию между двумя участниками.
    sender='SYSTEM' — деньги создаются из пула (награды, бонусы).
    Возвращает False если у пользователя не хватает баланса.
    """
    if sender != 'SYSTEM' and get_balance(sender) < amount:
        return False
 
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_query(
        "INSERT INTO ledger (sender_uid, receiver_uid, amount, tx_type, timestamp) VALUES (?, ?, ?, ?, ?)",
        (sender, receiver, amount, tx_type, now), commit=True
    )
    return True
 
 
def check_reward_claimed(uid: str, tx_type: str) -> bool:
    """Проверяет, была ли уже выдана награда данного типа юзеру."""
    res = db_query(
        "SELECT tx_id FROM ledger WHERE receiver_uid = ? AND tx_type = ?",
        (uid, tx_type), fetchone=True
    )
    return res is not None





# ============================================================
# MEWAI BOT — PART 3: КОМАНДЫ TELEGRAM
# ============================================================


# ── /start & /menu ───────────────────────────────────────────

@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    uid        = str(message.from_user.id)
    first_name = html.escape(message.from_user.first_name or "Friend")
    username   = html.escape(message.from_user.username   or "anonymous")

    # Регистрируем если новый, иначе просто идём дальше
    is_new = get_user(uid) is None
    register_user(uid, username, first_name)

    if is_new:
        make_transaction('SYSTEM', uid, 15, 'welcome_bonus')
        bonus_line = "🎁 <b>Welcome bonus:</b> +15 Purrs added to your wallet!"
        send_log("NEW_USER", f"👤 New user\nID: `{uid}`\nName: {first_name}\n@{username}")
    else:
        # Обновляем стрик — если заходит не первый раз сегодня, ничего не выдаём
        new_streak, reward = update_streak(uid)
        if reward > 0:
            make_transaction('SYSTEM', uid, reward, 'daily_reward')
            bonus_line = f"🔥 <b>Daily reward:</b> +{reward} Purrs! (Streak: {new_streak} days)"
            send_log("STREAK", f"🔥 Streak updated\n@{username} → {new_streak} days, +{reward} Purrs")
        else:
            bonus_line = ""

    # Клавиатура
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💰 Earn"),
        types.KeyboardButton("📊 Stats"),
        types.KeyboardButton("🔥 Streak"),
        types.KeyboardButton("🧹 Clear Chat"),
    )

    text = (
        f"Hey <b>{first_name}</b> 👋\n\n"
        "I'm <b>MewAI</b> — your AI companion built into Telegram.\n"
        "Just send me a message and I'll reply. I can chat, help with code, "
        "analyze images, and more.\n\n"
        "<b>Commands:</b>\n"
        "• /menu — show this screen\n"
        "• /stats — your profile & balance\n"
        "• /streak — daily check-in & streak reward\n"
        "• /clear — reset chat history\n\n"
        "💡 <i>Send me a photo and I'll describe what I see.</i>\n\n"
        f"{bonus_line}"
    )

    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")


# ── /stats ───────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text in ['/stats', '📊 Stats'])
def cmd_stats(message):
    uid = str(message.from_user.id)

    user  = get_user(uid)
    stats = get_stats(uid)

    if not user or not stats:
        bot.reply_to(message, "❌ Profile not found. Send /start first.")
        return

    username, first_name, join_date = user
    streak, last_login, total_msgs  = stats
    balance = get_balance(uid)

    # Считаем сколько дней с регистрации
    try:
        joined  = datetime.datetime.strptime(join_date, "%Y-%m-%d")
        days_in = (datetime.datetime.now() - joined).days
    except Exception:
        days_in = 0

    receipt = (
        "```\n"
        "======== MEWAI PROFILE =========\n"
        f"  NAME    : {first_name}\n"
        f"  HANDLE  : @{username}\n"
        f"  ID      : {uid}\n"
        "--------------------------------\n"
        f"  JOINED  : {join_date} ({days_in}d ago)\n"
        f"  STREAK  : {streak} days\n"
        f"  MESSAGES: {total_msgs}\n"
        "--------------------------------\n"
        f"  BALANCE : {balance} PURRS\n"
        "================================\n"
        "```"
    )

    bot.send_message(message.chat.id, receipt, parse_mode="Markdown")
    send_log("STATS", f"📊 Stats requested by @{username} (`{uid}`)")


# ── /streak ──────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text in ['/streak', '🔥 Streak'])
def cmd_streak(message):
    uid      = str(message.from_user.id)
    username = message.from_user.username or "anonymous"

    user = get_user(uid)
    if not user:
        bot.reply_to(message, "❌ Profile not found. Send /start first.")
        return

    new_streak, reward = update_streak(uid)

    if reward > 0:
        # Выдаём награду
        make_transaction('SYSTEM', uid, reward, 'daily_reward')
        balance = get_balance(uid)

        text = (
            f"🔥 <b>Daily check-in!</b>\n\n"
            f"Streak: <b>{new_streak} days</b>\n"
            f"Reward: <b>+{reward} Purrs</b>\n"
            f"Balance: <code>{balance} Purrs</code>\n\n"
            f"<i>Come back tomorrow to keep your streak going!</i>"
        )
        send_log("STREAK", f"🔥 @{username} checked in — streak {new_streak}d, +{reward} Purrs")
    else:
        # Уже заходил сегодня
        stats   = get_stats(uid)
        balance = get_balance(uid)
        streak  = stats[0] if stats else 0

        text = (
            f"✅ <b>Already checked in today.</b>\n\n"
            f"Streak: <b>{streak} days</b>\n"
            f"Balance: <code>{balance} Purrs</code>\n\n"
            f"<i>Next reward available tomorrow.</i>"
        )

    bot.reply_to(message, text, parse_mode="HTML")


# ── /clear ───────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text in ['/clear', '🧹 Clear Chat'])
def cmd_clear(message):
    uid = str(message.from_user.id)

    clear_chat_history(uid)
    send_log("CLEAR", f"🧹 Chat cleared by @{message.from_user.username} (`{uid}`)")

    bot.reply_to(
        message,
        "🧹 <b>Chat history cleared.</b>\n\n"
        "I no longer remember our previous conversation. "
        "Fresh start — just send your next message!",
        parse_mode="HTML"
    )


# ── /earn + кнопка ───────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text in ['/earn', '💰 Earn'])
def cmd_earn(message):
    uid = str(message.from_user.id)
    balance = get_balance(uid)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Join channel (+100 Purrs)", callback_data="earn_sub"),
        types.InlineKeyboardButton("🔄 Check my balance",          callback_data="earn_refresh"),
    )

    text = (
        "💰 <b>MewAI Earn Center</b>\n\n"
        f"Your balance: <code>{balance} Purrs</code>\n\n"
        "<b>Ways to earn:</b>\n"
        "🔹 <b>Daily streak</b> — use /streak every day\n"
        "🔹 <b>Join channel</b> — one-time reward per channel\n\n"
        "<i>More earning methods coming soon.</i>"
    )

    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('earn_'))
def handle_earn_callbacks(call):
    uid    = str(call.from_user.id)
    action = call.data[len('earn_'):]  # всё после "earn_"

    if action == "refresh":
        balance = get_balance(uid)
        bot.answer_callback_query(call.id, f"💰 Balance: {balance} Purrs", show_alert=True)

    elif action == "sub":
        # Ищем первый канал без награды
        target = None
        for channel in CHANNELS_TO_SUB:
            tx_type = f"sub_reward_{channel['id']}"
            if not check_reward_claimed(uid, tx_type):
                target = channel
                break

        if not target:
            bot.answer_callback_query(call.id, "✅ You've joined all available channels!", show_alert=True)
            return

        # Проверяем подписку
        try:
            status    = bot.get_chat_member(target['id'], call.from_user.id).status
            is_member = status in ['member', 'administrator', 'creator']
        except Exception as e:
            is_member = False
            print(f"Sub check error: {e}")

        if is_member:
            tx_type = f"sub_reward_{target['id']}"
            make_transaction('SYSTEM', uid, 100, tx_type)
            bot.answer_callback_query(call.id, f"✅ +100 Purrs for joining {target['name']}!", show_alert=True)

            next_markup = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Check next channel 🐾", callback_data="earn_sub")
            )
            bot.edit_message_text(
                f"🎉 <b>+100 Purrs earned!</b>\nThanks for joining <b>{target['name']}</b>.\n\nPress below to check the next channel.",
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=next_markup
            )
        else:
            join_markup = types.InlineKeyboardMarkup()
            join_markup.add(types.InlineKeyboardButton(f"Join {target['name']}", url=target['link']))
            join_markup.add(types.InlineKeyboardButton("✅ I joined, check now", callback_data="earn_sub"))

            bot.answer_callback_query(call.id, f"⚠️ You're not in {target['name']} yet.", show_alert=True)
            try:
                bot.edit_message_text(
                    f"To claim your reward, join <b>{target['name']}</b> and press the button below.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="HTML", reply_markup=join_markup
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    raise e


# ── /get (admin only) ────────────────────────────────────────

@bot.message_handler(commands=['get'])
def cmd_admin_give(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ <b>Access denied.</b>", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: <code>/get @username amount</code>", parse_mode="HTML")
        return

    target_username = args[1].replace('@', '')
    try:
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Amount must be a number.", parse_mode="HTML")
        return

    row = db_query("SELECT uid FROM users WHERE username = ?", (target_username,), fetchone=True)
    if not row:
        bot.reply_to(message, f"❌ User @{target_username} not found.", parse_mode="HTML")
        return

    target_uid = row[0]
    make_transaction('SYSTEM', target_uid, amount, 'admin_gift')
    bot.reply_to(message, f"✅ Sent <code>{amount} Purrs</code> to @{target_username}.", parse_mode="HTML")

    try:
        bot.send_message(
            target_uid,
            f"🎁 <b>You received a gift!</b>\nAdmin sent you <code>{amount} Purrs</code>.",
            parse_mode="HTML"
        )
    except Exception:
        pass





# ============================================================
# MEWAI BOT — PART 4: ГЕНЕРАЦИЯ ОТВЕТОВ ИИ
# ============================================================


# ── Системный промпт ─────────────────────────────────────────
# Задаёт характер и поведение бота.
# Главное: подстраивается под пользователя, не спамит текстом.

SYSTEM_PROMPT = """You are MewAI — a chill, sharp AI companion living inside Telegram.

PERSONALITY:
- Match the user's vibe: if they're casual, be casual. If they're serious, be focused.
- Never be robotic. Talk like a smart friend, not a manual.
- Slightly opinionated. Don't be afraid to say "honestly, X is better than Y".

RESPONSE STYLE:
- Keep it short by default. One idea = one short paragraph.
- Only go long if the topic genuinely needs it (step-by-step code, detailed explanation).
- No filler phrases like "Great question!", "Of course!", "Certainly!".
- No self-introductions. Never say "As an AI..." or "I'm here to help".
- Don't greet the user unless they greeted you first.

FORMATTING (Telegram MarkdownV2 rules):
- Use **bold** for key terms only, not decoration.
- Use `inline code` for short code snippets, variables, commands.
- Use ```language blocks``` for any code longer than one line.
- Use bullet points only for actual lists, not for every response.
- Never escape characters manually — the system handles that.

WHAT YOU CAN DO:
- Chat on any topic: tech, life, ideas, opinions.
- Help with code: write, review, debug small snippets.
- Analyze images the user sends.
- Answer questions concisely without padding.

WHAT YOU DON'T DO:
- Mention Purrs, tokens, or economy unless the user asks directly.
- Pretend to have feelings or act overly enthusiastic.
- Write walls of text when a sentence will do."""


# ── Конвертер Markdown → MarkdownV2 ─────────────────────────

def md_to_v2(text: str) -> str:
    """
    Конвертирует обычный Markdown от модели в Telegram MarkdownV2.
    - Код-блоки (``` и `) — не трогает, они уже валидны.
    - **bold** → *bold*, *italic* → _italic_
    - Все спецсимволы в обычном тексте экранирует.
    """
    ESCAPE = r'_[]()~>#+=|{}.!-'
    pattern = re.compile(r'(```[\s\S]*?```|`[^`]+`)', re.MULTILINE)
    parts   = pattern.split(text)
    result  = []

    for part in parts:
        # Код-блок — не трогаем
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

            # Обычный символ
            c    = part[i]
            out += f'\\{c}' if c in ESCAPE else c
            i   += 1

        result.append(out)

    return ''.join(result)


# ── Отправка ответа (с разбивкой на части если длинный) ─────

def send_ai_response(chat_id: int, status_msg_id: int, text: str, cost: int):
    """
    Отправляет готовый ответ в Telegram.
    Пробует MarkdownV2 → если ошибка, падает на plain text.
    Если текст длиннее 4000 символов — разбивает на части.
    """
    MAX_LEN     = 4000
    cost_suffix = f"\n\n💰 \\-{cost} Purrs"
    converted   = md_to_v2(text.strip())

    if len(converted) <= MAX_LEN:
        try:
            bot.edit_message_text(
                converted + cost_suffix,
                chat_id, status_msg_id,
                parse_mode="MarkdownV2"
            )
        except Exception:
            # Fallback: без разметки
            bot.edit_message_text(
                text.strip() + f"\n\n💰 -{cost} Purrs",
                chat_id, status_msg_id
            )
        return

    # Длинный ответ — режем на части
    parts = [converted[i:i+MAX_LEN] for i in range(0, len(converted), MAX_LEN)]

    try:
        bot.edit_message_text(parts[0], chat_id, status_msg_id, parse_mode="MarkdownV2")
    except Exception:
        bot.edit_message_text(text[:MAX_LEN], chat_id, status_msg_id)

    for idx in range(1, len(parts)):
        chunk = parts[idx]
        if idx == len(parts) - 1:
            chunk += cost_suffix
        try:
            bot.send_message(chat_id, chunk, parse_mode="MarkdownV2")
        except Exception:
            bot.send_message(chat_id, chunk)


# ── Скачивание фото из Telegram ─────────────────────────────

def get_image_base64(message) -> str | None:
    """Скачивает фото из Telegram и возвращает base64 строку."""
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url  = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        response  = requests.get(file_url, timeout=15)
        return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        print(f"❌ Фото не загружено: {e}")
        return None


# ── Генерация с Round-Robin по ключам ───────────────────────

def generate_response(messages_payload: list) -> str | None:
    """
    Перебирает API ключи по кругу (round-robin).
    Если ключ падает — берёт следующий.
    Возвращает полный текст ответа или None если все ключи упали.
    """
    for attempt in range(len(API_KEYS)):
        api_key = get_next_key()
        try:
            client = Client(
                host="https://ollama.com",
                headers={'Authorization': f'Bearer {api_key}'}
            )

            full_response = ""
            for part in client.chat(
                'gemma4:31b-cloud',
                messages=messages_payload,
                stream=True
            ):
                full_response += part['message']['content']

            if full_response.strip():
                return full_response

        except Exception as e:
            print(f"⚠️ Ключ #{attempt + 1} упал: {e}")
            continue

    return None


# ── Главный хэндлер сообщений ────────────────────────────────

@bot.message_handler(content_types=[
    'text', 'photo',
    'video', 'animation', 'document', 'sticker', 'voice', 'video_note'
])
def ai_message_handler(message):
    uid       = str(message.from_user.id)
    chat_type = message.chat.type

    # 1. В группах — отвечаем только если упомянули или ответили боту
    if chat_type in ['group', 'supergroup']:
        bot_me     = bot.get_me()
        is_reply   = (
            message.reply_to_message is not None and
            message.reply_to_message.from_user.id == bot_me.id
        )
        is_mention = False
        if message.text and message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    if message.text[entity.offset:entity.offset + entity.length] == f"@{bot_me.username}":
                        is_mention = True
        if not (is_reply or is_mention):
            return

    # 2. Поддерживаем только текст и фото
    if message.content_type not in ['text', 'photo']:
        bot.reply_to(
            message,
            "🐾 <i>I can read text and analyze photos.\nVideos, stickers and voice — not yet!</i>",
            parse_mode="HTML"
        )
        return

    # 3. Проверка баланса
    balance = get_balance(uid)
    if balance < 1:
        bot.reply_to(
            message,
            f"❌ <b>Not enough Purrs.</b>\n"
            f"Balance: <code>{balance}</code>\n\n"
            f"Use /streak to earn daily rewards or /earn for more options.",
            parse_mode="HTML"
        )
        return

    # 4. Определяем тип входящего сообщения
    is_photo  = message.content_type == 'photo'
    user_text = message.caption if (is_photo and message.caption) else (message.text or "")

    # Если фото без подписи — просим модель описать
    if is_photo and not user_text:
        user_text = "Describe what you see in this image."

    # 5. Загружаем историю чата из БД
    history = get_chat_history(uid, limit=10)

    # 6. Формируем сообщение для модели
    if is_photo:
        img_b64 = get_image_base64(message)
        if not img_b64:
            bot.reply_to(message, "❌ Couldn't load the image. Please try again.")
            return
        user_message    = {"role": "user", "content": user_text, "images": [img_b64]}
        history_content = f"[photo] {user_text}"
    else:
        user_message    = {"role": "user", "content": user_text}
        history_content = user_text

    # Сохраняем вопрос в историю (один раз, до генерации)
    save_message(uid, 'user', history_content)
    increment_msg_count(uid)

    messages_to_send = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [user_message]

    # 7. Статус-сообщение пока модель думает
    status_text = "🔍 <i>Analyzing...</i>" if is_photo else "✨ <i>Thinking...</i>"
    status_msg  = bot.reply_to(message, status_text, parse_mode="HTML")

    # 8. Генерация
    full_response = generate_response(messages_to_send)

    if not full_response:
        bot.edit_message_text(
            "❌ All servers are busy right now. Try again in a moment.",
            message.chat.id, status_msg.message_id
        )
        return

    # 9. Считаем стоимость и списываем Purrs
    # 1 Purr за каждые 500 символов, минимум 1
    cost = max(1, len(full_response) // 500)
    make_transaction(uid, 'SYSTEM', cost, 'ai_payment')

    # 10. Отправляем ответ
    send_ai_response(message.chat.id, status_msg.message_id, full_response, cost)

    # 11. Сохраняем ответ бота в историю и датасет
    save_message(uid, 'assistant', full_response)
    save_to_dataset(history_content, full_response)

    # 12. Лог для админа
    send_log("CHAT", (
        f"✉️ **{'Photo' if is_photo else 'Message'}**\n"
        f"👤 @{message.from_user.username or 'anon'} (`{uid}`)\n"
        f"❓ _{history_content[:100]}_\n"
        f"🤖 _{full_response[:120]}..._\n"
        f"💰 `{cost} Purrs`"
    ))


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == '__main__':
    print("🐾 MewAI starting...")
    repair_database()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)