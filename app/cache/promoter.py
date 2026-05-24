from app.cache.merchant_cache import (
    get_appearance_count, delete_merchant, THRESHOLD_DB
)
from app.db.database import SessionLocal
from app.db.models import Merchant, User, CategoryEnum


def check_and_promote(user_phone: str, upi_id: str, category: str,
                      nickname: str = None):
    """
    Checks if merchant has crossed the promotion threshold.
    If yes → writes to permanent DB and removes from cache.
    """
    count = get_appearance_count(user_phone, upi_id)

    if count >= THRESHOLD_DB:
        _promote_to_db(user_phone, upi_id, category, nickname, count)
        delete_merchant(user_phone, upi_id)
        return True  # promoted

    return False  # still in cache


def _promote_to_db(user_phone: str, upi_id: str, category: str,
                   nickname: str, count: int):
    """Writes merchant permanently to MySQL."""
    db = SessionLocal()
    try:
        # Get user
        user = db.query(User).filter(User.phone_number == user_phone).first()
        if not user:
            return

        # Check if already in DB
        existing = db.query(Merchant).filter(
            Merchant.user_id == user.id,
            Merchant.upi_id == upi_id,
        ).first()

        if existing:
            existing.is_permanent = True
            existing.appearance_count = count
        else:
            merchant = Merchant(
                user_id=user.id,
                upi_id=upi_id,
                nickname=nickname,
                category=CategoryEnum(category),
                appearance_count=count,
                is_permanent=True,
            )
            db.add(merchant)

        db.commit()
        print(f"✅ Promoted merchant {upi_id} to permanent DB for {user_phone}")

    finally:
        db.close()


def get_permanent_merchant(user_phone: str, upi_id: str) -> dict | None:
    """
    Checks permanent DB for merchant.
    Called before Redis cache — permanent always takes priority.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == user_phone).first()
        if not user:
            return None

        merchant = db.query(Merchant).filter(
            Merchant.user_id == user.id,
            Merchant.upi_id == upi_id,
            Merchant.is_permanent == True,
        ).first()

        if merchant:
            return {
                "category": merchant.category.value,
                "nickname": merchant.nickname,
                "upi_id": merchant.upi_id,
            }
        return None
    finally:
        db.close()