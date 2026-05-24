import redis
from app.config import settings

# Single Redis connection pool shared across the app
_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,   # always return strings, not bytes
        )
    return _redis_client