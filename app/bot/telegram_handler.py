"""
Telegram webhook handler.
Registered at /telegram/webhook in main.py.
"""
import json
from fastapi import Request, BackgroundTasks
from telegram import Update, Bot, InlineKeyboardMarkup
from telegram.constants import ParseMode
from app.config import settings
from app.bot.conversation import get_pending_state, set_pending_confirmation
from app.bot.telegram_commands import handle_start, handle_text, handle_callback

# bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
def get_bot() -> Bot:
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


def get_telegram_sender(update_data: dict) -> str:
    """Extract a unique sender ID from Telegram update."""
    if "message" in update_data:
        user_id = update_data["message"]["from"]["id"]
    elif "callback_query" in update_data:
        user_id = update_data["callback_query"]["from"]["id"]
    else:
        return ""
    return f"telegram:{user_id}"


async def send_telegram_message(chat_id: int, text: str,
                                 keyboard=None):
    await get_bot().send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )


async def process_telegram_update(update_data: dict):
    """Main router for all Telegram updates."""
    update = Update.de_json(update_data, get_bot())

    # Text message
    if update.message and update.message.text:
        chat_id = update.message.chat_id
        sender  = get_telegram_sender(update_data)
        text    = update.message.text.strip()

        if text in ("/start", "start"):
            result = await handle_start(sender)
        else:
            result = await handle_text(sender, text)

        await send_telegram_message(chat_id, result["text"], result.get("keyboard"))

    # Photo message (UPI screenshot)
    elif update.message and update.message.photo:
        chat_id = update.message.chat_id
        sender  = get_telegram_sender(update_data)

        await get_bot().send_message(chat_id=chat_id, text="⏳ Processing your screenshot...")

        # Get highest resolution photo
        photo = update.message.photo[-1]
        tg_file = await get_bot().get_file(photo.file_id)
        file_url = tg_file.file_path  # Telegram CDN URL, no auth needed

        # Process in background
        from app.tasks.image_tasks import process_upi_screenshot_bg
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            lambda: process_upi_screenshot_bg_telegram(sender, file_url, chat_id)
        )

    # Inline button tap
    elif update.callback_query:
        query       = update.callback_query
        chat_id     = query.message.chat_id
        sender      = get_telegram_sender(update_data)
        callback    = query.data

        await query.answer()  # dismiss the loading spinner on button

        state = get_pending_state(sender)
        if not state:
            await get_bot().send_message(chat_id=chat_id, text="Session expired\\. Please send the screenshot again\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        result = await handle_callback(sender, callback, state)
        await send_telegram_message(chat_id, result["text"], result.get("keyboard"))


def process_upi_screenshot_bg_telegram(sender: str, file_url: str, chat_id: int):
    """
    Wrapper around image_tasks that sends result to Telegram instead of WhatsApp.
    """
    import httpx
    from app.ocr.extractor_ocrspace import extract_text_from_url
    from app.parsers.upi.router import parse_upi_screenshot
    from app.cache.merchant_cache import get_merchant
    from app.cache.promoter import get_permanent_merchant
    from app.bot.telegram_commands import suggest_category_from_text, CATEGORY_EMOJIS
    from app.bot.telegram_keyboards import yes_no_keyboard
    from app.bot.conversation import set_pending_confirmation
    import asyncio

    async def _send(text, keyboard=None):
        await get_bot().send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )

    async def _run():
        try:
            # Download from Telegram CDN (no auth needed)
            response = httpx.get(file_url, timeout=30.0)
            response.raise_for_status()
            image_bytes = response.content

            # OCR via OCR.space
            import base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            base64_image = f"data:image/jpeg;base64,{b64}"

            ocr_response = httpx.post(
                "https://api.ocr.space/parse/image",
                data={
                    "base64Image": base64_image,
                    "language": "eng",
                    "OCREngine": 2,
                    "isOverlayRequired": False,
                    "detectOrientation": True,
                    "scale": True,
                },
                headers={"apikey": settings.OCR_SPACE_API_KEY},
                timeout=30.0,
            )
            ocr_response.raise_for_status()
            ocr_result = ocr_response.json()

            texts = []
            for parsed in ocr_result.get("ParsedResults", []):
                raw = parsed.get("ParsedText", "")
                texts.extend([l.strip() for l in raw.split("\n") if l.strip()])

            if not texts:
                await _send("🔍 Couldn't read text from this image\\. Try a clearer screenshot\\.")
                return

            result = parse_upi_screenshot(texts)

            if result is None:
                await _send("🤔 Couldn't recognise this as a UPI screenshot\\.\nOr type manually: *150 groceries*")
                return

            if result.amount == 0:
                await _send(f"📸 Detected *{result.app_source.upper()}* but couldn't read amount\\.\nType manually: *150 expense*")
                return

            upi_id    = result.upi_id or result.merchant_name or result.app_source
            merchant  = result.merchant_name or result.upi_id or "Unknown"
            txn_emoji = "💸" if result.transaction_type == "debit" else "💰"
            direction = "paid to" if result.transaction_type == "debit" else "received from"

            known = get_permanent_merchant(sender, upi_id)
            if not known:
                known = get_merchant(sender, upi_id)

            suggested = known["category"] if known else suggest_category_from_text(f"{merchant} {upi_id}")
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

            known_tag = " _\\(remembered\\)_" if known else ""
            await _send(
                f"{txn_emoji} *₹{result.amount:.0f}* {direction} *{merchant}*\n"
                f"App: {result.app_source.upper()}\n"
                f"Category: {suggested.title()} {emoji}{known_tag}\n\n"
                f"Is this correct?",
                keyboard=yes_no_keyboard(),
            )

        except Exception as e:
            await _send("⚠️ Something went wrong\\. Try again or type manually: *150 groceries*")
            print(f"Telegram OCR error: {e}")

    asyncio.run(_run())