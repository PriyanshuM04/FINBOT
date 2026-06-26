"""
Telegram command handlers — same logic as WhatsApp commands
but uses Telegram's native inline keyboards.
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
from app.bot.telegram_keyboards import yes_no_keyboard, category_keyboard
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
                     description: str, source: str, raw_input: str):
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
    finally:
        db.close()


async def handle_start(sender: str) -> dict:
    return {
        "text": (
            "👋 Welcome to *FinBot*!\n\n"
            "• Send *40 chai* or *chai 40* to log an expense\n"
            "• Forward a *UPI screenshot* to auto-log\n"
            "• Send /report for your weekly summary\n"
            "• Send /dashboard for your personal dashboard\n\n"
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

    if lower in ("/start", "start", "hi", "hello", "help"):
        return await handle_start(sender)

    if lower == "/report":
        from app.intelligence.report_builder import get_weekly_summary
        summary = get_weekly_summary(sender)
        return {"text": summary, "keyboard": None}

    if lower == "/dashboard":
        token = hashlib.sha256(sender.encode()).hexdigest()[:16]
        link = f"https://finbot-api-d5le.onrender.com/dashboard/{token}"
        return {"text": f"📊 Open your dashboard: {link}", "keyboard": None}

    match = EXPENSE_PATTERN.match(body.strip())
    if match:
        if match.group(1):
            amount = float(match.group(1))
            description = match.group(2).strip()
        else:
            amount = float(match.group(4))
            description = match.group(3).strip()

        if not description:
            description = "expense"

        category = suggest_category_from_text(description)
        emoji = CATEGORY_EMOJIS.get(category, "📦")
        save_transaction(sender, amount, category, description, "text", body)
        return {
            "text": f"✅ Logged ₹{amount:.0f} for *{description}* · {category.title()} {emoji}",
            "keyboard": None,
        }

    return {
        "text": (
            "❓ Didn't catch that. Try:\n"
            "• *40 chai* to log an expense\n"
            "• /start for all commands"
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


async def handle_callback(sender: str, callback_data: str, state: dict) -> dict:
    if callback_data == "confirm_yes":
        return await _confirm_yes(sender, state)
    if callback_data == "confirm_no":
        return await _confirm_no(sender, state)
    if callback_data.startswith("cat_"):
        category = callback_data.replace("cat_", "")
        return await _save_with_category(sender, category, state)
    return {"text": "❓ Unknown action.", "keyboard": None}


async def _confirm_yes(sender: str, state: dict) -> dict:
    clear_pending_state(sender)
    set_merchant(sender, state["upi_id"], state["category"])
    record_appearance(sender, state["upi_id"])
    check_and_promote(sender, state["upi_id"], state["category"])
    save_transaction(
        sender, state["amount"], state["category"],
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    emoji = CATEGORY_EMOJIS.get(state["category"], "📦")
    return {
        "text": (
            f"✅ Logged ₹{state['amount']:.0f} for *{state['merchant_name']}*\n"
            f"Category: {state['category'].title()} {emoji}\n\n"
            f"I'll remember *{state['merchant_name']}* next time!"
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
    save_transaction(
        sender, state["amount"], category,
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return {
        "text": (
            f"✅ Logged ₹{state['amount']:.0f} for *{state['merchant_name']}*\n"
            f"Category: {category.title()} {emoji}\n\n"
            f"I'll remember *{state['merchant_name']}* as {category.title()} next time!"
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
    save_transaction(
        sender, amount, category,
        state["merchant_name"], f"upi_{state['app_source']}", state["upi_id"],
    )
    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return {
        "text": (
            f"✅ Logged ₹{amount:.0f} for *{state['merchant_name']}*\n"
            f"Category: {category.title()} {emoji}"
        ),
        "keyboard": None,
    }