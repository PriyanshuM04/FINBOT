import re
import json
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum
from app.cache.merchant_cache import set_merchant, record_appearance
from app.cache.promoter import check_and_promote
from app.cache.redis_client import get_redis
from app.bot.conversation import (
    get_pending_state, clear_pending_state, set_pending_category
)

EXPENSE_PATTERN = re.compile(r"^₹?(\d+(?:\.\d{1,2})?)\s*(.*)?$")

CORRECTION_PATTERN = re.compile(
    r"^₹?(\d+(?:\.\d{1,2})?)\s+(food|travel|shopping|health|bills|entertainment|other)$",
    re.IGNORECASE
)

CATEGORY_MAP = {
    "1": "food", "2": "travel", "3": "shopping",
    "4": "health", "5": "bills", "6": "entertainment", "7": "other"
}

CATEGORY_EMOJIS = {
    "food": "🍔", "travel": "🚗", "shopping": "🛍️",
    "health": "💊", "bills": "💡", "entertainment": "🎬", "other": "📦"
}

CATEGORY_MENU = (
    "Which category is correct?\n\n"
    "1 - Food 🍔\n"
    "2 - Travel 🚗\n"
    "3 - Shopping 🛍️\n"
    "4 - Health 💊\n"
    "5 - Bills 💡\n"
    "6 - Entertainment 🎬\n"
    "7 - Other 📦"
)

CORRECTION_PROMPT = (
    "❌ Please type the correct amount and category:\n\n"
    "*Example: 100 food* or *192 travel*\n\n"
    "Categories: food, travel, shopping,\n"
    "health, bills, entertainment, other"
)


def get_or_create_user(db: Session, phone_number: str) -> User:
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


async def handle_text_command(sender: str, body: str) -> str:
    lower = body.lower().strip()

    # ── Check pending state first ─────────────────────────────────
    state = get_pending_state(sender)

    if state and state["type"] == "awaiting_confirmation":
        return await _handle_confirmation(sender, body, lower, state)

    if state and state["type"] == "awaiting_correction":
        return await _handle_correction(sender, body, lower, state)

    # ── Normal commands ───────────────────────────────────────────
    if lower in ("help", "hi", "hello", "start"):
        return (
            "👋 Welcome to *FinBot*!\n\n"
            "• Send *40 chai* to log an expense\n"
            "• Forward a *UPI screenshot* to auto-log\n"
            "• Send *report* for your weekly summary\n\n"
            "Let's start tracking! 💰"
        )

    if lower == "report":
        from app.intelligence.report_builder import get_weekly_summary
        return get_weekly_summary(sender)

    match = EXPENSE_PATTERN.match(body.strip())
    if match:
        amount = float(match.group(1))
        description = match.group(2).strip() if match.group(2) else "expense"
        save_transaction(sender, amount, "other", description, "text", body)
        return f"✅ Logged ₹{amount:.0f} for *{description}*"

    return (
        "❓ Didn't catch that. Try:\n"
        "• *40 chai* to log an expense\n"
        "• *help* for all commands"
    )


async def _handle_confirmation(sender: str, body: str,
                                lower: str, state: dict) -> str:
    if lower in ("yes", "y", "correct", "ok", "okay"):
        clear_pending_state(sender)

        set_merchant(sender, state["upi_id"], state["category"])
        record_appearance(sender, state["upi_id"])
        check_and_promote(sender, state["upi_id"], state["category"])

        save_transaction(
            sender,
            state["amount"],
            state["category"],
            state["merchant_name"],
            f"upi_{state['app_source']}",
            state["upi_id"],
        )

        emoji = CATEGORY_EMOJIS.get(state["category"], "📦")
        return (
            f"✅ Logged ₹{state['amount']:.0f} for *{state['merchant_name']}*\n"
            f"Category: {state['category'].title()} {emoji}\n\n"
            f"🧠 I'll remember *{state['merchant_name']}* next time!"
        )

    if lower in ("no", "n", "wrong"):
        correction_state = {
            "type": "awaiting_correction",
            "upi_id": state["upi_id"],
            "merchant_name": state["merchant_name"],
            "transaction_type": state["transaction_type"],
            "app_source": state["app_source"],
        }
        r = get_redis()
        r.setex(f"pending:{sender}", 600, json.dumps(correction_state))
        return CORRECTION_PROMPT

    return (
        f"Please reply *yes* to save or *no* to correct.\n\n"
        f"💸 ₹{state['amount']:.0f} to *{state['merchant_name']}* "
        f"— Category: {state['category'].title()}"
    )


async def _handle_correction(sender: str, body: str,
                              lower: str, state: dict) -> str:
    match = CORRECTION_PATTERN.match(body.strip())

    if not match:
        return CORRECTION_PROMPT

    amount   = float(match.group(1))
    category = match.group(2).lower()

    clear_pending_state(sender)

    set_merchant(sender, state["upi_id"], category)
    record_appearance(sender, state["upi_id"])
    check_and_promote(sender, state["upi_id"], category)

    save_transaction(
        sender,
        amount,
        category,
        state["merchant_name"],
        f"upi_{state['app_source']}",
        state["upi_id"],
    )

    emoji = CATEGORY_EMOJIS.get(category, "📦")
    return (
        f"✅ Logged ₹{amount:.0f} for *{state['merchant_name']}*\n"
        f"Category: {category.title()} {emoji}\n\n"
        f"🧠 I'll remember *{state['merchant_name']}* as {category.title()} next time!"
    )


async def handle_image_command(sender: str, media_url: str) -> str:
    from app.tasks.image_tasks import process_upi_screenshot
    process_upi_screenshot.delay(sender, media_url)
    return "⏳ Processing your screenshot..."