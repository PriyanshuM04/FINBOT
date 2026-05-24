"""
Scheduled Celery tasks for automatic reports.
Sunday weekly summary is sent to all active users.
"""
from celery.schedules import crontab
from app.tasks.celery_app import celery
from app.db.database import SessionLocal
from app.db.models import User
from app.intelligence.report_builder import get_weekly_summary
from app.config import settings
from twilio.rest import Client


def send_whatsapp(to: str, message: str):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=to,
        body=message,
    )


@celery.task(name="send_weekly_summaries")
def send_weekly_summaries():
    """
    Sends weekly summary to all active users.
    Scheduled every Sunday at 9:00 AM IST.
    """
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        for user in users:
            try:
                summary = get_weekly_summary(user.phone_number)
                send_whatsapp(user.phone_number, summary)
                print(f"✅ Weekly summary sent to {user.phone_number}")
            except Exception as e:
                print(f"❌ Failed to send summary to {user.phone_number}: {e}")
    finally:
        db.close()


@celery.task(name="send_weekly_summary_single")
def send_weekly_summary_single(phone_number: str):
    """Send weekly summary to a single user — used for manual trigger."""
    summary = get_weekly_summary(phone_number)
    send_whatsapp(phone_number, summary)


# ── Celery Beat Schedule ──────────────────────────────────────────
celery.conf.beat_schedule = {
    "weekly-summary-sunday": {
        "task": "send_weekly_summaries",
        "schedule": crontab(hour=9, minute=0, day_of_week=0),  # Sunday 9AM
    },
}