"""
Middleware para verificação de assinatura do webhook da Meta.
Valida X-Hub-Signature-256 para garantir que o payload é autêntico.
"""

import hashlib
import hmac

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.config.settings import settings


class WebhookSignatureMiddleware(BaseHTTPMiddleware):
    """Verifica a assinatura HMAC-SHA256 do webhook da Meta."""

    async def dispatch(self, request: Request, call_next):
        # Só verificar em rotas POST do webhook
        if request.url.path == "/webhook" and request.method == "POST":
            # Se APP_SECRET não está configurado, pular validação
            if not settings.FACEBOOK_APP_SECRET:
                logger.warning("⚠️ FACEBOOK_APP_SECRET não configurado - pulando validação")
                return await call_next(request)

            signature = request.headers.get("X-Hub-Signature-256", "")

            if not signature:
                # Em dev, permitir sem assinatura
                if settings.APP_ENV == "development":
                    logger.warning("⚠️ Webhook sem assinatura (permitido em dev)")
                else:
                    logger.error("❌ Webhook sem assinatura")
                    raise HTTPException(status_code=401, detail="Missing signature")

            if signature and settings.APP_ENV != "development":
                body = await request.body()
                expected = self._compute_signature(body)

                if not hmac.compare_digest(signature, expected):
                    logger.error("❌ Assinatura do webhook inválida")
                    raise HTTPException(status_code=401, detail="Invalid signature")

                logger.debug("✅ Assinatura do webhook válida")

        response = await call_next(request)
        return response

    def _compute_signature(self, body: bytes) -> str:
        """Calcula HMAC-SHA256 do body com o app secret."""
        mac = hmac.new(
            settings.FACEBOOK_APP_SECRET.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        )
        return f"sha256={mac.hexdigest()}"
