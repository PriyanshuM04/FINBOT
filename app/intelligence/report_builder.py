"""
Builds weekly and monthly spending summaries from the DB.
Used by both the scheduled Sunday report and manual 'report' command.
"""
from datetime import datetime, timedelta
from sqlalchemy import func
from app.db.database import SessionLocal
from app.db.models import Transaction, User, CategoryEnum

CATEGORY_EMOJIS = {
    "food": "🍔", "travel": "🚗", "shopping": "🛍️",
    "health": "💊", "bills": "💡", "entertainment": "🎬", "other": "📦"
}


def get_weekly_summary(user_phone: str) -> str:
    """Builds a weekly spending summary for a user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == user_phone).first()
        if not user:
            return "No data found for your account."

        # Last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        transactions = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= week_ago,
        ).all()

        if not transactions:
            return (
                "📊 *Weekly Summary*\n\n"
                "No transactions logged this week.\n"
                "Forward a UPI screenshot to start tracking!"
            )

        total = sum(t.amount for t in transactions)
        count = len(transactions)

        # Category breakdown
        category_totals: dict[str, float] = {}
        for t in transactions:
            cat = t.category.value
            category_totals[cat] = category_totals.get(cat, 0) + t.amount

        # Sort by amount descending
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

        # Top merchant
        merchant_totals: dict[str, float] = {}
        for t in transactions:
            if t.description:
                merchant_totals[t.description] = (
                    merchant_totals.get(t.description, 0) + t.amount
                )
        top_merchant = max(merchant_totals, key=merchant_totals.get) if merchant_totals else None
        top_merchant_amount = merchant_totals[top_merchant] if top_merchant else 0

        # Build message
        lines = [
            f"📊 *Weekly Summary*",
            f"_{datetime.now().strftime('%d %b %Y')}_\n",
            f"💰 Total spent: *₹{total:.0f}*",
            f"🧾 Transactions: *{count}*\n",
            f"*Category Breakdown:*",
        ]

        for cat, amount in sorted_cats:
            emoji = CATEGORY_EMOJIS.get(cat, "📦")
            pct = (amount / total) * 100
            lines.append(f"{emoji} {cat}: ₹{amount:.0f} ({pct:.0f}%)")

        if top_merchant:
            lines.append(f"\n🏆 Top spend: *{top_merchant}* — ₹{top_merchant_amount:.0f}")

        lines.append("\n_Forward UPI screenshots to keep tracking!_")

        return "\n".join(lines)

    finally:
        db.close()


def get_monthly_summary(user_phone: str) -> str:
    """Builds a monthly spending summary."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == user_phone).first()
        if not user:
            return "No data found for your account."

        # Current month
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        transactions = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= month_start,
        ).all()

        if not transactions:
            return (
                f"📅 *{now.strftime('%B')} Summary*\n\n"
                "No transactions logged this month yet."
            )

        total = sum(t.amount for t in transactions)
        count = len(transactions)

        category_totals: dict[str, float] = {}
        for t in transactions:
            cat = t.category.value
            category_totals[cat] = category_totals.get(cat, 0) + t.amount

        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

        lines = [
            f"📅 *{now.strftime('%B %Y')} Summary*\n",
            f"💰 Total spent: *₹{total:.0f}*",
            f"🧾 Transactions: *{count}*\n",
            f"*Category Breakdown:*",
        ]

        for cat, amount in sorted_cats:
            emoji = CATEGORY_EMOJIS.get(cat, "📦")
            pct = (amount / total) * 100
            lines.append(f"{emoji} {cat}: ₹{amount:.0f} ({pct:.0f}%)")

        lines.append("\n_Reply *report* anytime for your dashboard link._")

        return "\n".join(lines)

    finally:
        db.close()