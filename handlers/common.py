from aiogram import Router, html, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

import database as db  # Твой модуль базы
from keyboards import main_menu_keyboard # Вынеси кнопки в отдельный файл или оставь тут

router = Router()

# ============================================================
# /start
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message):
    uid        = str(message.from_user.id)
    first_name = html.escape(message.from_user.first_name or "Friend")
    username   = message.from_user.username or "anonymous"

    is_new = db.register_user(uid, username, first_name)

    if is_new:
        db.make_transaction("SYSTEM", uid, 15, "welcome_bonus")
        bonus_line = "🎁 <b>Welcome gift:</b> +15 Purrs added to your wallet!\n\n"
    else:
        db.update_username(uid, username, first_name)
        new_streak, reward = db.update_streak(uid)
        if reward > 0:
            db.make_transaction("SYSTEM", uid, reward, "daily_reward")
            bonus_line = f"🔥 <b>Daily reward:</b> +{reward} Purrs! (Streak: {new_streak} days)\n\n"
        else:
            bonus_line = ""

    text = (
        f"Hey, <b>{first_name}</b> 👋\n\n"
        "I'm <b>MewAI</b> — your AI companion built right into Telegram.\n\n"
        "<b>What I can do:</b>\n"
        "• Chat about anything — tech, ideas, life, code\n"
        "• Analyze images you send me\n"
        "• Help debug or write code snippets\n"
        "• Answer questions without the fluff\n\n"
        "<b>How it works:</b>\n"
        "Every reply costs a few <b>Purrs</b> — the in-bot currency.\n"
        "Earn more by checking in daily or joining the channel.\n\n"
        f"{bonus_line}"
        "Use the buttons below or just send a message to start. 🐾"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())

# ============================================================
# /menu
# ============================================================

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    uid   = str(message.from_user.id)
    user  = db.get_user(uid)

    if not user:
        await message.answer("❌ You're not registered yet. Send /start first.")
        return

    balance = db.get_balance(uid)
    first_name = html.escape(user["first_name"] or "Friend")

    text = (
        f"Welcome back, <b>{first_name}</b> 👋\n\n"
        f"💰 Balance: <code>{balance} Purrs</code>\n\n"
        "What would you like to do?"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "cmd_menu")
async def cb_menu(call: CallbackQuery):
    uid   = str(call.from_user.id)
    user  = db.get_user(uid)
    if not user:
        await call.answer("Send /start first.", show_alert=True)
        return

    balance    = db.get_balance(uid)
    first_name = html.escape(user["first_name"] or "Friend")

    text = (
        f"Welcome back, <b>{first_name}</b> 👋\n\n"
        f"💰 Balance: <code>{balance} Purrs</code>\n\n"
        "What would you like to do?"
    )

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    await call.answer()


# ============================================================
# /stats
# ============================================================

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await _show_stats(message.from_user, reply_target=message)


@router.callback_query(F.data == "cmd_stats")
async def cb_stats(call: CallbackQuery):
    await _show_stats(call.from_user, call=call)
    await call.answer()


async def _show_stats(user_obj, reply_target: Message = None, call: CallbackQuery = None):
    uid   = str(user_obj.id)
    user  = db.get_user(uid)
    stats = db.get_stats(uid)

    if not user or not stats:
        text = "❌ Profile not found. Send /start first."
        if call:
            await call.message.edit_text(text, reply_markup=back_to_menu_keyboard())
        else:
            await reply_target.answer(text)
        return

    balance    = db.get_balance(uid)
    first_name = html.escape(user["first_name"] or "—")
    username   = html.escape(user["username"]   or "anonymous")
    join_date  = user["join_date"][:10]
    streak     = stats["streak"]
    total_msgs = stats["total_msgs"]

    try:
        joined  = datetime.datetime.fromisoformat(user["join_date"])
        days_in = (datetime.datetime.now(datetime.timezone.utc) - joined).days
    except Exception:
        days_in = 0

    # Иконка стрика
    if streak >= 30:
        streak_icon = "🏆"
    elif streak >= 14:
        streak_icon = "💎"
    elif streak >= 7:
        streak_icon = "🔥"
    else:
        streak_icon = "⚡"

    text = (
        "╔══ <b>MEWAI PROFILE</b> ══╗\n\n"
        f"👤  <b>{first_name}</b>  •  @{username}\n"
        f"🪪  <code>{uid}</code>\n\n"
        f"📅  Joined <b>{join_date}</b>  ({days_in} days ago)\n"
        f"{streak_icon}  Streak: <b>{streak} days</b>\n"
        f"💬  Messages sent: <b>{total_msgs}</b>\n\n"
        f"╠══════════════════╣\n\n"
        f"💰  Balance: <b>{balance} Purrs</b>\n\n"
        "╚══════════════════╝"
    )

    kb = back_to_menu_keyboard()
    if call:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await reply_target.answer(text, parse_mode="HTML", reply_markup=kb)


# ============================================================
# Возврат в главное меню (через кнопку)
# ============================================================
@router.callback_query(lambda c: c.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📍 <b>Main Menu:</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()