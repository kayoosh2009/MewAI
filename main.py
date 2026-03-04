
#   $$\      $$\                          $$$$$$\  $$$$$$\ 
#   $$$\    $$$ |                        $$  __$$\ \_$$  _|
#   $$$$\  $$$$ | $$$$$$\  $$\  $$\  $$\ $$ /  $$ |  $$ |  
#   $$\$$\$$ $$ |$$  __$$\ $$ | $$ | $$ |$$$$$$$$ |  $$ |  
#   $$ \$$$  $$ |$$$$$$$$ |$$ | $$ | $$ |$$  __$$ |  $$ |  
#   $$ |\$  /$$ |$$   ____|$$ | $$ | $$ |$$ |  $$ |  $$ |  
#   $$ | \_/ $$ |\$$$$$$$\ \$$$$$\$$$$  |$$ |  $$ |$$$$$$\ 
#   \__|     \__| \_______| \_____\____/ \__|  \__|\______|
                                                       
                                                       
import os
import telebot
from telebot import types
from dotenv import load_dotenv
import json
import datetime
from ollama import Client

# Загрузка настроек
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
bot = telebot.TeleBot(TOKEN)

#pip install -r requirements.txt

POSTS_LIST = [
    "https://t.me/kayoosh_channel/284",
    "https://t.me/kayoosh_channel/285",
    "https://t.me/kayoosh_channel/286"
]












#      \__$$ |                                                                      $$ |      
#         $$ | $$$$$$$\  $$$$$$\  $$$$$$$\        $$\  $$\  $$\  $$$$$$\   $$$$$$\  $$ |  $$\ 
#         $$ |$$  _____|$$  __$$\ $$  __$$\       $$ | $$ | $$ |$$  __$$\ $$  __$$\ $$ | $$  |
#   $$\   $$ |\$$$$$$\  $$ /  $$ |$$ |  $$ |      $$ | $$ | $$ |$$ /  $$ |$$ |  \__|$$$$$$  / 
#   $$ |  $$ | \____$$\ $$ |  $$ |$$ |  $$ |      $$ | $$ | $$ |$$ |  $$ |$$ |      $$  _$$<  
#   \$$$$$$  |$$$$$$$  |\$$$$$$  |$$ |  $$ |      \$$$$$\$$$$  |\$$$$$$  |$$ |      $$ | \$$\ 
#    \______/ \_______/  \______/ \__|  \__|       \_____\____/  \______/ \__|      \__|  \__|
                                                                                          
                                                                                          

def load_json(path):
    # Автоматическое создание папки, если её нет
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
        print(f"📁 Создана папка: {folder}")

    # Если файла нет, создаем его с пустым словарем {}
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        print(f"📄 Создан файл: {path}")
        return {}

    # Читаем файл
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Ошибка при чтении {path}: {e}")
        return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Инициализация всех баз данных
# Теперь они создадутся сами при первом запуске
users = load_json('data/users.json')
stats = load_json('data/stats.json')
chats = load_json('data/chats.json')
# language.json обычно создается вручную тобой, но если его нет — создастся пустой
locales = load_json('language.json')

# Утилита для текста (RU/EN)
def get_text(uid, key):
    # Проверяем язык пользователя, по умолчанию 'en'
    user_data = users.get(str(uid), {})
    lang = user_data.get('lang', 'en')
    
    # Ищем текст в locales. Если ключа или языка нет — вернем сам ключ
    lang_data = locales.get(lang, locales.get('en', {}))
    return lang_data.get(key, key)














 

#    $$$$$$\                                                                  $$\           
#   $$  __$$\                                                                 $$ |          
#   $$ /  \__| $$$$$$\  $$$$$$\$$$$\  $$$$$$\$$$$\   $$$$$$\  $$$$$$$\   $$$$$$$ | $$$$$$$\ 
#   $$ |      $$  __$$\ $$  _$$  _$$\ $$  _$$  _$$\  \____$$\ $$  __$$\ $$  __$$ |$$  _____|
#   $$ |      $$ /  $$ |$$ / $$ / $$ |$$ / $$ / $$ | $$$$$$$ |$$ |  $$ |$$ /  $$ |\$$$$$$\  
#   $$ |  $$\ $$ |  $$ |$$ | $$ | $$ |$$ | $$ | $$ |$$  __$$ |$$ |  $$ |$$ |  $$ | \____$$\ 
#   \$$$$$$  |\$$$$$$  |$$ | $$ | $$ |$$ | $$ | $$ |\$$$$$$$ |$$ |  $$ |\$$$$$$$ |$$$$$$$  |
#    \______/  \______/ \__| \__| \__|\__| \__| \__| \_______|\__|  \__| \_______|\_______/ 
                                                                                        
                                                                                        
                                                                                        

