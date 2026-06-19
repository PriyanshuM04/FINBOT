import httpx
from app.ocr.preprocessor import preprocess_image_bytes
from app.ocr.extractor import extract_text
from app.parsers.upi.router import parse_upi_screenshot
from app.db.database import SessionLocal
from app.db.models import User, Transaction, CategoryEnum
from app.config import settings
from app.cache.merchant_cache import get_merchant, record_appearance
from app.cache.promoter import get_permanent_merchant, check_and_promote
from app.bot.conversation import set_pending_confirmation
from twilio.rest import Client

CATEGORY_KEYWORDS = {
    "food":          ["swiggy", "zomato", "domino", "pizza", "food", "cafe",
                      "restaurant", "chai", "biryani", "hotel", "dhaba",
                      "bakery", "juice", "snack", "eat", "lunch", "dinner"],
    "travel":        ["irctc", "uber", "ola", "rapido", "redbus", "petrol",
                      "fuel", "cab", "auto", "parking", "railway", "bus",
                      "metro", "flight", "indigo", "spicejet"],
    "shopping":      ["amazon", "flipkart", "myntra", "ajio", "meesho",
                      "mall", "store", "mart", "shop", "bazar", "market"],
    "health":        ["pharmacy", "medical", "chemist", "hospital", "clinic",
                      "doctor", "lab", "apollo", "medplus", "netmeds",
                      "1mg", "medicine", "pharma"],
    "bills":         ["electricity", "jio", "airtel", "bsnl", "recharge",
                      "netflix", "spotify", "prime", "hotstar", "disney",
                      "water", "gas", "rent", "broadband", "wifi"],
    "entertainment": ["bookmyshow", "pvr", "inox", "cinema", "movie",
                      "game", "sport", "ticket"],
}

CATEGORY_EMOJIS = {
    "food": "🍔", "travel": "🚗", "shopping": "🛍️",
    "health": "💊", "bills": "💡", "entertainment": "🎬", "other": "📦"
}


def send_whatsapp(to: str, message: str):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=to,
        body=message,
    )


def get_or_create_user(db, phone_number: str):
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def save_transaction(sender: str, amount: float, category: str,
                     description: str, app_source: str, raw_texts: list):
    db = SessionLocal()
    try:
        user = get_or_create_user(db, sender)
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            category=CategoryEnum(category),
            description=description,
            source=f"upi_{app_source}",
            raw_input=str(raw_texts[:3]),
        )
        db.add(transaction)
        db.commit()
    finally:
        db.close()


def suggest_category(merchant_name: str, upi_id: str) -> str:
    text = f"{merchant_name} {upi_id}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "other"


def process_upi_screenshot_bg(sender: str, media_url: str):
    """
    Runs as FastAPI BackgroundTask — no Celery needed.
    Sends result back via WhatsApp after processing.
    """
    try:
        response = httpx.get(
            media_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()

        processed = preprocess_image_bytes(response.content)
        texts = extract_text(processed)

        if not texts:
            send_whatsapp(sender,
                "🔍 Couldn't read any text from this image.\n"
                "Make sure the screenshot is clear and try again.")
            return

        result = parse_upi_screenshot(texts)

        if result is None:
            send_whatsapp(sender,
                "🤔 Couldn't recognise this as a UPI screenshot.\n"
                "Supported: GPay, PhonePe, Paytm, Amazon Pay\n\n"
                "Or type manually: *150 groceries*")
            return

        if result.amount == 0:
            send_whatsapp(sender,
                f"📸 Detected *{result.app_source.upper()}* transaction "
                f"but couldn't read the amount.\n\n"
                f"Please type manually: *150 {result.merchant_name or 'expense'}*")
            return

        upi_id    = result.upi_id or result.merchant_name or result.app_source
        merchant  = result.merchant_name or result.upi_id or "Unknown merchant"
        txn_emoji = "💸" if result.transaction_type == "debit" else "💰"
        direction = "paid to" if result.transaction_type == "debit" else "received from"

        known = get_permanent_merchant(sender, upi_id)
        if not known:
            known = get_merchant(sender, upi_id)

        suggested = known["category"] if known else suggest_category(merchant, upi_id)
        emoji     = CATEGORY_EMOJIS.get(suggested, "📦")

        set_pending_confirmation(
            sender,
            upi_id=upi_id,
            merchant_name=merchant,
            amount=result.amount,
            category=suggested,
            transaction_type=result.transaction_type,
            app_source=result.app_source,
        )

        known_tag = " _(remembered)_" if known else ""
        send_whatsapp(sender,
            f"{txn_emoji} *₹{result.amount:.0f}* {direction} *{merchant}*\n"
            f"App: {result.app_source.upper()}\n"
            f"Category: {suggested.title()} {emoji}{known_tag}\n\n"
            f"Reply *yes* to save  |  Reply *no* to correct")

    except Exception as e:
        send_whatsapp(sender,
            "⚠️ Something went wrong processing your screenshot.\n"
            "Please try again or type manually: *150 groceries*")
        print(f"OCR error for {sender}: {e}")