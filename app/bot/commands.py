import re
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum

EXPENSE_PATTERN = re.compile(r"^₹?(\d+(?:\.\d{1,2})?)\s*(.*)?$")


def get_or_create_user(db: Session, phone_number: str) -> User:
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


async def handle_text_command(sender: str, body: str) -> str:
    lower = body.lower().strip()

    if lower in ("help", "hi", "hello", "start"):
        return (
            "👋 Welcome to *FinBot*!\n\n"
            "Here's what you can do:\n"
            "• Send *40 chai* to log ₹40 expense\n"
            "• Forward a *UPI screenshot* to auto-log it\n"
            "• Send *report* to get your dashboard link\n\n"
            "Let's start tracking! 💰"
        )

    if lower == "report":
        return "📊 Dashboard coming in Phase 5!"

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
                category=CategoryEnum.other,
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
            f"Category: Other _(categories coming in Phase 3)_"
        )

    return (
        "❓ Didn't catch that. Try:\n"
        "• *40 chai* to log an expense\n"
        "• *help* to see all commands"
    )


async def handle_image_command(sender: str, media_url: str) -> str:
    """
    Queues OCR task in Celery and returns instant acknowledgement.
    Actual reply is sent by Celery worker when processing is done.
    """
    from app.tasks.image_tasks import process_upi_screenshot
    process_upi_screenshot.delay(sender, media_url)
    return "⏳ Processing your screenshot... I'll reply in a few seconds!"