@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name or "User"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. РЕГИСТРАЦИЯ В USERS.JSON (Основной профиль)
    if uid not in users:
        users[uid] = {
            "username": username,
            "first_name": first_name,
            "join_date": now,
            "lang": "ru"  # По умолчанию ставим RU, потом предложим сменить
        }
        save_json('data/users.json', users)

    # 2. РЕГИСТРАЦИЯ В STATS.JSON (Экономика)
    if uid not in stats:
        stats[uid] = {
            "balance": 15.0,  # Стартовый капитал
            "total_spent_tokens": 0,
            "last_bonus_date": ""
        }
        save_json('data/stats.json', stats)

    # 3. РЕГИСТРАЦИЯ В CHATS.JSON (История сообщений)
    if uid not in chats:
        chats[uid] = []
        save_json('data/chats.json', chats)

    # ПОДГОТОВКА КНОПОК ВЫБОРА ЯЗЫКА
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ru = types.InlineKeyboardButton("Русский 🇷🇺", callback_data="setlang_ru")
    btn_en = types.InlineKeyboardButton("English 🇺🇸", callback_data="setlang_en")
    markup.add(btn_ru, btn_en)

    # Отправляем приветствие (берем из нашего language.json)
    # Используем uid, чтобы get_text знал, какой язык достать (пока что RU)
    welcome_text = get_text(uid, "start")
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# ОБРАБОТЧИК КНОПОК ВЫБОРА ЯЗЫКА
@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def handle_setlang(call):
    uid = str(call.from_user.id)
    new_lang = call.data.split('_')[1]

    if uid in users:
        users[uid]['lang'] = new_lang
        save_json('data/users.json', users)
        
        # Уведомляем пользователя об успехе
        confirm_text = get_text(uid, "lang_set")
        bot.answer_callback_query(call.id, confirm_text)
        
        # Редактируем сообщение, чтобы убрать кнопки
        bot.edit_message_text(
            confirm_text, 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="Markdown"
        )






@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    uid = str(message.from_user.id)
    
    # Проверяем, есть ли пользователь в базе (на случай, если он не нажал /start)
    if uid not in stats or uid not in users:
        uid = str(message.from_user.id)
        bot.reply_to(message, get_text(uid, "start_needed"))
        return

    # Подготавливаем данные для вставки в текст
    user_name = users[uid].get('first_name', 'User')
    user_balance = stats[uid].get('balance', 0)
    
    # Берем шаблон из language.json и подставляем переменные
    text = get_text(uid, "stats_format").format(
        name=user_name,
        uid=uid,
        balance=f"{user_balance:.2f}" # Округляем до 2 знаков для красоты
    )

    bot.send_message(message.chat.id, text, parse_mode="Markdown")






@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    uid = str(message.from_user.id)
    
    # Проверяем наличие пользователя в базе
    if uid not in chats:
        chats[uid] = []
        save_json('data/chats.json', chats)
    
    # Полностью очищаем список сообщений для этого пользователя
    chats[uid] = []
    save_json('data/chats.json', chats)
    
    # Берем текст подтверждения из нашего language.json
    confirm_text = get_text(uid, "clear_done")
    
    # Отправляем ответ пользователю
    bot.reply_to(message, confirm_text, parse_mode="Markdown")






@bot.message_handler(commands=['lang'])
def cmd_lang(message):
    uid = str(message.from_user.id)
    
    # Создаем кнопки (те же самые, что в /start)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ru = types.InlineKeyboardButton("Русский 🇷🇺", callback_data="setlang_ru")
    btn_en = types.InlineKeyboardButton("English 🇺🇸", callback_data="setlang_en")
    markup.add(btn_ru, btn_en)

    # Текст сообщения на двух языках сразу, чтобы пользователь понял, куда нажать
    text = "Выберите язык / Choose language:"
    
    bot.send_message(message.chat.id, text, reply_markup=markup)





