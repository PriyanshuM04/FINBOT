import json
from app.cache.redis_client import get_redis

# TTL tiers in seconds
TTL_7_DAYS  = 7  * 24 * 3600
TTL_30_DAYS = 30 * 24 * 3600
TTL_90_DAYS = 90 * 24 * 3600

# Promotion thresholds
THRESHOLD_30  = 3    # 3+ times in 7 days  → 30 days
THRESHOLD_90  = 10   # 10+ times in 30 days → 90 days
THRESHOLD_DB  = 20   # 20+ times in 90 days → permanent DB


def _cache_key(user_phone: str, upi_id: str) -> str:
    """Redis key: merchant:{phone}:{upi_id}"""
    return f"merchant:{user_phone}:{upi_id}"


def _freq_key(user_phone: str, upi_id: str) -> str:
    """Redis key for frequency counter: freq:{phone}:{upi_id}"""
    return f"freq:{user_phone}:{upi_id}"


def get_merchant(user_phone: str, upi_id: str) -> dict | None:
    """
    Returns cached merchant data or None if not found/expired.
    Data includes: category, nickname, appearance_count
    """
    r = get_redis()
    key = _cache_key(user_phone, upi_id)
    data = r.get(key)
    if data:
        return json.loads(data)
    return None


def set_merchant(user_phone: str, upi_id: str, category: str,
                 nickname: str = None, ttl: int = TTL_7_DAYS):
    """Store merchant in cache with given TTL."""
    r = get_redis()
    key = _cache_key(user_phone, upi_id)
    data = {
        "category": category,
        "nickname": nickname,
        "upi_id": upi_id,
    }
    r.setex(key, ttl, json.dumps(data))


def record_appearance(user_phone: str, upi_id: str) -> int:
    """
    Increments appearance counter and extends TTL based on frequency.
    Returns current appearance count.
    """
    r = get_redis()
    freq_key = _freq_key(user_phone, upi_id)
    cache_key = _cache_key(user_phone, upi_id)

    # Increment frequency counter
    count = r.incr(freq_key)

    # Extend TTL on freq key too (same as cache key)
    current_ttl = r.ttl(cache_key)

    if count >= THRESHOLD_30 and current_ttl < TTL_30_DAYS:
        r.expire(cache_key, TTL_30_DAYS)
        r.expire(freq_key, TTL_30_DAYS)

    elif count >= THRESHOLD_90 and current_ttl < TTL_90_DAYS:
        r.expire(cache_key, TTL_90_DAYS)
        r.expire(freq_key, TTL_90_DAYS)

    return count


def get_appearance_count(user_phone: str, upi_id: str) -> int:
    """Returns current appearance count from Redis."""
    r = get_redis()
    val = r.get(_freq_key(user_phone, upi_id))
    return int(val) if val else 0


def delete_merchant(user_phone: str, upi_id: str):
    """Remove merchant from cache (e.g. after DB promotion)."""
    r = get_redis()
    r.delete(_cache_key(user_phone, upi_id))
    r.delete(_freq_key(user_phone, upi_id))