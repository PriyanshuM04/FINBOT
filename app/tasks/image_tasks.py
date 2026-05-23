from app.tasks.celery_app import celery
from app.ocr.preprocessor import preprocess_image_bytes
from app.ocr.extractor import extract_text
from app.parsers.upi.router import parse_upi_screenshot
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum
from app.config import settings
from twilio.rest import Client


APP_CATEGORY_DEFAULTS = {
    "gpay":      CategoryEnum.other,
    "phonepe":   CategoryEnum.other,
    "paytm":     CategoryEnum.other,
    "amazonpay": CategoryEnum.shopping,
}


def send_whatsapp_reply(to: str, message: str):
    """Send a WhatsApp message via Twilio API directly."""
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=to,
        body=message,
    )


def get_or_create_user(db, phone_number: str):
    from app.db.models import User
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@celery.task(name="process_upi_screenshot")
def process_upi_screenshot(sender: str, media_url: str):
    """
    Background task — runs OCR and parses UPI screenshot.
    Sends WhatsApp reply directly via Twilio API when done.
    """
    import httpx
    import asyncio

    try:
        # Download image synchronously for Celery
        response = httpx.get(
            media_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()
        image_bytes = response.content

        # OCR
        processed = preprocess_image_bytes(image_bytes)
        texts = extract_text(processed)

        if not texts:
            send_whatsapp_reply(
                sender,
                "🔍 Couldn't read any text from this image.\n"
                "Make sure the screenshot is clear and try again."
            )
            return

        # Parse
        result = parse_upi_screenshot(texts)

        if result is None:
            send_whatsapp_reply(
                sender,
                "🤔 Couldn't recognise this as a UPI screenshot.\n"
                "Supported: GPay, PhonePe, Paytm, Amazon Pay\n\n"
                "Or type manually: *150 groceries*"
            )
            return

        # Handle zero amount
        if result.amount == 0:
            send_whatsapp_reply(
                sender,
                f"📸 Detected *{result.app_source.upper()}* transaction "
                f"but couldn't read the amount clearly.\n\n"
                f"Please type it manually:\n"
                f"*amount {result.merchant_name or 'expense'}*"
            )
            return

        # Save to DB
        category = APP_CATEGORY_DEFAULTS.get(result.app_source, CategoryEnum.other)
        db = SessionLocal()
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

        # Send confirmation
        txn_emoji = "💸" if result.transaction_type == "debit" else "💰"
        direction = "paid to" if result.transaction_type == "debit" else "received from"
        merchant = result.merchant_name or result.upi_id or "Unknown"

        send_whatsapp_reply(
            sender,
            f"{txn_emoji} *₹{result.amount:.0f}* {direction} *{merchant}*\n"
            f"App: {result.app_source.upper()}\n"
            f"Category: {category.value}\n\n"
            f"✅ Logged! _(Categories auto-assigned in Phase 3)_"
        )

    except Exception as e:
        send_whatsapp_reply(
            sender,
            f"⚠️ Something went wrong processing your screenshot.\n"
            f"Please try again or type manually: *150 groceries*"
        )
        raise  # Re-raise so Celery logs it