"""
Cliente para enviar mensagens via WhatsApp Cloud API (Meta Graph API).
Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
"""

import httpx
from loguru import logger
from app.config.settings import settings


class WhatsAppClient:
    """Envia mensagens de texto e mídia via WhatsApp Cloud API."""

    def __init__(self):
        self.base_url = settings.whatsapp_base_url
        self.phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, text: str) -> dict:
        """Envia mensagem de texto para o usuário."""
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"Mensagem enviada para {to}: {data}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Erro ao enviar mensagem para {to}: "
                    f"{e.response.status_code} - {e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(f"Erro inesperado ao enviar mensagem: {e}")
                raise

    async def send_image(self, to: str, image_url: str, caption: str = "") -> dict:
        """Envia imagem via URL para o usuário."""
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict:
        """Envia documento (PDF, etc.) para o usuário."""
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "caption": caption,
                "filename": filename,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def mark_as_read(self, message_id: str) -> dict:
        """Marca uma mensagem como lida (blue ticks)."""
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
