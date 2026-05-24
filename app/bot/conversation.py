"""
Manages pending conversation states in Redis.
When bot asks user for category or confirmation,
the pending state is stored here until user replies.

State types:
  - "awaiting_category" : bot asked user to pick category for a merchant
  - "awaiting_confirmation" : bot asked user to confirm parsed amount
"""
import json
from app.cache.redis_client import get_redis

PENDING_TTL = 10 * 60  # 10 minutes to respond before state expires


def _state_key(user_phone: str) -> str:
    return f"pending:{user_phone}"


def set_pending_category(user_phone: str, upi_id: str, merchant_name: str,
                         amount: float, transaction_type: str, app_source: str):
    """Store state waiting for user to pick a category."""
    r = get_redis()
    state = {
        "type": "awaiting_category",
        "upi_id": upi_id,
        "merchant_name": merchant_name,
        "amount": amount,
        "transaction_type": transaction_type,
        "app_source": app_source,
    }
    r.setex(_state_key(user_phone), PENDING_TTL, json.dumps(state))


def set_pending_confirmation(user_phone: str, upi_id: str, merchant_name: str,
                              amount: float, category: str,
                              transaction_type: str, app_source: str):
    """Store state waiting for user to confirm parsed details."""
    r = get_redis()
    state = {
        "type": "awaiting_confirmation",
        "upi_id": upi_id,
        "merchant_name": merchant_name,
        "amount": amount,
        "category": category,
        "transaction_type": transaction_type,
        "app_source": app_source,
    }
    r.setex(_state_key(user_phone), PENDING_TTL, json.dumps(state))


def get_pending_state(user_phone: str) -> dict | None:
    """Returns pending state or None if no state / expired."""
    r = get_redis()
    data = r.get(_state_key(user_phone))
    if data:
        return json.loads(data)
    return None


def clear_pending_state(user_phone: str):
    """Clear state after user has responded."""
    r = get_redis()
    r.delete(_state_key(user_phone))


def set_pending_state_raw(user_phone: str, state: dict):
    """Store any arbitrary state dict."""
    r = get_redis()
    r.setex(_state_key(user_phone), PENDING_TTL, json.dumps(state))