@bot.message_handler(commands=['earn'])
def cmd_earn(message):
    uid = str(message.from_user.id) # Используем message, так как это хендлер команды

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(get_text(uid, "earn_btn_view"), callback_data="earn_view"),
        types.InlineKeyboardButton(get_text(uid, "earn_btn_react"), callback_data="earn_react"),
        types.InlineKeyboardButton(get_text(uid, "earn_btn_sub"), callback_data="earn_sub"),
        types.InlineKeyboardButton(get_text(uid, "earn_btn_apy"), callback_data="earn_apy")
    )

    bot.send_message(
        message.chat.id, 
        get_text(uid, "earn_menu_title"), 
        reply_markup=markup, 
        parse_mode="Markdown"
    )






@bot.callback_query_handler(func=lambda call: call.data.startswith('earn_'))
def handle_earn_all(call):
    uid = str(call.from_user.id)
    action = call.data.split('_')[1]
    channel_id = "@kayoosh_channel"
    post_url = "https://t.me/kayoosh_channel/284"

    # --- ЛОГИКА ПРОСМОТРА (ПЕРЕХОД) ---
    if action == "view":
        viewed = stats[uid].get('viewed_posts', [])
        next_post = next((p for p in POSTS_LIST if p not in viewed), None)

        if not next_post:
            bot.answer_callback_query(call.id, get_text(uid, "all_posts_viewed"), show_alert=True)
            return

        idx = POSTS_LIST.index(next_post)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(get_text(uid, "btn_open_post"), url=next_post),
            types.InlineKeyboardButton(get_text(uid, "btn_confirm_view"), callback_data=f"earn_confirm_{idx}")
        )

        bot.edit_message_text(
            get_text(uid, "view_instruction"), 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup
        )

        # Извлекаем ID пользователя из объекта call
        uid = str(call.from_user.id)

        bot.edit_message_text(
            get_text(uid, "view_instruction"), 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup
        )

    # --- ЛОГИКА ПОДТВЕРЖДЕНИЯ ПРОСМОТРА ---
    elif action == "confirm":
        idx = int(call.data.split('_')[2])
        post_url = POSTS_LIST[idx]
        
        if post_url not in stats[uid].get('viewed_posts', []):
            stats[uid]['balance'] += 10
            stats[uid].setdefault('viewed_posts', []).append(post_url)
            save_json('data/stats.json', stats)
            
            uid = str(call.from_user.id)
            bot.answer_callback_query(call.id, get_text(uid, "reward_view_success"), show_alert=True)
            # Возвращаем пользователя в меню заданий
            cmd_earn(call.message)
        else:
            uid = str(call.from_user.id)
            bot.answer_callback_query(call.id, get_text(uid, "reward_already_claimed"), show_alert=True)

    elif action == "confirm_view":
        stats[uid]['balance'] += 10
        save_json('data/stats.json', stats)
        uid = str(call.from_user.id)
        reward = 10  # Сумма награды

        # Получаем шаблон текста и вставляем в него число
        msg = get_text(uid, "reward_credited").format(reward)

        bot.answer_callback_query(call.id, msg, show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif action == "react":
        uid = str(call.from_user.id)

        # Используем .format() для подстановки ссылки в переведенный текст
        text = get_text(uid, "react_instruction").format(post_url=post_url)

        bot.edit_message_text(
            text, 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="Markdown"
        )

    elif action == "sub":
        try:
            member = bot.get_chat_member(channel_id, call.from_user.id)
            if member.status in ['member', 'administrator', 'creator']:
                now = datetime.datetime.now()
                last_sub = stats[uid].get('last_sub_reward_date', "")
                if not last_sub or (now - datetime.datetime.strptime(last_sub, "%Y-%m-%d")).days >= 7:
                    stats[uid]['balance'] += 100
                    stats[uid]['last_sub_reward_date'] = now.strftime("%Y-%m-%d")
                    save_json('data/stats.json', stats)
                    uid = str(call.from_user.id)
                    reward = 100 # Награда за подписку

                    # Берём универсальный ключ и подставляем в него число 100
                    msg = get_text(uid, "reward_credited").format(reward)

                    bot.answer_callback_query(call.id, msg, show_alert=True)
                else:
                    uid = str(call.from_user.id)

                    bot.answer_callback_query(
                        call.id, 
                        get_text(uid, "reward_limit_weekly"), 
                        show_alert=True
                    )
            else:
                markup = types.InlineKeyboardMarkup()
                uid = str(call.from_user.id)

                markup = types.InlineKeyboardMarkup()
                # Текст кнопки "Подписаться"
                markup.add(types.InlineKeyboardButton(get_text(uid, "btn_subscribe"), url="https://t.me/kayoosh_channel"))

                # Сообщение о том, что подписка не найдена
                bot.send_message(
                    call.message.chat.id, 
                    get_text(uid, "sub_error_msg"), 
                    reply_markup=markup
                )
        except:
            # Получаем uid из объекта call
            uid = str(call.from_user.id)

            bot.answer_callback_query(
                call.id, 
                get_text(uid, "error_admin_rights"), 
                show_alert=True
            )

    elif action == "apy":
        uid = str(call.from_user.id)

        # Получаем текст из JSON и выводим его
        bot.send_message(
            call.message.chat.id, 
            get_text(uid, "apy_deposit_info"), 
            parse_mode="Markdown"
        )





@bot.message_handler(func=lambda message: message.forward_from_chat is not None or message.forward_from is not None)
def handle_forward_check(message):
    uid = str(message.from_user.id)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    stats[uid].setdefault('daily_reposts_count', 0)
    stats[uid].setdefault('last_repost_date', "")

    if stats[uid]['last_repost_date'] != today:
        stats[uid]['daily_reposts_count'] = 0
        stats[uid]['last_repost_date'] = today

    if stats[uid]['daily_reposts_count'] < 5:
        stats[uid]['balance'] += 20
        stats[uid]['daily_reposts_count'] += 1
        save_json('data/stats.json', stats)
        uid = str(message.from_user.id)
        reward = 20
        remaining = 5 - stats[uid].get('daily_reposts_count', 0)

        # Берем перевод и подставляем значения
        text = get_text(uid, "repost_success").format(reward, remaining)

        bot.reply_to(message, text)
    else:
        uid = str(message.from_user.id)
        max_limit = 5 # Твой текущий лимит

        # Вызываем перевод и подставляем цифры лимита
        text = get_text(uid, "repost_limit_reached").format(max_limit, max_limit)

        bot.reply_to(message, text)





def process_apy_step(message):
    uid = str(message.from_user.id)
    try:
        amount = float(message.text)
        if amount < 10 or stats[uid]['balance'] < amount:
            uid = str(message.from_user.id)
            min_deposit = 10

            # Получаем перевод и подставляем минимальную сумму
            text = get_text(uid, "deposit_error_low").format(min_deposit)

            bot.reply_to(message, text)
            return
        
        now = datetime.datetime.now()
        last_apy = stats[uid].get('last_apy_date', "")
        if last_apy and (now - datetime.datetime.strptime(last_apy, "%Y-%m-%d")).days < 30:
            uid = str(message.from_user.id)

            # Используем функцию локализации
            bot.reply_to(message, get_text(uid, "deposit_limit_monthly"))
            return

        stats[uid]['balance'] -= amount
        stats[uid]['apy_stake'] = stats[uid].get('apy_stake', 0) + amount
        stats[uid]['last_apy_date'] = now.strftime("%Y-%m-%d")
        save_json('data/stats.json', stats)
        uid = str(message.from_user.id)
        daily_profit = amount * 0.04

        # Получаем локализованный текст и вставляем значения
        text = get_text(uid, "deposit_success").format(amount, daily_profit)

        bot.reply_to(message, text)
    except:
        uid = str(message.from_user.id)

        # Получаем локализованное сообщение об ошибке
        bot.reply_to(message, get_text(uid, "error_invalid_number"))






@bot.message_handler(func=lambda message: message.forward_from_chat is not None)
def handle_forward(message):
    uid = str(message.from_user.id)
    
    # Проверяем, что пост именно из твоего канала (замени ID на свой)
    # Его можно узнать, переслав пост любому боту типа @IDBot
    MY_CHANNEL_ID = -100234567890  # Твой ID канала

    if message.forward_from_chat.id == MY_CHANNEL_ID:
        # Проверяем лимиты (5 раз в день)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if stats[uid].get('last_repost_date') != today:
            stats[uid]['daily_reposts_count'] = 0
            stats[uid]['last_repost_date'] = today

        if stats[uid]['daily_reposts_count'] < 5:
            stats[uid]['balance'] += 20
            stats[uid]['daily_reposts_count'] += 1
            save_json('data/stats.json', stats)
            uid = str(message.from_user.id)
            reward = 20
            # Безопасно получаем количество репостов (если ключа нет, ставим 0)
            count = stats.get(uid, {}).get('daily_reposts_count', 0)
            remaining = 5 - count

            # Вызываем перевод и вставляем значения
            text = get_text(uid, "repost_success").format(reward, remaining)

            bot.reply_to(message, text)
        else:
            uid = str(message.from_user.id)

            # Получаем локализованный текст ошибки
            bot.reply_to(message, get_text(uid, "repost_limit_daily"))
    else:
        uid = str(message.from_user.id)

        # Получаем локализованный текст об ошибке источника
        bot.reply_to(message, get_text(uid, "repost_error_wrong_source"))







# --- АДМИН КОМАНДЫ ---
@bot.message_handler(commands=['get'])
def cmd_admin_get(message):
    # 1. Проверка: ты ли это?
    if message.from_user.id != ADMIN_ID:
        return # Просто игнорируем, если пишет не админ

    try:
        # Ожидаемый формат: /get @username 500
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Формат: `/get @username 100`", parse_mode="Markdown")
            return

        target_user = parts[1].replace('@', '') # Убираем @ если есть
        amount = float(parts[2]) # Сколько монет выдать

        # 2. Поиск ID пользователя по юзернейму в нашей базе
        target_uid = None
        for uid, data in users.items():
            if data.get('username') == target_user:
                target_uid = uid
                break
        
        # 3. Если нашли — начисляем
        if target_uid:
            if target_uid not in stats: # На всякий случай проверяем stats
                stats[target_uid] = {"balance": 0.0, "total_spent_tokens": 0, "last_bonus_date": ""}
            
            stats[target_uid]['balance'] += amount
            save_json('data/stats.json', stats)
            
            bot.reply_to(message, f"✅ Пользователю @{target_user} выдано **{amount}** монет!", parse_mode="Markdown")
            
            # Опционально: уведомляем счастливчика
            try:
                bot.send_message(target_uid, f"🎁 Админ начислил вам **{amount}** монет!", parse_mode="Markdown")
            except:
                pass # Если пользователь заблокировал бота
        else:
            bot.reply_to(message, f"❌ Пользователь @{target_user} не найден в базе данных.")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: `{e}`", parse_mode="Markdown")






@bot.message_handler(commands=['announce'])
def admin_announce_start(message):
    if message.from_user.id != ADMIN_ID: return
    
    msg = bot.send_message(message.chat.id, "📢 **РАССЫЛКА (Шаг 1/2)**\nВведите сообщение для **РУССКИХ** пользователей или напишите `cancel` для отмены:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, admin_announce_ru_step)

# --- ШАГ 2: Получение RU текста и запрос EN ---
def admin_announce_ru_step(message):
    if message.text and message.text.lower() == 'cancel':
        bot.send_message(message.chat.id, "❌ Рассылка отменена.")
        return
    
    ru_text = message.text # Сохраняем русский текст
    msg = bot.send_message(message.chat.id, "📢 **РАССЫЛКА (Шаг 2/2)**\nТеперь введите сообщение для **АНГЛИЙСКИХ** пользователей или напишите `cancel`:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, admin_announce_en_step, ru_text)

# --- ШАГ 3: Получение EN текста и ФИНАЛ ---
def admin_announce_en_step(message, ru_text):
    if message.text and message.text.lower() == 'cancel':
        bot.send_message(message.chat.id, "❌ Рассылка отменена.")
        return

    en_text = message.text
    count = 0
    errors = 0

    bot.send_message(message.chat.id, "🚀 Начинаю рассылку...")

    # Проходим по всем пользователям
    for uid, data in users.items():
        try:
            target_lang = data.get('lang', 'en')
            final_text = ru_text if target_lang == 'ru' else en_text
            
            # Отправляем сообщение
            bot.send_message(uid, final_text, parse_mode="Markdown")
            count += 1
        except Exception:
            errors += 1
            continue # Если заблокировал бота — идем дальше

    # Отправка русской версии в канал (как ты и просил)
    try:
        CHANNEL_ID = os.getenv('CHANNEL_ID')
        bot.send_message(CHANNEL_ID, ru_text, parse_mode="Markdown")
    except:
        pass

    bot.send_message(message.chat.id, f"✅ **Рассылка завершена!**\n\nДоставлено: `{count}`\nОшибок (блок бота): `{errors}`", parse_mode="Markdown")













#    $$$$$$\  $$$$$$\       $$\                          $$\           
#   $$  __$$\ \_$$  _|      $$ |                         \__|          
#   $$ /  $$ |  $$ |        $$ |      $$$$$$\   $$$$$$\  $$\  $$$$$$$\ 
#   $$$$$$$$ |  $$ |        $$ |     $$  __$$\ $$  __$$\ $$ |$$  _____|
#   $$  __$$ |  $$ |        $$ |     $$ /  $$ |$$ /  $$ |$$ |$$ /      
#   $$ |  $$ |  $$ |        $$ |     $$ |  $$ |$$ |  $$ |$$ |$$ |      
#   $$ |  $$ |$$$$$$\       $$$$$$$$\\$$$$$$  |\$$$$$$$ |$$ |\$$$$$$$\ 
#     \__|\______|      \________|\______/  \____$$ |\__| \_______|
#                                              $$\   $$ |              
#                                              \$$$$$$  |              
#                                               \______/   


ollama_client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

@bot.message_handler(func=lambda message: True)
def ai_message_handler(message):
    uid = str(message.from_user.id)
    
    # 1. ПРОВЕРКА: Есть ли юзер в базе?
    if uid not in stats:
        bot.reply_to(message, "❌ Пожалуйста, напишите /start для регистрации.")
        return

    # 2. ПРОВЕРКА БАЛАНСА
    user_balance = stats[uid].get('balance', 0)
    if user_balance <= 0:
        bot.reply_to(message, get_text(uid, "low_balance_error").format(balance=user_balance))
        return

    # 3. ПОДГОТОВКА КОНТЕКСТА
    user_history = chats.get(uid, [])
    user_history.append({'role': 'user', 'content': message.text})
    
    # Ограничиваем память (последние 10 сообщений), чтобы не тратить лишние монеты
    if len(user_history) > 10:
        user_history = user_history[-10:]

    # Сообщение ожидания
    status_msg = bot.reply_to(message, get_text(uid, "ai_thinking"))
    
    full_response = ""
    last_update_time = datetime.datetime.now()

    try:
        # 4. ЗАПРОС К OLLAMA
        # Берем системный промпт из language.json
        system_msg = {'role': 'system', 'content': get_text(uid, "system_prompt")}
        messages_to_send = [system_msg] + user_history

        # Стриминг ответа
        for part in ollama_client.chat('gpt-oss:120b', messages=messages_to_send, stream=True):
            chunk = part['message']['content']
            full_response += chunk
            
            # Обновляем сообщение в ТГ не чаще чем раз в 2 секунды (лимиты Telegram)
            if (datetime.datetime.now() - last_update_time).total_seconds() > 2.0:
                try:
                    bot.edit_message_text(full_response + " ▌ ", message.chat.id, status_msg.message_id)
                    last_update_time = datetime.datetime.now()
                except:
                    pass # Пропускаем ошибки редактирования

        # 5. РАСЧЕТ СТОИМОСТИ
        # Считаем примерно: 1 токен ≈ 4 символа. Или используем длину текста.
        # Твой алгоритм: 1 монета = 5300 токенов. 
        # Допустим, 1 символ текста = 0.25 токена.
        total_chars = len(message.text) + len(full_response)
        tokens_spent = total_chars / 4  # Приблизительная оценка
        coins_to_deduct = tokens_spent / 5300

        # Списываем баланс (может уйти в минус, как ты и хотел)
        stats[uid]['balance'] -= coins_to_deduct
        stats[uid]['total_spent_tokens'] += tokens_spent
        save_json('data/stats.json', stats)

        # 6. ФИНАЛЬНОЕ ОБНОВЛЕНИЕ
        final_text = full_response + f"\n\n💰 -{coins_to_deduct:.4f} 🪙"
        
        try:
            bot.edit_message_text(
                chat_id=message.chat.id, 
                message_id=status_msg.message_id, 
                text=final_text, 
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.edit_message_text(
                chat_id=message.chat.id, 
                message_id=status_msg.message_id, 
                text=final_text
            )
            print(f"Ошибка Markdown: {e}")

        # Сохраняем ответ в историю
        user_history.append({'role': 'assistant', 'content': full_response})
        chats[uid] = user_history
        save_json('data/chats.json', chats)

    except Exception as e:  # ЭТОТ БЛОК ОБЯЗАТЕЛЕН! Он закрывает самый первый try
        print(f"Ошибка ИИ: {e}")
        # Пытаемся отправить сообщение об ошибке пользователю
        try:
            bot.edit_message_text(
                get_text(uid, "ai_error"), 
                message.chat.id, 
                status_msg.message_id
            )
        except:
            pass

# ЗАПУСК БОТА (вне функции handle_message)
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()