"""
Serviço para download de mídia do WhatsApp Cloud API.
"""

import base64
import httpx
from loguru import logger
from app.config.settings import settings


class WhatsAppMedia:
    """Gerencia download de mídia da WhatsApp Cloud API."""

    def __init__(self):
        self.base_url = settings.whatsapp_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"
        }

    async def download(self, media_id: str) -> bytes:
        """Baixa mídia pelo media_id do WhatsApp (2 etapas)."""
        async with httpx.AsyncClient(timeout=60) as client:
            # Etapa 1: Obter URL da mídia
            url_response = await client.get(
                f"{self.base_url}/{media_id}",
                headers=self.headers,
            )
            url_response.raise_for_status()
            media_url = url_response.json()["url"]
            logger.info(f"URL da mídia obtida: {media_url}")

            # Etapa 2: Baixar o arquivo
            media_response = await client.get(
                media_url,
                headers=self.headers,
            )
            media_response.raise_for_status()
            logger.info(f"Mídia baixada: {len(media_response.content)} bytes")
            return media_response.content

    def to_base64(self, image_bytes: bytes) -> str:
        """Converte bytes para base64 string."""
        return base64.standard_b64encode(image_bytes).decode("utf-8")

    def detect_type(self, image_bytes: bytes) -> str:
        """Detecta MIME type pelos magic bytes."""
        if image_bytes[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        elif image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"  # fallback
