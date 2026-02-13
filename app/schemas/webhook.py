"""
Schemas Pydantic para o payload do WhatsApp Cloud API (Meta).
Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
"""

from pydantic import BaseModel
from typing import Optional


class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str


class WhatsAppTextMessage(BaseModel):
    body: str


class WhatsAppImageMessage(BaseModel):
    id: str
    mime_type: str
    sha256: Optional[str] = None
    caption: Optional[str] = None


class WhatsAppDocumentMessage(BaseModel):
    id: str
    mime_type: str
    sha256: Optional[str] = None
    filename: Optional[str] = None
    caption: Optional[str] = None


class WhatsAppMessage(BaseModel):
    from_: str  # Número do remetente
    id: str
    timestamp: str
    type: str  # text, image, document, audio, etc.
    text: Optional[WhatsAppTextMessage] = None
    image: Optional[WhatsAppImageMessage] = None
    document: Optional[WhatsAppDocumentMessage] = None

    class Config:
        populate_by_name = True


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WhatsAppStatus(BaseModel):
    id: str
    status: str  # sent, delivered, read, failed
    timestamp: str
    recipient_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[list[WhatsAppContact]] = None
    messages: Optional[list[WhatsAppMessage]] = None
    statuses: Optional[list[WhatsAppStatus]] = None


class WhatsAppChange(BaseModel):
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Payload raiz do webhook da Meta."""
    object: str
    entry: list[WhatsAppEntry]


# --- Schema de mensagem extraída (simplificado para uso interno) ---


class ParsedMessage(BaseModel):
    """Mensagem extraída e simplificada para processamento."""
    phone: str
    name: str
    message_id: str
    type: str  # text, image, document
    content: str  # texto ou media_id
    caption: Optional[str] = None
    timestamp: str
