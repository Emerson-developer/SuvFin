"""
Parser para extrair dados relevantes do payload do webhook da Meta.
"""

from loguru import logger
from app.schemas.webhook import ParsedMessage
from typing import Optional


class WhatsAppParser:
    """Extrai e simplifica mensagens do payload do webhook da Meta."""

    def extract(self, payload: dict) -> Optional[ParsedMessage]:
        """Extrai a primeira mensagem do payload do webhook."""
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            contacts = value.get("contacts", [{}])
            contact = contacts[0] if contacts else {}
            profile_name = contact.get("profile", {}).get("name", "Usuário")

            msg_type = msg.get("type", "text")
            content = ""
            caption = None

            if msg_type == "text":
                content = msg.get("text", {}).get("body", "")
            elif msg_type == "image":
                content = msg.get("image", {}).get("id", "")
                caption = msg.get("image", {}).get("caption")
            elif msg_type == "document":
                content = msg.get("document", {}).get("id", "")
                caption = msg.get("document", {}).get("caption")
            elif msg_type == "audio":
                content = msg.get("audio", {}).get("id", "")
            else:
                logger.warning(f"Tipo de mensagem não suportado: {msg_type}")
                return None

            return ParsedMessage(
                phone=msg.get("from", ""),
                name=profile_name,
                message_id=msg.get("id", ""),
                type=msg_type,
                content=content,
                caption=caption,
                timestamp=msg.get("timestamp", ""),
            )

        except (KeyError, IndexError) as e:
            logger.error(f"Erro ao parsear payload do webhook: {e}")
            return None
