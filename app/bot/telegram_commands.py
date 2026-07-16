"""
Telegram command handlers with undo, history, and category learning.
"""
import re
import json
import hashlib
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum
from app.cache.merchant_cache import set_merchant, record_appearance
from app.cache.promoter import check_and_promote
from app.cache.redis_client import get_redis
from app.bot.conversation import get_pending_state, clear_pending_state
from app.bot.telegram_keyboards import (
    yes_no_keyboard, category_keyboard,
    confirm_clear_keyboard, history_keyboard
)
from app.config import settings

EXPENSE_PATTERN = re.compile(
    r"^₹?(\d+(?:\.\d{1,2})?)\s+(.+)$|^(.+?)\s+₹?(\d+(?:\.\d{1,2})?)$",
    re.IGNORECASE
)

CORRECTION_PATTERN = re.compile(
    r"^₹?(\d+(?:\.\d{1,2})?)\s+(food|travel|shopping|health|bills|entertainment|other)$",
    re.IGNORECASE
)

CATEGORY_KEYWORDS = {
    "food":          ["swiggy", "zomato", "domino", "pizza", "food", "cafe",
                      "restaurant", "chai", "biryani", "hotel", "dhaba",
                      "bakery", "juice", "snack", "eat", "lunch", "dinner",
                      "breakfast", "pav", "bhaji", "maggi", "tea", "coffee"],
    "travel":        ["irctc", "uber", "ola", "rapido", "redbus", "petrol",
                      "fuel", "cab", "auto", "parking", "railway", "bus",
                      "metro", "flight", "train", "toll"],
    "shopping":      ["amazon", "flipkart", "myntra", "ajio", "meesho",
                      "mall", "store", "mart", "shop", "bazar", "market",
                      "cloth", "dress", "shoes", "bag"],
    "health":        ["pharmacy", "medical", "chemist", "hospital", "clinic",
                      "doctor", "lab", "apollo", "medplus", "netmeds",
                      "1mg", "medicine", "pharma", "health", "gym"],
    "bills":         ["electricity", "jio", "airtel", "bsnl", "recharge",
                      "netflix", "spotify", "prime", "hotstar", "disney",
                      "water", "gas", "rent", "broadband", "wifi", "bill",
                      "mobile", "dth", "insurance"],
    "entertainment": ["bookmyshow", "pvr", "inox", "cinema", "movie",
                      "game", "sport", "concert", "event", "show"],
}

CATEGORY_EMOJIS = {
    "food": "🍔", "travel": "🚗", "shopping": "🛍️",
    "health": "💊", "bills": "💡", "entertainment": "🎬", "other": "📦"
}

CORRECTION_PROMPT = (
    "❌ Please type the correct amount and category:\n\n"
    "Example: 100 food or 192 travel\n\n"
    "Categories: food, travel, shopping, health, bills, entertainment, other"
)

KEYWORD_CACHE_TTL = 30 * 24 * 60 * 60
LAST_TXN_TTL     = 24 * 60 * 60  # store last txn ID for 24 hours


def get_learned_category(sender: str, keyword: str) -> str | None:
    r = get_redis()
    val = r.get(f"keyword:{sender}:{keyword.lower().strip()}")
    return val.decode() if isinstance(val, bytes) else val if val else None


def save_learned_keyword(sender: str, keyword: str, category: str):
    r = get_redis()
    r.setex(f"keyword:{sender}:{keyword.lower().strip()}", KEYWORD_CACHE_TTL, category)


def save_last_txn_id(sender: str, txn_id: int):
    r = get_redis()
    r.setex(f"last_txn:{sender}", LAST_TXN_TTL, str(txn_id))


def get_last_txn_id(sender: str) -> int | None:
    r = get_redis()
    val = r.get(f"last_txn:{sender}")
    if not val:
        return None
    return int(val) if isinstance(val, int) else int(val.decode() if isinstance(val, bytes) else val)


def suggest_category_from_text(text: str) -> str:
    text = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "other"


