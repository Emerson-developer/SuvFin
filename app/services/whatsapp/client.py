"""
Cliente para enviar mensagens via WhatsApp Cloud API (Meta Graph API).
Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
"""

import httpx
from loguru import logger
from app.config.settings import settings


class WhatsAppClient:
    """Envia mensagens de texto e mídia via WhatsApp Cloud API."""

    _http_client: httpx.AsyncClient | None = None

    def __init__(self):
        self.base_url = settings.whatsapp_base_url
        self.phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _get_http_client(cls) -> httpx.AsyncClient:
        if cls._http_client is None or cls._http_client.is_closed:
            cls._http_client = httpx.AsyncClient(timeout=30)
        return cls._http_client

    @classmethod
    async def close_http_client(cls):
        if cls._http_client and not cls._http_client.is_closed:
            await cls._http_client.close()
            cls._http_client = None

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

        client = self._get_http_client()
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

        client = self._get_http_client()
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

        client = self._get_http_client()
        response = await client.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def send_interactive_list(
        self,
        to: str,
        header_text: str,
        body_text: str,
        footer_text: str,
        button_text: str,
        sections: list[dict],
    ) -> dict:
        """
        Envia mensagem interativa com lista de opções (máx 10 itens).
        sections = [{"title": "Seção", "rows": [{"id": "x", "title": "T", "description": "D"}]}]
        """
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header_text},
                "body": {"text": body_text},
                "footer": {"text": footer_text},
                "action": {
                    "button": button_text,
                    "sections": sections,
                },
            },
        }

        client = self._get_http_client()
        try:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Lista interativa enviada para {to}: {data}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Erro ao enviar lista interativa para {to}: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise

    async def mark_as_read(self, message_id: str) -> dict:
        """Marca uma mensagem como lida (blue ticks)."""
        url = f"{self.base_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        client = self._get_http_client()
        response = await client.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()
