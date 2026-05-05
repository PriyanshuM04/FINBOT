from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from app.db.database import engine, Base
from app.bot.handler import handle_message
import app.db.models  # noqa: F401 — ensures models are registered before create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates all tables on startup if they don't exist
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")
    yield
    print("👋 Shutting down FinBot")


app = FastAPI(
    title="FinBot",
    description="Personal Finance Intelligence via WhatsApp",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"status": "FinBot is running"}


@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),       # sender's WhatsApp number e.g. whatsapp:+919876543210
    Body: str = Form(default=""),  # text message body
    NumMedia: int = Form(default=0),  # number of media attachments
    MediaUrl0: str = Form(default=None),   # first media URL if any
    MediaContentType0: str = Form(default=None),  # media MIME type
):
    """
    Twilio calls this endpoint every time a WhatsApp message arrives.
    Returns TwiML — empty string means no immediate reply (bot replies async).
    """
    reply = await handle_message(
        sender=From,
        body=Body.strip(),
        num_media=NumMedia,
        media_url=MediaUrl0,
        media_type=MediaContentType0,
    )

    # Twilio expects TwiML — plain text reply wrapped in Message tag
    if reply:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")

    # No reply — return empty TwiML
    return PlainTextResponse(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml"
    )