from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from app.db.database import engine, Base
from app.bot.handler import handle_message
import app.db.models  # noqa: F401
from app.dashboard.routes import router as dashboard_router
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def root():
    return {"status": "FinBot is running"}


@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
):
    sender = From
    body = Body.strip()

    # Image message — acknowledge immediately, process in background
    if NumMedia > 0 and MediaUrl0:
        from app.tasks.image_tasks import process_upi_screenshot_bg
        background_tasks.add_task(process_upi_screenshot_bg, sender, MediaUrl0)
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>⏳ Processing your screenshot...</Message>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")

    # Text message — handle normally
    reply = await handle_message(
        sender=sender,
        body=body,
        num_media=NumMedia,
        media_url=MediaUrl0,
        media_type=MediaContentType0,
    )

    if reply:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")

    return PlainTextResponse(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml"
    )