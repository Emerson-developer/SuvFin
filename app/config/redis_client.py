import redis.asyncio as redis
from app.config.settings import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> redis.Redis:
    """Dependency para injetar Redis."""
    return redis_client


async def close_redis():
    """Fecha conexão Redis no shutdown."""
    await redis_client.close()
