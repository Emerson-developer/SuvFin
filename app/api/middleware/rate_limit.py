"""
Middleware de rate limiting usando Redis.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.config.redis_client import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting por IP/número do WhatsApp."""

    MAX_REQUESTS = 30  # Por minuto
    WINDOW_SECONDS = 60

    async def dispatch(self, request: Request, call_next):
        # Só aplicar rate limit no webhook POST
        if request.url.path == "/webhook" and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            key = f"rate:{client_ip}"

            try:
                current = await redis_client.incr(key)
                if current == 1:
                    await redis_client.expire(key, self.WINDOW_SECONDS)

                if current > self.MAX_REQUESTS:
                    logger.warning(f"Rate limit excedido para {client_ip}")
                    raise HTTPException(
                        status_code=429,
                        detail="Too many requests. Try again later.",
                    )
            except HTTPException:
                raise
            except Exception as e:
                # Se o Redis estiver down, permitir (fail open)
                logger.warning(f"Rate limit check falhou (Redis): {e}")

        response = await call_next(request)
        return response
