import os
import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ── Подключение к Supabase ───────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# USERS
# ============================================================

def register_user(uid: str, username: str, first_name: str) -> bool:
    """
    Регистрирует нового пользователя.
    Возвращает True если пользователь новый, False если уже существует.
    """
    existing = (
        supabase.table("users")
        .select("uid")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    if existing.data:
        return False

    today = datetime.datetime.now(datetime.timezone.utc).isoformat()

    supabase.table("users").insert({
        "uid":        uid,
        "username":   username,
        "first_name": first_name,
        "join_date":  today,
    }).execute()

    supabase.table("stats").insert({
        "uid":        uid,
        "streak":     1,
        "last_login": today,
        "total_msgs": 0,
    }).execute()

    return True


def get_user(uid: str) -> dict | None:
    """Возвращает профиль пользователя или None."""
    res = (
        supabase.table("users")
        .select("username, first_name, join_date")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    return res.data


def get_stats(uid: str) -> dict | None:
    """Возвращает статистику пользователя или None."""
    res = (
        supabase.table("stats")
        .select("streak, last_login, total_msgs")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    return res.data


def increment_msg_count(uid: str):
    """Увеличивает счётчик сообщений на 1."""
    supabase.rpc("increment_msgs", {"user_uid": uid}).execute()


def update_streak(uid: str) -> tuple[int, int]:
    """
    Проверяет и обновляет стрик при входе.
    Возвращает (new_streak, daily_reward).
    """
    now       = datetime.datetime.now(datetime.timezone.utc)
    today     = now.date().isoformat()
    yesterday = (now.date() - datetime.timedelta(days=1)).isoformat()

    stats = get_stats(uid)
    if not stats:
        return 0, 0

    streak      = stats["streak"]
    last_login  = stats["last_login"][:10]  # берём только дату YYYY-MM-DD

    if last_login == today:
        return streak, 0  # уже заходил сегодня

    new_streak = streak + 1 if last_login == yesterday else 1
    daily_reward = min(new_streak, 50)

    supabase.table("stats").update({
        "streak":     new_streak,
        "last_login": now.isoformat(),
    }).eq("uid", uid).execute()

    return new_streak, daily_reward


def update_username(uid: str, username: str, first_name: str):
    """Обновляет username и first_name при каждом входе (могут измениться)."""
    supabase.table("users").update({
        "username":   username,
        "first_name": first_name,
    }).eq("uid", uid).execute()


# ============================================================
# ECONOMY (Purrs)
# ============================================================

def get_balance(uid: str) -> int:
    """
    Баланс = сумма входящих − сумма исходящих транзакций.
    """
    incoming = (
        supabase.table("ledger")
        .select("amount")
        .eq("receiver_uid", uid)
        .execute()
    )
    outgoing = (
        supabase.table("ledger")
        .select("amount")
        .eq("sender_uid", uid)
        .execute()
    )

    total_in  = sum(r["amount"] for r in (incoming.data or []))
    total_out = sum(r["amount"] for r in (outgoing.data  or []))
    return total_in - total_out


def make_transaction(
    sender: str, receiver: str, amount: int, tx_type: str = "transfer"
) -> bool:
    """
    Проводит транзакцию.
    sender='SYSTEM' — монеты создаются из пула (бонусы, награды).
    Возвращает False если баланса не хватает.
    """
    if sender != "SYSTEM" and get_balance(sender) < amount:
        return False

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    supabase.table("ledger").insert({
        "sender_uid":   sender,
        "receiver_uid": receiver,
        "amount":       amount,
        "tx_type":      tx_type,
        "timestamp":    now,
    }).execute()
    return True


def check_reward_claimed(uid: str, tx_type: str) -> bool:
    """Проверяет, была ли уже выдана награда данного типа."""
    res = (
        supabase.table("ledger")
        .select("tx_id")
        .eq("receiver_uid", uid)
        .eq("tx_type", tx_type)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def get_transaction_history(uid: str, limit: int = 10) -> list[dict]:
    """Возвращает последние N транзакций пользователя."""
    res = (
        supabase.table("ledger")
        .select("sender_uid, receiver_uid, amount, tx_type, timestamp")
        .or_(f"sender_uid.eq.{uid},receiver_uid.eq.{uid}")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_top_balances(limit: int = 10) -> list[dict]:
    """
    Топ пользователей по балансу.
    Используем RPC-функцию в Supabase для агрегации.
    """
    res = supabase.rpc("get_top_balances", {"lim": limit}).execute()
    return res.data or []


# ============================================================
# CHAT HISTORY
# ============================================================

CHAT_HISTORY_LIMIT = 100  # максимум сообщений на пользователя

def save_message(uid: str, role: str, content: str):
    """Сохраняет сообщение в историю чата и обрезает до лимита."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    supabase.table("chats").insert({
        "uid":       uid,
        "role":      role,
        "content":   content,
        "timestamp": now,
    }).execute()

    # Чистим старые сообщения — оставляем только последние CHAT_HISTORY_LIMIT
    old_rows = (
        supabase.table("chats")
        .select("id")
        .eq("uid", uid)
        .order("id", desc=True)
        .offset(CHAT_HISTORY_LIMIT)
        .execute()
    )
    if old_rows.data:
        ids_to_delete = [r["id"] for r in old_rows.data]
        supabase.table("chats").delete().in_("id", ids_to_delete).execute()


def get_chat_history(uid: str, limit: int = 10) -> list[dict]:
    """
    Возвращает последние N сообщений в хронологическом порядке
    для передачи в модель.
    """
    res = (
        supabase.table("chats")
        .select("role, content")
        .eq("uid", uid)
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    # Разворачиваем — из БД приходит «новое первым», модели нужно хронологически
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_chat_history(uid: str):
    """Удаляет всю историю чатов пользователя."""
    supabase.table("chats").delete().eq("uid", uid).execute()


def get_last_activity(uid: str) -> datetime.datetime | None:
    """Возвращает дату последнего сообщения пользователя."""
    res = (
        supabase.table("chats")
        .select("timestamp")
        .eq("uid", uid)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    try:
        return datetime.datetime.fromisoformat(res.data[0]["timestamp"])
    except Exception:
        return None


def get_all_user_ids() -> list[str]:
    """Возвращает список всех uid для планировщика напоминаний."""
    res = supabase.table("users").select("uid").execute()
    return [r["uid"] for r in (res.data or [])]


# ============================================================
# DATASET (для обучения ИИ)
# ============================================================

def save_to_dataset(query: str, response: str):
    """Анонимно сохраняет пару вопрос → ответ для обучения модели."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    supabase.table("training_data").insert({
        "user_query":   query,
        "ai_response":  response,
        "timestamp":    now,
    }).execute()