import re
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum


# Simple pattern: optional currency symbol, amount, then description
# Matches: "40 chai", "150 auto", "₹200 groceries", "10"
EXPENSE_PATTERN = re.compile(r"^₹?(\d+(?:\.\d{1,2})?)\s*(.*)?$")


def get_or_create_user(db: Session, phone_number: str) -> User:
    """Fetch existing user or create a new one."""
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


async def handle_text_command(sender: str, body: str) -> str:
    """
    Handles all incoming text messages.
    Supported:
      - "40 chai"        → logs ₹40, description "chai"
      - "report"         → placeholder for now
      - "help"           → shows available commands
      - anything else    → unknown command message
    """

    lower = body.lower().strip()

    # Help command
    if lower in ("help", "hi", "hello", "start"):
        return (
            "👋 Welcome to *FinBot*!\n\n"
            "Here's what you can do:\n"
            "• Send *40 chai* to log ₹40 expense\n"
            "• Send *150 auto* to log ₹150 expense\n"
            "• Send *report* to get your dashboard link\n"
            "• Forward a UPI screenshot to auto-log it _(coming soon)_\n\n"
            "Let's start tracking! 💰"
        )

    # Report command
    if lower == "report":
        return "📊 Dashboard coming in Phase 5! For now, keep logging your expenses."

    # Expense pattern — "40 chai", "150 auto", "₹200 groceries"
    match = EXPENSE_PATTERN.match(body.strip())
    if match:
        amount = float(match.group(1))
        description = match.group(2).strip() if match.group(2) else "expense"

        db: Session = SessionLocal()
        try:
            user = get_or_create_user(db, sender)
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                category=CategoryEnum.other,   # default — categorization in Phase 3
                description=description,
                source="text",
                raw_input=body,
            )
            db.add(transaction)
            db.commit()
        finally:
            db.close()

        return (
            f"✅ Logged ₹{amount:.0f} for *{description}*\n"
            f"Category: Other _(you can set categories in Phase 3)_"
        )

    return (
        "❓ Didn't catch that. Try:\n"
        "• *40 chai* to log an expense\n"
        "• *help* to see all commands"
    )