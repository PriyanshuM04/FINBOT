from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from app.db.database import SessionLocal
from app.db.models import User, Transaction
from datetime import datetime, timedelta
import hashlib
import os

router = APIRouter()


def get_user_by_token(token: str) -> User | None:
    """Derive user from token — SHA256 of phone number."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            expected = hashlib.sha256(user.phone_number.encode()).hexdigest()[:16]
            if expected == token:
                return user
        return None
    finally:
        db.close()


@router.get("/dashboard/{token}", response_class=HTMLResponse)
def dashboard_page(token: str):
    """Serves the dashboard HTML page."""
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)


@router.get("/api/dashboard/{token}/summary")
def dashboard_summary(token: str):
    """Returns all dashboard data as JSON."""
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")

    db = SessionLocal()
    try:
        now = datetime.now()
        week_ago   = now - timedelta(days=7)
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        three_months_ago = now - timedelta(days=90)

        # All transactions this month
        month_txns = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= month_start,
        ).order_by(Transaction.created_at.desc()).all()

        # All transactions last 3 months for trend
        trend_txns = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.created_at >= three_months_ago,
        ).all()

        # Category breakdown this month
        category_totals = {}
        for t in month_txns:
            cat = t.category.value
            category_totals[cat] = category_totals.get(cat, 0) + t.amount

        # Recent transactions (last 10)
        recent = []
        for t in month_txns[:5]:
            recent.append({
                "id": t.id,
                "amount": t.amount,
                "category": t.category.value,
                "description": t.description or "Unknown",
                "source": t.source,
                "date": t.created_at.strftime("%d %b, %I:%M %p") if t.created_at else "—",
            })

        # Monthly trend — group by month
        monthly_totals = {}
        for t in trend_txns:
            if t.created_at:
                key = t.created_at.strftime("%b %Y")
                monthly_totals[key] = monthly_totals.get(key, 0) + t.amount

        # Top merchants this month
        merchant_totals = {}
        for t in month_txns:
            if t.description:
                merchant_totals[t.description] = (
                    merchant_totals.get(t.description, 0) + t.amount
                )
        top_merchants = sorted(merchant_totals.items(),
                               key=lambda x: x[1], reverse=True)[:5]

        total_month = sum(t.amount for t in month_txns)
        total_week  = sum(t.amount for t in month_txns
                          if t.created_at and t.created_at >= week_ago)

        return {
            "user_phone": user.phone_number[-4:],  # last 4 digits only
            "total_month": round(total_month, 2),
            "total_week": round(total_week, 2),
            "txn_count_month": len(month_txns),
            "category_breakdown": category_totals,
            "monthly_trend": monthly_totals,
            "top_merchants": [{"name": n, "amount": round(a, 2)}
                              for n, a in top_merchants],
            "recent_transactions": recent,
        }

    finally:
        db.close()