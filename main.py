import os
import asyncio
import random
import datetime
import base64
import requests
import html

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv

import database as db
import commands
from generation import generate_and_stream, send_ai_response

load_dotenv()

TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
LOG_CHAT = int(os.getenv("LOG_CHAT_ID", 0))

bot = Bot(token=TOKEN)
dp  = Dispatcher()

# Подключаем router из commands.py
dp.include_router(commands.router)


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

async def send_log(tag: str, text: str):
    if not LOG_CHAT:
        return
    now     = datetime.datetime.now().strftime("%H:%M:%S")
    payload = f"🕒 <code>{now}</code>\n{text}\n\n#{tag}"
    try:
        await bot.send_message(LOG_CHAT, payload, parse_mode="HTML")
    except Exception as e:
        print(f"❌ Log failed: {e}")


# ============================================================
# СКАЧИВАНИЕ ФОТО
# ============================================================

def get_image_base64(file_path: str) -> str | None:
    try:
        url      = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        response = requests.get(url, timeout=15)
        return base64.b64encode(response.content).decode("utf-8")
    except Exception as e:
        print(f"❌ Image download failed: {e}")
        return None


# ============================================================
# ADMIN: /get — выдать Purrs пользователю
# ============================================================

@dp.message(Command("get"))
async def cmd_admin_give(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ <b>Access denied.</b>", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("Usage: <code>/get @username amount</code>", parse_mode="HTML")
        return

    target_username = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Amount must be a number.", parse_mode="HTML")
        return

    target = db.get_user_by_username(target_username)
    if not target:
        await message.answer(f"❌ User @{target_username} not found.", parse_mode="HTML")
        return

    target_uid = target["uid"]
    db.make_transaction("SYSTEM", target_uid, amount, "admin_gift")
    await message.answer(
        f"✅ Sent <code>{amount} Purrs</code> to @{target_username}.",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            target_uid,
            f"🎁 <b>You received a gift!</b>\nAdmin sent you <code>{amount} Purrs</code>.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ============================================================
# ADMIN: /promo — создать новый промокод и разослать в канал
# ============================================================

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003414162996"))

@dp.message(Command("promo"))
async def cmd_admin_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ <b>Access denied.</b>", parse_mode="HTML")
        return

    args = message.text.split()
    # /promo [CODE] — код можно задать вручную или сгенерировать
    if len(args) >= 2:
        code = args[1].upper()
    else:
        code = "MEW" + str(random.randint(1000, 9999))

    db.create_promo_code(code, reward=10, hours=24)

    text = (
        "🎟 <b>Daily promo code is here!</b>\n\n"
        f"Code: <code>{code}</code>\n"
        "Reward: <b>+10 Purrs</b>\n"
        "Valid for: <b>24 hours</b>\n\n"
        "Use it with /redeem in the bot 🐾"
    )

    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        await message.answer(f"✅ Promo <code>{code}</code> created and posted.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"✅ Code created but channel post failed: {e}", parse_mode="HTML")

    await send_log("PROMO", f"🎟 New promo code: <code>{code}</code>")


# ============================================================
# ГЛАВНЫЙ ХЕНДЛЕР СООБЩЕНИЙ
# ============================================================

@dp.message(F.content_type.in_({"text", "photo"}))
async def ai_message_handler(message: Message):
    uid       = str(message.from_user.id)
    chat_type = message.chat.type

    # В группах — только если упомянули или ответили боту
    if chat_type in ("group", "supergroup"):
        bot_me     = await bot.get_me()
        is_reply   = (
            message.reply_to_message is not None and
            message.reply_to_message.from_user.id == bot_me.id
        )
        is_mention = False
        if message.text and message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention = message.text[entity.offset:entity.offset + entity.length]
                    if mention == f"@{bot_me.username}":
                        is_mention = True
        if not (is_reply or is_mention):
            return

    # Только текст и фото
    if message.content_type not in ("text", "photo"):
        await message.reply(
            "🐾 <i>I can read text and analyze photos.\nVideos, stickers and voice — not yet!</i>",
            parse_mode="HTML"
        )
        return

    # Юзер должен быть зарегистрирован
    if not db.get_user(uid):
        await message.reply(
            "👋 Looks like you're new here! Send /start to get started.",
            parse_mode="HTML"
        )
        return

    # Проверка баланса
    balance = db.get_balance(uid)
    if balance < 1:
        await message.reply(
            "❌ <b>Not enough Purrs.</b>\n"
            f"Balance: <code>{balance}</code>\n\n"
            "Use /streak for a daily reward or /earn for more options.",
            parse_mode="HTML"
        )
        return

    # Определяем тип сообщения
    is_photo  = message.content_type == "photo"
    user_text = message.caption if (is_photo and message.caption) else (message.text or "")

    if is_photo and not user_text:
        user_text = "Describe what you see in this image."

    # Загружаем историю чата (последние 10 сообщений)
    history = db.get_chat_history(uid, limit=10)

    # Формируем сообщение для модели
    if is_photo:
        file_info = await bot.get_file(message.photo[-1].file_id)
        img_b64   = get_image_base64(file_info.file_path)
        if not img_b64:
            await message.reply("❌ Couldn't load the image. Please try again.")
            return
        user_message    = {"role": "user", "content": user_text, "images": [img_b64]}
        history_content = f"[photo] {user_text}"
    else:
        user_message    = {"role": "user", "content": user_text}
        history_content = user_text

    # Сохраняем сообщение юзера в историю и счётчик
    db.save_message(uid, "user", history_content)
    db.increment_msg_count(uid)

    messages_to_send = history + [user_message]

    # Статусное сообщение — покажем пока генерируется
    status_text = "🔍 Analyzing █" if is_photo else "✨ Thinking █"
    status_msg  = await message.reply(status_text)

    # Генерация со стримингом
    full_response = generate_and_stream(
        bot, message.chat.id, status_msg.message_id, messages_to_send
    )

    if not full_response:
        await bot.edit_message_text(
            "❌ All servers are busy right now. Try again in a moment.",
            message.chat.id, status_msg.message_id
        )
        return

    # Считаем стоимость и списываем Purrs
    cost = max(1, len(full_response) // 500)
    db.make_transaction(uid, "SYSTEM", cost, "ai_payment")

    # Финальная отправка с форматированием
    send_ai_response(bot, message.chat.id, status_msg.message_id, full_response, cost)

    # Сохраняем ответ бота
    db.save_message(uid, "assistant", full_response)
    db.save_to_dataset(history_content, full_response)

    # Лог для админа
    username = html.escape(message.from_user.username or "anon")
    await send_log("CHAT", (
        f"✉️ <b>{'Photo' if is_photo else 'Message'}</b>\n"
        f"👤 @{username} (<code>{uid}</code>)\n"
        f"❓ <i>{html.escape(history_content[:100])}</i>\n"
        f"🤖 <i>{html.escape(full_response[:120])}...</i>\n"
        f"💰 <code>{cost} Purrs</code>"
    ))


# ============================================================
# НАПОМИНАНИЯ О НЕАКТИВНОСТИ
# ============================================================

INACTIVITY_MESSAGES = [
    "👋 Hey, haven't heard from you in a while!\nMiss our chats — come say hi 🐾",
    "🐾 Still here whenever you need me.\nIt's been a couple of days — anything on your mind?",
    "✨ Just checking in! Haven't chatted in a bit — what's going on?",
    "😺 Psst... remember me? Come back, I'm bored without you.",
    "🌙 Been quiet lately. Feel free to drop a message anytime — I'm always around.",
]

async def check_inactivity():
    """Проверяет всех юзеров — отправляет напоминание если 48–72 часа молчат."""
    now      = datetime.datetime.now(datetime.timezone.utc)
    all_uids = db.get_all_user_ids()

    for uid in all_uids:
        try:
            last_active = db.get_last_activity(uid)
            if not last_active:
                continue

            # Приводим к offset-aware если нужно
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=datetime.timezone.utc)

            hours_ago = (now - last_active).total_seconds() / 3600

            if 48 <= hours_ago < 72:
                text = random.choice(INACTIVITY_MESSAGES)
                await bot.send_message(uid, text)
                await send_log("INACTIVITY", f"📬 Reminder sent to <code>{uid}</code>")

        except Exception as e:
            print(f"⚠️ Inactivity check failed for {uid}: {e}")


async def inactivity_scheduler():
    """Раз в час проверяет неактивных пользователей."""
    while True:
        await asyncio.sleep(3600)
        try:
            await check_inactivity()
        except Exception as e:
            print(f"❌ Inactivity scheduler error: {e}")


# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    print("🐾 MewAI starting...")

    # Запускаем планировщик фоном
    asyncio.create_task(inactivity_scheduler())

    # Стартуем polling
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())