def get_or_create_user(db, phone_number: str):
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def save_transaction(sender: str, amount: float, category: str,
                     description: str, source: str, raw_input: str) -> int:
    """Save transaction and return its ID."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, sender)
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            category=CategoryEnum(category),
            description=description,
            source=source,
            raw_input=raw_input,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        txn_id = transaction.id
    finally:
        db.close()
    return txn_id


async def handle_start(sender: str) -> dict:
    return {
        "text": (
            "👋 Welcome to *FinBot*!\n\n"
            "• Send *40 chai* or *chai 40* to log an expense\n"
            "• Forward a *UPI screenshot* to auto-log\n"
            "• Send /report for your weekly summary\n"
            "• Send /dashboard for your personal dashboard\n"
            "• Send /undo to remove your last entry\n"
            "• Send /history to view and delete recent entries\n"
            "• Send /clear to reset all your data\n\n"
            "Let's start tracking! 💰"
        ),
        "keyboard": None,
    }


async def handle_text(sender: str, body: str) -> dict:
    lower = body.lower().strip()
    state = get_pending_state(sender)

    if state and state["type"] == "awaiting_confirmation":
        return await _handle_text_during_confirmation(sender, lower, state)

    if state and state["type"] == "awaiting_correction":
        return await _handle_correction(sender, body, lower, state)

    if state and state["type"] == "awaiting_text_category":
        return await _handle_text_category_typed(sender, lower, state)

    if lower in ("/start", "start", "hi", "hello", "help"):
        return await handle_start(sender)

    if lower == "/report":
        from app.intelligence.report_builder import get_weekly_summary
        summary = get_weekly_summary(sender)
        return {"text": summary, "keyboard": None}

    if lower == "/dashboard":
        token = hashlib.sha256(sender.encode()).hexdigest()[:16]
        link  = f"https://finbot-api-d5le.onrender.com/dashboard/{token}"
        return {"text": f"📊 Open your dashboard: {link}", "keyboard": None}

    if lower == "/undo":
        return await _handle_undo(sender)

    if lower == "/history":
        return await _handle_history(sender)

    if lower == "/clear":
        return {
            "text": (
                "⚠️ *This will permanently delete ALL your transactions.*\n\n"
                "Are you sure you want to reset your data?"
            ),
            "keyboard": confirm_clear_keyboard(),
        }

    # Expense logging
    match = EXPENSE_PATTERN.match(body.strip())
    if match:
        if match.group(1):
            amount      = float(match.group(1))
            description = match.group(2).strip()
        else:
            amount      = float(match.group(4))
            description = match.group(3).strip()

        if not description:
            description = "expense"

        # Check learned keywords first
        learned = get_learned_category(sender, description)
        if learned:
            emoji  = CATEGORY_EMOJIS.get(learned, "📦")
            txn_id = save_transaction(sender, amount, learned, description, "text", body)
            save_last_txn_id(sender, txn_id)
            return {
                "text": f"✅ Logged ₹{amount:.0f} for *{description}* · {learned.title()} {emoji}\n_/undo to remove_",
                "keyboard": None,
            }

        category = suggest_category_from_text(description)

        if category != "other":
            emoji  = CATEGORY_EMOJIS.get(category, "📦")
            txn_id = save_transaction(sender, amount, category, description, "text", body)
            save_last_txn_id(sender, txn_id)
            return {
                "text": f"✅ Logged ₹{amount:.0f} for *{description}* · {category.title()} {emoji}\n_/undo to remove_",
                "keyboard": None,
            }

        # No match — ask category
        r = get_redis()
        pending = {
            "type": "awaiting_text_category",
            "amount": amount,
            "description": description,
            "raw": body,
        }
        r.setex(f"pending:{sender}", 300, json.dumps(pending))
        return {
            "text": f"₹{amount:.0f} for *{description}*\n\nWhich category?",
            "keyboard": category_keyboard(),
        }

    return {
        "text": (
            "❓ Didn't catch that. Try:\n"
            "• *40 chai* to log an expense\n"
            "• /start for all commands"
        ),
        "keyboard": None,
    }


async def _handle_undo(sender: str) -> dict:
    txn_id = get_last_txn_id(sender)
    if not txn_id:
        return {"text": "Nothing to undo — no recent transaction found.", "keyboard": None}

    db = SessionLocal()
    try:
        txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
        if not txn:
            return {"text": "That transaction no longer exists.", "keyboard": None}

        desc   = txn.description
        amount = txn.amount
        db.delete(txn)
        db.commit()

        # Clear from Redis
        r = get_redis()
        r.delete(f"last_txn:{sender}")
    finally:
        db.close()

    return {
        "text": f"🗑️ Removed last entry: ₹{amount:.0f} {desc}",
        "keyboard": None,
    }


async def _handle_history(sender: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == sender).first()
        if not user:
            return {"text": "No transactions found.", "keyboard": None}

        txns = (
            db.query(Transaction)
            .filter(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(5)
            .all()
        )

        if not txns:
            return {"text": "No transactions found.", "keyboard": None}

        lines = ["*Your last 5 transactions:*\n"]
        txn_list = []
        for i, t in enumerate(txns, 1):
            emoji = CATEGORY_EMOJIS.get(t.category.value, "📦")
            date  = t.created_at.strftime("%d %b") if t.created_at else ""
            lines.append(f"{i}. ₹{t.amount:.0f} {t.description} · {emoji} _{date}_")
            txn_list.append({
                "index": i,
                "id": t.id,
                "amount": t.amount,
                "description": t.description,
            })

        lines.append("\n_Tap to delete an entry:_")
        return {
            "text": "\n".join(lines),
            "keyboard": history_keyboard(txn_list),
        }
    finally:
        db.close()


async def _handle_text_category_typed(sender: str, lower: str, state: dict) -> dict:
    valid = ["food", "travel", "shopping", "health", "bills", "entertainment", "other"]
    if lower in valid:
        return await _save_text_with_category(sender, lower, state)
    return {
        "text": "Please tap one of the category buttons above.",
        "keyboard": category_keyboard(),
    }


async def handle_callback(sender: str, callback_data: str, state: dict) -> dict:
    if callback_data == "confirm_yes":
        return await _confirm_yes(sender, state)
    if callback_data == "confirm_no":
        return await _confirm_no(sender, state)
    if callback_data.startswith("cat_"):
        category = callback_data.replace("cat_", "")
        if state and state.get("type") == "awaiting_text_category":
            return await _save_text_with_category(sender, category, state)
        return await _save_with_category(sender, category, state)
    if callback_data.startswith("del_"):
        txn_id = int(callback_data.replace("del_", ""))
        return await _delete_transaction(sender, txn_id)
    if callback_data == "clear_confirm":
        return await _clear_user_data(sender)
    if callback_data == "clear_cancel":
        return {"text": "✅ Cancelled. Your data is safe.", "keyboard": None}
    return {"text": "❓ Unknown action.", "keyboard": None}


async def _delete_transaction(sender: str, txn_id: int) -> dict:
    db = SessionLocal()
    try:
        txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
        if not txn:
            return {"text": "Transaction not found.", "keyboard": None}
        desc   = txn.description
        amount = txn.amount
        db.delete(txn)
        db.commit()
    finally:
        db.close()
    return {
        "text": f"🗑️ Deleted: ₹{amount:.0f} {desc}",
        "keyboard": None,
    }


async def _save_text_with_category(sender: str, category: str, state: dict) -> dict:
    clear_pending_state(sender)
    amount      = state["amount"]
    description = state["description"]
    save_learned_keyword(sender, description, category)
    txn_id = save_transaction(sender, amount, category, description, "text", state["raw"])
    save_last_txn_id(sender, txn_id)
    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return {
        "text": (
            f"✅ Logged ₹{amount:.0f} for *{description}* · {category.title()} {emoji}\n\n"
            f"Got it! I'll remember *{description}* as {category.title()} next time.\n_/undo to remove_"
        ),
        "keyboard": None,
    }


async def _handle_text_during_confirmation(sender: str, lower: str, state: dict) -> dict:
    if lower in ("yes", "y"):
        return await _confirm_yes(sender, state)
    if lower in ("no", "n"):
        return await _confirm_no(sender, state)
    emoji = CATEGORY_EMOJIS.get(state["category"], "📦")
    return {
        "text": (
            f"💸 *₹{state['amount']:.0f}* to *{state['merchant_name']}*\n"
            f"Category: {state['category'].title()} {emoji}\n\n"
            f"Is this correct?"
        ),
        "keyboard": yes_no_keyboard(),
    }


async def _confirm_yes(sender: str, state: dict) -> dict:
    clear_pending_state(sender)
    set_merchant(sender, state["upi_id"], state["category"])
    record_appearance(sender, state["upi_id"])
    check_and_promote(sender, state["upi_id"], state["category"])
    txn_id = save_transaction(
        sender, state["amount"], state["category"],
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    save_last_txn_id(sender, txn_id)
    emoji = CATEGORY_EMOJIS.get(state["category"], "📦")
    return {
        "text": (
            f"✅ Logged ₹{state['amount']:.0f} for *{state['merchant_name']}*\n"
            f"Category: {state['category'].title()} {emoji}\n\n"
            f"I'll remember *{state['merchant_name']}* next time!\n_/undo to remove_"
        ),
        "keyboard": None,
    }


async def _confirm_no(sender: str, state: dict) -> dict:
    correction_state = {
        "type": "awaiting_correction",
        "upi_id": state["upi_id"],
        "merchant_name": state["merchant_name"],
        "amount": state["amount"],
        "transaction_type": state["transaction_type"],
        "app_source": state["app_source"],
    }
    r = get_redis()
    r.setex(f"pending:{sender}", 600, json.dumps(correction_state))
    return {
        "text": "Which category should this go to?",
        "keyboard": category_keyboard(),
    }


async def _save_with_category(sender: str, category: str, state: dict) -> dict:
    clear_pending_state(sender)
    set_merchant(sender, state["upi_id"], category)
    record_appearance(sender, state["upi_id"])
    check_and_promote(sender, state["upi_id"], category)
    txn_id = save_transaction(
        sender, state["amount"], category,
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    save_last_txn_id(sender, txn_id)
    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return {
        "text": (
            f"✅ Logged ₹{state['amount']:.0f} for *{state['merchant_name']}*\n"
            f"Category: {category.title()} {emoji}\n\n"
            f"I'll remember *{state['merchant_name']}* as {category.title()} next time!\n_/undo to remove_"
        ),
        "keyboard": None,
    }


async def _handle_correction(sender: str, body: str, lower: str, state: dict) -> dict:
    match = CORRECTION_PATTERN.match(body.strip())
    if not match:
        return {"text": CORRECTION_PROMPT, "keyboard": None}

    amount   = float(match.group(1))
    category = match.group(2).lower()
    clear_pending_state(sender)
    set_merchant(sender, state["upi_id"], category)
    record_appearance(sender, state["upi_id"])
    check_and_promote(sender, state["upi_id"], category)
    txn_id = save_transaction(
        sender, amount, category,
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    save_last_txn_id(sender, txn_id)
    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return {
        "text": (
            f"✅ Logged ₹{amount:.0f} for *{state['merchant_name']}*\n"
            f"Category: {category.title()} {emoji}\n_/undo to remove_"
        ),
        "keyboard": None,
    }


async def _clear_user_data(sender: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == sender).first()
        if user:
            db.query(Transaction).filter(Transaction.user_id == user.id).delete()
            db.commit()
        r = get_redis()
        for key in r.scan_iter(f"merchant:{sender}:*"):
            r.delete(key)
        for key in r.scan_iter(f"perm_merchant:{sender}:*"):
            r.delete(key)
        for key in r.scan_iter(f"keyword:{sender}:*"):
            r.delete(key)
        r.delete(f"last_txn:{sender}")
        clear_pending_state(sender)
    finally:
        db.close()
    return {
        "text": "✅ All your transactions have been cleared. Fresh start! 💪",
        "keyboard": None,
    }