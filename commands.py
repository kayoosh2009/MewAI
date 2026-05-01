import datetime
import html
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db

router = Router()

CHANNEL_ID = -1003414162996

# ── Вспомогательные функции ──────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Stats",   callback_data="cmd_stats"),
            InlineKeyboardButton(text="🔥 Streak",  callback_data="cmd_streak"),
        ],
        [
            InlineKeyboardButton(text="💰 Earn",    callback_data="cmd_earn"),
            InlineKeyboardButton(text="🧹 Clear",   callback_data="cmd_clear_confirm"),
        ],
        [
            InlineKeyboardButton(text="☕ Donate",  callback_data="cmd_donate"),
        ],
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Back to menu", callback_data="cmd_menu")]
    ])

def get_active_promo(code: str) -> dict | None:
    """Возвращает промокод если он существует и ещё активен."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    res = (
        db.supabase.table("promo_codes")
        .select("code, reward, expires_at")
        .eq("code", code.upper())
        .eq("is_active", True)
        .gte("expires_at", now)
        .maybe_single()
        .execute()
    )
    return res.data
 
 
def already_redeemed(uid: str, code: str) -> bool:
    """Проверяет, использовал ли юзер этот промокод."""
    res = (
        db.supabase.table("promo_redemptions")
        .select("id")
        .eq("uid", uid)
        .eq("code", code.upper())
        .maybe_single()
        .execute()
    )
    return bool(res.data)
 
 
def redeem_code(uid: str, code: str, reward: int) -> bool:
    """
    Фиксирует использование промокода и начисляет Purrs.
    Возвращает False если гонка записей (код уже был активирован параллельно).
    """
    try:
        db.supabase.table("promo_redemptions").insert({
            "uid":  uid,
            "code": code.upper(),
        }).execute()
    except Exception:
        # unique(uid, code) сработал — юзер успел использовать код дважды
        return False
 
    db.make_transaction("SYSTEM", uid, reward, f"promo_{code.upper()}")
    return True
 
 
def time_left(expires_at: str) -> str:
    """Возвращает строку с оставшимся временем до истечения промокода."""
    try:
        exp = datetime.datetime.fromisoformat(expires_at)
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = exp - now
        if delta.total_seconds() <= 0:
            return "expired"
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        minutes    = rem // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return "unknown"


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
# /streak
# ============================================================

@router.message(Command("streak"))
async def cmd_streak(message: Message):
    await _show_streak(message.from_user, reply_target=message)


@router.callback_query(F.data == "cmd_streak")
async def cb_streak(call: CallbackQuery):
    await _show_streak(call.from_user, call=call)
    await call.answer()


async def _show_streak(user_obj, reply_target: Message = None, call: CallbackQuery = None):
    uid  = str(user_obj.id)
    user = db.get_user(uid)

    if not user:
        text = "❌ Profile not found. Send /start first."
        if call:
            await call.message.edit_text(text, reply_markup=back_to_menu_keyboard())
        else:
            await reply_target.answer(text)
        return

    new_streak, reward = db.update_streak(uid)

    if reward > 0:
        db.make_transaction("SYSTEM", uid, reward, "daily_reward")
        balance = db.get_balance(uid)

        # Прогресс до следующей милестоуна
        milestones = [7, 14, 30, 60, 100]
        next_ms    = next((m for m in milestones if m > new_streak), None)
        progress   = f"\n🎯  Next milestone: <b>{next_ms} days</b> ({next_ms - new_streak} to go)" if next_ms else "\n🏆  You've hit all milestones!"

        text = (
            "🔥 <b>Daily check-in!</b>\n\n"
            f"Streak: <b>{new_streak} days</b>\n"
            f"Reward: <b>+{reward} Purrs</b>\n"
            f"Balance: <code>{balance} Purrs</code>\n"
            f"{progress}\n\n"
            "<i>Come back tomorrow to keep the streak alive!</i>"
        )
    else:
        stats   = db.get_stats(uid)
        balance = db.get_balance(uid)
        streak  = stats["streak"] if stats else 0

        text = (
            "✅ <b>Already checked in today.</b>\n\n"
            f"Streak: <b>{streak} days</b>\n"
            f"Balance: <code>{balance} Purrs</code>\n\n"
            "<i>Next reward available tomorrow.</i>"
        )

    kb = back_to_menu_keyboard()
    if call:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await reply_target.answer(text, parse_mode="HTML", reply_markup=kb)


# ============================================================
# /clear
# ============================================================

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Yes, clear it", callback_data="cmd_clear_do"),
            InlineKeyboardButton(text="Cancel",        callback_data="cmd_menu"),
        ]
    ])
    await message.answer(
        "🧹 <b>Clear chat history?</b>\n\n"
        "I'll forget everything we've talked about.\n"
        "This can't be undone.",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data == "cmd_clear_confirm")
async def cb_clear_confirm(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Yes, clear it", callback_data="cmd_clear_do"),
            InlineKeyboardButton(text="Cancel",        callback_data="cmd_menu"),
        ]
    ])
    await call.message.edit_text(
        "🧹 <b>Clear chat history?</b>\n\n"
        "I'll forget everything we've talked about.\n"
        "This can't be undone.",
        parse_mode="HTML",
        reply_markup=kb
    )
    await call.answer()


@router.callback_query(F.data == "cmd_clear_do")
async def cb_clear_do(call: CallbackQuery):
    uid = str(call.from_user.id)
    db.clear_chat_history(uid)

    await call.message.edit_text(
        "🧹 <b>Done — chat history cleared.</b>\n\n"
        "Fresh start. Just send your next message! 🐾",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await call.answer("History cleared.")


# ============================================================
# /donate
# ============================================================

DONATE_TEXT = (
    "☕ <b>Support MewAI</b>\n\n"
    "MewAI runs on caffeine and good vibes.\n"
    "If you enjoy using it, consider buying me a coffee!\n\n"
    "<b>TON:</b>\n"
    "<code>UQA...your_ton_address_here</code>\n\n"
    "<b>BTC:</b>\n"
    "<code>bc1q...your_btc_address_here</code>\n\n"
    "<b>Card (RU):</b>\n"
    "<code>0000 0000 0000 0000</code>\n\n"
    "Every little bit helps keep the servers running. 🙏"
)


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    await message.answer(DONATE_TEXT, parse_mode="HTML", reply_markup=back_to_menu_keyboard())


@router.callback_query(F.data == "cmd_donate")
async def cb_donate(call: CallbackQuery):
    await call.message.edit_text(DONATE_TEXT, parse_mode="HTML", reply_markup=back_to_menu_keyboard())
    await call.answer()


# ============================================================
# /earn (заглушка — полная логика будет в отдельном файле)
# ============================================================

@router.callback_query(F.data == "cmd_earn")
async def cb_earn(call: CallbackQuery):
    uid     = str(call.from_user.id)
    balance = db.get_balance(uid)

    text = (
        "💰 <b>Earn Purrs</b>\n\n"
        f"Your balance: <code>{balance} Purrs</code>\n\n"
        "<b>Ways to earn:</b>\n"
        "🔹 <b>Daily streak</b> — check in every day with /streak\n"
        "🔹 <b>Join channel</b> — one-time +100 Purrs per channel\n\n"
        "<i>More methods coming soon.</i>"
    )

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())
    await call.answer()



# ============================================================
# /redeem
# ============================================================
 
@router.message(Command("redeem"))
async def cmd_redeem(message: Message):
    uid  = str(message.from_user.id)
    args = message.text.split(maxsplit=1)
 
    # Нет аргумента — подсказка
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "🎟 <b>Redeem a promo code</b>\n\n"
            "Usage: <code>/redeem CODE</code>\n\n"
            "Daily codes are posted in the channel.\n"
            "Each code gives <b>+10 Purrs</b> and lasts <b>24 hours.</b>",
            parse_mode="HTML"
        )
        return
 
    code = args[1].strip().upper()
 
    # Юзер зарегистрирован?
    if not db.get_user(uid):
        await message.answer("❌ Send /start first to register.")
        return
 
    # Промокод существует и не истёк?
    promo = get_active_promo(code)
    if not promo:
        await message.answer(
            "❌ <b>Invalid or expired code.</b>\n\n"
            "Check the channel for the latest daily code.",
            parse_mode="HTML"
        )
        return
 
    # Уже использован этим юзером?
    if already_redeemed(uid, code):
        left = time_left(promo["expires_at"])
        await message.answer(
            f"⚠️ <b>Already redeemed.</b>\n\n"
            f"You've already used code <code>{code}</code>.\n"
            f"Next code drops in ~<b>{left}</b>.",
            parse_mode="HTML"
        )
        return
 
    # Всё ок — начисляем
    success = redeem_code(uid, code, promo["reward"])
    if not success:
        await message.answer(
            "⚠️ <b>Already redeemed.</b>\n\n"
            "Looks like you used this code just now.",
            parse_mode="HTML"
        )
        return
 
    balance = db.get_balance(uid)
    left    = time_left(promo["expires_at"])
 
    await message.answer(
        f"✅ <b>Code redeemed!</b>\n\n"
        f"<code>{code}</code> → <b>+{promo['reward']} Purrs</b>\n"
        f"Balance: <code>{balance} Purrs</code>\n\n"
        f"<i>Code expires in {left}.</i>",
        parse_mode="HTML"
    )