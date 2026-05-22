import re
import tempfile
import os
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum
from app.utils.image_upload import download_twilio_image
from app.ocr.preprocessor import preprocess_image_bytes
from app.ocr.extractor import extract_text
from app.parsers.upi.router import parse_upi_screenshot

EXPENSE_PATTERN = re.compile(r"^₹?(\d+(?:\.\d{1,2})?)\s*(.*)?$")

# Maps app_source to category default
APP_CATEGORY_DEFAULTS = {
    "gpay":      CategoryEnum.other,
    "phonepe":   CategoryEnum.other,
    "paytm":     CategoryEnum.other,
    "amazonpay": CategoryEnum.shopping,
}


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
    Downloads image from Twilio, runs OCR, parses UPI transaction,
    saves to DB, and returns a confirmation message.
    """
    try:
        # Step 1 — Download image from Twilio
        image_bytes = await download_twilio_image(media_url)

        # Step 2 — Preprocess and OCR
        processed = preprocess_image_bytes(image_bytes)
        texts = extract_text(processed)

        if not texts:
            return (
                "🔍 Couldn't read any text from this image.\n"
                "Make sure the screenshot is clear and try again."
            )

        # Step 3 — Parse UPI transaction
        result = parse_upi_screenshot(texts)

        if result is None:
            return (
                "🤔 Couldn't recognise this as a UPI screenshot.\n"
                "Supported apps: GPay, PhonePe, Paytm, Amazon Pay\n\n"
                "Or type manually: *150 groceries*"
            )

        # Step 4 — Handle zero/missing amount
        if result.amount == 0:
            return (
                f"📸 Detected a *{result.app_source.upper()}* transaction "
                f"but couldn't read the amount clearly.\n\n"
                f"Please type the amount manually:\n"
                f"*{int(result.amount or 0)} {result.merchant_name or 'expense'}*"
            )

        # Step 5 — Save to DB
        category = APP_CATEGORY_DEFAULTS.get(result.app_source, CategoryEnum.other)

        db: Session = SessionLocal()
        try:
            user = get_or_create_user(db, sender)
            transaction = Transaction(
                user_id=user.id,
                amount=result.amount,
                category=category,
                description=result.merchant_name or result.upi_id or result.app_source,
                source=f"upi_{result.app_source}",
                raw_input=str(result.raw_texts[:3]),
            )
            db.add(transaction)
            db.commit()
        finally:
            db.close()

        # Step 6 — Build confirmation reply
        txn_type_emoji = "💸" if result.transaction_type == "debit" else "💰"
        merchant_display = result.merchant_name or result.upi_id or "Unknown merchant"

        reply = (
            f"{txn_type_emoji} *₹{result.amount:.0f}* "
            f"{'paid to' if result.transaction_type == 'debit' else 'received from'} "
            f"*{merchant_display}*\n"
            f"App: {result.app_source.upper()}\n"
            f"Category: {category.value}\n\n"
            f"✅ Logged! _(Categories auto-assigned in Phase 3)_"
        )

        return reply

    except Exception as e:
        return (
            f"⚠️ Something went wrong processing your screenshot.\n"
            f"Error: {str(e)[:100]}\n\n"
            f"Please try again or type manually: *150 groceries*"
        )