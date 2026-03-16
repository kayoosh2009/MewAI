
# <--------------- MewAI --------------->                                                     
import os
import telebot
from telebot import types
from dotenv import load_dotenv
import sqlite3
import html
import datetime
from ollama import Client

# Загрузка настроек
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
bot = telebot.TeleBot(TOKEN)

#pip install -r requirements.txt

POSTS_LIST = [
    "https://t.me/kayoosh_channel/213", "https://t.me/kayoosh_channel/214", "https://t.me/kayoosh_channel/215"
]



# <--------------- Database Logic --------------->
def init_db():
    conn = sqlite3.connect('mewai.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            uid TEXT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            streak INTEGER DEFAULT 0,
            last_login TEXT
        )
    ''')
    
    # Таблица истории чатов (ДОБАВЛЕНО)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            role TEXT,
            content TEXT
        )
    ''')
    
    # Пул ликвидности (100кк MewAI = 100ккк Purrs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_pool (
            id INTEGER PRIMARY KEY,
            total_purrs INTEGER DEFAULT 100000000000
        )
    ''')

    # Блокчейн-реестр
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_uid TEXT,
            receiver_uid TEXT,
            amount INTEGER,
            fee INTEGER,
            tx_type TEXT,
            timestamp TEXT
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM global_pool")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO global_pool (total_purrs) VALUES (100000000000)")

    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect('mewai.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        result = None
        if fetchone: result = cursor.fetchone()
        if fetchall: result = cursor.fetchall()
        if commit: conn.commit()
        return result
    finally:
        conn.close()

# --- ФУНКЦИИ ЭКОНОМИКИ ---

def get_balance(uid):
    incoming = db_query("SELECT SUM(amount) FROM ledger WHERE receiver_uid = ?", (uid,), fetchone=True)[0] or 0
    outgoing = db_query("SELECT SUM(amount + fee) FROM ledger WHERE sender_uid = ?", (uid,), fetchone=True)[0] or 0
    return int(incoming - outgoing)

def make_transaction(sender, receiver, amount, tx_type='transfer', fee=0):
    """Универсальная функция для перевода Purrs"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Если платит юзер (не система), проверяем баланс
    if sender != 'SYSTEM':
        if get_balance(sender) < (amount + fee):
            return False
    
    # Записываем в реестр
    db_query(
        "INSERT INTO ledger (sender_uid, receiver_uid, amount, fee, tx_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (sender, receiver, amount, fee, tx_type, now),
        commit=True
    )
    
    # Если есть комиссия или оплата ИИ, пополняем Global Pool
    if fee > 0 or receiver == 'SYSTEM':
        added = fee if receiver != 'SYSTEM' else amount
        db_query("UPDATE global_pool SET total_purrs = total_purrs + ?", (added,), commit=True)
        
    return True

def get_total_messages(uid):
    count = db_query("SELECT COUNT(*) FROM history WHERE uid = ? AND role = 'user'", (uid,), fetchone=True)[0] or 0
    return count

def is_subscribed(user_id):
    """Проверка подписки на канал спонсора"""
    try:
        # Замени на ID своего канала
        status = bot.get_chat_member("-1003414162996", user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def check_reward_claimed(uid, tx_type):
    """Проверяет, получал ли юзер награду этого типа (например, за подписку)"""
    res = db_query("SELECT tx_id FROM ledger WHERE receiver_uid = ? AND tx_type = ?", (uid, tx_type), fetchone=True)
    return res is not None





# <--------------- Commands Logic --------------->  
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    uid = str(message.from_user.id)
    first_name = html.escape(message.from_user.first_name or "Friend")
    username = html.escape(message.from_user.username or "Anonymous")
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. DATABASE REGISTRATION
    # Проверяем, есть ли пользователь в таблице профилей
    user = db_query("SELECT streak, last_login FROM users WHERE uid = ?", (uid,), fetchone=True)

    if not user:
        # Новый пользователь: создаем профиль
        db_query(
            "INSERT INTO users (uid, username, first_name, join_date, streak, last_login) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, username, first_name, today, 1, today),
            commit=True
        )
        # Награда за первую регистрацию (Welcome Bonus) - 15 Purrs
        make_transaction('SYSTEM', uid, 15, 'welcome_bonus')
        bonus_msg = "🎁 Welcome Bonus: +15 Purrs added to your balance!"
    else:
        # Старый пользователь: проверяем Daily Reward (Streak)
        streak, last_login = user
        if last_login != today:
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            new_streak = streak + 1 if last_login == yesterday else 1
            
            # Награда равна количеству дней стрика (но не более 50 за раз, для баланса)
            daily_reward = min(new_streak, 50)
            make_transaction('SYSTEM', uid, daily_reward, 'daily_reward')
            
            db_query("UPDATE users SET streak = ?, last_login = ? WHERE uid = ?", (new_streak, today, uid), commit=True)
            bonus_msg = f"🎁 Daily Bonus: +{daily_reward} Purrs! (Streak: {new_streak} days)"
        else:
            bonus_msg = ""

    # 2. CREATE MENU (Reply Keyboard)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💰 Earn"), 
        types.KeyboardButton("📊 Stats"),
        types.KeyboardButton("🎮 Game"),
        types.KeyboardButton("🧹 Clear Chat")
    )

    # Текст сообщения
    welcome_text = (
        f"Hi <b>{first_name}</b>,\n\n"
        "My name is <b>MewAI</b>. I am a free AI assistant created by @kayoosh_x "
        "that allows you to get fast answers directly in your messenger.\n\n"
        "Our project is built around the new <b>MewAI</b> crypto token. "
        "You can use it here to generate AI responses and support our ecosystem.\n\n"
        "📜 <b>Available Commands:</b>\n"
        "• /stats — Your statistics and balance\n"
        "• /clear — Delete chat history from the database\n"
        "• /earn — Earn Purr tokens\n"
        "• /game — Launch our clicker game\n\n"
        f"<i>{bonus_msg}</i>"
    )

    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=markup, 
        parse_mode="HTML"
    )





@bot.message_handler(commands=['stats'])
@bot.message_handler(func=lambda message: message.text == "📊 Stats")
def cmd_stats(message):
    uid = str(message.from_user.id)
    
    # Получаем данные пользователя из таблицы users
    user_data = db_query("SELECT username, first_name, join_date, streak FROM users WHERE uid = ?", (uid,), fetchone=True)
    
    if not user_data:
        bot.reply_to(message, "❌ Profile not found. Please type /start first!")
        return

    username, first_name, join_date, streak = user_data
    
    # Считаем данные "на лету" из других таблиц
    balance = get_balance(uid)
    total_messages = get_total_messages(uid)

    # Формируем текст в виде чека
    receipt_text = (
        "```\n"
        "========= MEWAI RECEIPT =========\n"
        f"NAME:     {first_name}\n"
        f"HANDLE:   @{username}\n"
        f"ID:       {uid}\n"
        "---------------------------------\n"
        f"JOINED:   {join_date}\n"
        f"STREAK:   {streak} days\n"
        f"MESSAGES: {total_messages}\n"
        "---------------------------------\n"
        f"BALANCE:  {balance} PURRS\n"
        "=================================\n"
        "```\n"
        "🔗 *MewAI Project • Blockchain Ledger*"
    )

    bot.send_message(message.chat.id, receipt_text, parse_mode="Markdown")






@bot.message_handler(commands=['clear'])
@bot.message_handler(func=lambda message: message.text == "🧹 Clear Chat")
def cmd_clear(message):
    uid = str(message.from_user.id)
    
    # 1. Удаляем всю историю переписки пользователя из SQLite
    db_query("DELETE FROM history WHERE uid = ?", (uid,), commit=True)
    
    # 2. Формируем текст подтверждения на английском
    confirm_text = (
        "🧹 *Chat history cleared!*\n"
        "Your context has been reset. Now I won't remember our previous messages, "
        "which saves your tokens for future generations."
    )
    
    # 3. Отправляем ответ
    bot.reply_to(message, confirm_text, parse_mode="Markdown")



@bot.message_handler(commands=['earn'])
@bot.message_handler(func=lambda message: message.text == "💰 Earn")
def cmd_earn(message):
    uid = str(message.from_user.id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Subscribe to Channel (+100 Purrs)", callback_data="earn_sub"),
        types.InlineKeyboardButton("📈 Open Staking (7% APY)", callback_data="earn_apy"),
        types.InlineKeyboardButton("🎮 Play Clicker Game", url="https://yourgame.link"), # Ссылка на твою игру
        types.InlineKeyboardButton("🔄 Refresh Bonus Status", callback_data="earn_refresh")
    )

    earn_text = (
        "🐾 *MewAI Earning Center*\n\n"
        "Complete tasks below to stack up your **Purrs** and support the MewAI ecosystem!\n\n"
        "🔹 **Daily Check-in**: Just use the bot daily to grow your streak!\n"
        "🔹 **Social**: Join our community for massive one-time rewards.\n"
        "🔹 **Staking**: Passive income for long-term holders.\n"
        "🔹 **Game**: Play and withdraw directly from the Global Pool."
    )

    bot.send_message(message.chat.id, earn_text, reply_markup=markup, parse_mode="Markdown")



@bot.callback_query_handler(func=lambda call: call.data.startswith('earn_'))
def handle_earn_callbacks(call):
    uid = str(call.from_user.id)
    action = call.data.split('_')[1]

    if action == "sub":
        # Проверяем, не получал ли уже
        if check_reward_claimed(uid, 'sub_reward'):
            bot.answer_callback_query(call.id, "❌ You have already claimed this reward!", show_alert=True)
            return

        # Проверяем подписку
        if is_subscribed(call.from_user.id):
            # Начисляем 100 Purrs от системы
            make_transaction('SYSTEM', uid, 100, 'sub_reward')
            bot.answer_callback_query(call.id, "✅ Success! +100 Purrs added!", show_alert=True)
            bot.edit_message_text("Thank you for subscribing! Your bonus is credited.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ You are not subscribed to @kayoosh_channel yet!", show_alert=True)

    elif action == "apy":
        # Создаем кнопки для выбора суммы стейкинга
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Stake 100", callback_data="stake_100"),
            types.InlineKeyboardButton("Stake 1000", callback_data="stake_1000"),
            types.InlineKeyboardButton("Stake 10000", callback_data="stake_10000")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Earn", callback_data="earn_refresh"))

        balance = get_balance(uid)
        apy_info = (
            "📈 <b>MewAI Staking</b>\n\n"
            "By staking your Purrs, you lock them for 30 days to support network stability.\n"
            "In return, you get <b>7% monthly growth</b>.\n\n"
            f"Your current balance: <code>{balance} Purrs</code>\n"
            "<i>Choose the amount you want to stake:</i>"
        )
        bot.edit_message_text(apy_info, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Добавляем новый обработчик для самих транзакций стейкинга
    elif action.startswith("stake_"):
        amount = int(call.data.split('_')[2])
        if get_balance(uid) < amount:
            bot.answer_callback_query(call.id, "❌ Not enough Purrs for this stake!", show_alert=True)
        else:
            # Переводим в SYSTEM (заморозка)
            make_transaction(uid, 'SYSTEM', amount, 'staking_deposit')
            bot.answer_callback_query(call.id, f"✅ {amount} Purrs successfully staked!", show_alert=True)
            bot.edit_message_text(f"🚀 <b>Success!</b>\nYou have staked <b>{amount} Purrs</b>.\nRewards will be added in 30 days.", call.message.chat.id, call.message.message_id, parse_mode="HTML")






 
# <--------------- AI generation  --------------->  

# Загружаем все 3 ключа из .env (убедись, что они там есть)
API_KEYS = [
    os.getenv('OLLAMA_API_KEY_1'),
    os.getenv('OLLAMA_API_KEY_2'),
    os.getenv('OLLAMA_API_KEY_3')
]
# Убираем пустые ключи, если вдруг какой-то не указан
API_KEYS = [key for key in API_KEYS if key]

# Указываем ВСЕ типы контента, чтобы бот мог на них реагировать
@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document', 'sticker', 'voice', 'video_note'])
def ai_message_handler(message):
    uid = str(message.from_user.id)
    chat_type = message.chat.type
    
    # 1. ФИЛЬТР ВЫЗОВА В ГРУППАХ (Отвечает только если позвали или ответили)
    bot_me = bot.get_me()
    if chat_type in ['group', 'supergroup']:
        is_mentioned = False
        is_reply = False

        if message.text and message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention_text = message.text[entity.offset:entity.offset + entity.length]
                    if mention_text == f"@{bot_me.username}":
                        is_mentioned = True
        
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_me.id:
            is_reply = True

        if not (is_mentioned or is_reply):
            return

    # 2. ФИЛЬТР МЕДИА-ФАЙЛОВ
    if message.content_type != 'text':
        bot.reply_to(message, "🐾 <i>Meow! I can only read text for now. Images, videos, and stickers are not supported yet!</i>", parse_mode="HTML")
        return

    # 3. ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА БАЛАНСА В SQLITE (Минимум 1 Purr для старта)
    user_balance = get_balance(uid)
    if user_balance < 1:
        bot.reply_to(message, f"❌ <b>Insufficient balance!</b>\nYour balance: <code>{user_balance} Purrs</code>.\nUse /earn to get more!", parse_mode="HTML")
        return

    # 4. ПОДГОТОВКА КОНТЕКСТА ИЗ БД
    raw_history = db_query("SELECT role, content FROM history WHERE uid = ? ORDER BY id DESC LIMIT 10", (uid,), fetchall=True)
    user_history = [{"role": r[0], "content": r[1]} for r in reversed(raw_history)]
    
    user_history.append({'role': 'user', 'content': message.text})
    
    # Сразу сохраняем вопрос юзера в базу данных
    db_query("INSERT INTO history (uid, role, content) VALUES (?, ?, ?)", (uid, 'user', message.text), commit=True)

    status_msg = bot.reply_to(message, "✨ <i>MewAI is pawing through the bytes...</i>", parse_mode="HTML")
    
    # УЛУЧШЕННЫЙ ПРОМТ (Заставляем ИИ использовать HTML и запрещаем Markdown)
    system_prompt = (
        "You are MewAI, a helpful AI assistant in a crypto ecosystem. "
        "Guidelines:\n"
        "1. Be friendly, concise, and use cat-related emojis occasionally.\n"
        "2. Use HTML tags for formatting: <b>bold</b>, <i>italic</i>, <code>code</code>.\n"
        "3. Do NOT use Markdown (like ** or _). This is strictly prohibited. \n"
        "4. Reply to the user in the language they used, crack some jokes, and keep the conversation going!"
    )
    messages_to_send = [{'role': 'system', 'content': system_prompt}] + user_history

    # 5. ГЕНЕРАЦИЯ С ИСПОЛЬЗОВАНИЕМ НЕСКОЛЬКИХ API КЛЮЧЕЙ
    success = False
    full_response = ""
    
    for index, api_key in enumerate(API_KEYS):
        try:
            # Инициализируем клиента с текущим ключом из цикла
            ollama_client = Client(
                host="https://ollama.com",
                headers={'Authorization': f'Bearer {api_key}'}
            )
            
            last_update_time = datetime.datetime.now()
            
            # Стриминг ответа
            for part in ollama_client.chat('gemini-3-flash-preview:cloud', messages=messages_to_send, stream=True):
                chunk = part['message']['content']
                full_response += chunk
                
                # Обновляем сообщение не чаще раза в 2.5 секунды
                if (datetime.datetime.now() - last_update_time).total_seconds() > 2.5:
                    try:
                        bot.edit_message_text(full_response + " ▌", message.chat.id, status_msg.message_id, parse_mode="HTML")
                        last_update_time = datetime.datetime.now()
                    except:
                        pass
            
            # Если дошли сюда без ошибок, значит ответ успешно сгенерирован
            success = True
            break # Прерываем цикл, так как ответ готов
            
        except Exception as e:
            print(f"⚠️ Ошибка с ключом #{index + 1}: {e}")
            full_response = "" # Очищаем мусор перед попыткой со следующим ключом
            continue # Переходим к следующему ключу

    # 6. ЕСЛИ ВСЕ 3 КЛЮЧА НЕ СРАБОТАЛИ
    if not success:
        bot.edit_message_text("❌ Sorry, all AI servers are currently busy or overloaded. Please try again later.", message.chat.id, status_msg.message_id)
        return

    # 7. ДИНАМИЧЕСКИЙ РАСЧЕТ И СПИСАНИЕ СРЕДСТВ
    # 1 Purr за каждые 500 символов (но минимум 1 Purr)
    chars = len(full_response)
    cost = max(1, chars // 500)
    
    # Оплата уходит в SYSTEM (Global Pool)
    make_transaction(uid, 'SYSTEM', cost, 'ai_payment')

    # 8. ФИНАЛЬНОЕ ОБНОВЛЕНИЕ ТЕКСТА (Только HTML)
    final_text = f"{full_response.strip()}\n\n💰 <code>-{cost} Purrs</code>"
    
    try:
        bot.edit_message_text(
            chat_id=message.chat.id, 
            message_id=status_msg.message_id, 
            text=final_text, 
            parse_mode="HTML"
        )
    except Exception as e:
        # Fallback без форматирования, если ИИ все же сломал HTML-теги
        bot.edit_message_text(
            chat_id=message.chat.id, 
            message_id=status_msg.message_id, 
            text=final_text
        )

    # 9. СОХРАНЯЕМ ОТВЕТ В ИСТОРИЮ БД
    db_query("INSERT INTO history (uid, role, content) VALUES (?, ?, ?)", (uid, 'assistant', full_response), commit=True)


# ЗАПУСК БОТА
if __name__ == '__main__':
    print("🐾 MewAI is starting...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)