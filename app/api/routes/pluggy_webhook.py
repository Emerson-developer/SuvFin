"""
Rota de Webhook do Pluggy Open Finance.
Recebe notificações de eventos (item/*, transactions/*).
"""

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from loguru import logger

from app.services.pluggy.sync_service import PluggySyncService
from app.services.whatsapp.client import WhatsAppClient
from app.models.pluggy_item import PluggyItem
from app.config.database import async_session
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/pluggy", tags=["pluggy-webhook"])


@router.post("/webhook")
async def pluggy_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe webhooks do Pluggy.
    Responde 200 imediatamente e processa em background (Pluggy exige <5s).
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    item_id = payload.get("itemId", "")

    logger.info(f"📩 Pluggy webhook: event={event}, itemId={item_id}")

    background_tasks.add_task(_process_pluggy_event, payload)

    return {"status": "received"}


async def _process_pluggy_event(payload: dict) -> None:
    """Processa evento do Pluggy em background."""
    event = payload.get("event", "")
    item_id = payload.get("itemId", "")
    sync_service = PluggySyncService()

    try:
        if event in ("item/created", "item/updated"):
            await sync_service.sync_item(item_id)

        elif event == "item/error":
            status = payload.get("status", "LOGIN_ERROR")
            await sync_service.update_item_status(item_id, status)
            # Notificar usuário via WhatsApp
            await _notify_item_error(item_id, status)

        elif event == "transactions/created":
            await sync_service.import_created_transactions(item_id)

        elif event == "transactions/updated":
            transaction_ids = payload.get("transactionIds", [])
            await sync_service.handle_updated_transactions(transaction_ids)

        elif event == "transactions/deleted":
            transaction_ids = payload.get("transactionIds", [])
            await sync_service.handle_deleted_transactions(transaction_ids)

        elif event == "item/deleted":
            # Item foi deletado no Pluggy
            async with async_session() as session:
                result = await session.execute(
                    select(PluggyItem).where(PluggyItem.pluggy_item_id == item_id)
                )
                item = result.scalar_one_or_none()
                if item and item.is_active:
                    await sync_service.unregister_connection(
                        str(item.user_id), item_id
                    )

        else:
            logger.warning(f"⚠️ Pluggy evento desconhecido: {event}")

    except Exception as e:
        logger.error(f"❌ Erro processando Pluggy webhook {event}: {e}")


async def _notify_item_error(pluggy_item_id: str, status: str) -> None:
    """Notifica o usuário via WhatsApp que sua conexão bancária está com erro."""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(PluggyItem.pluggy_item_id == pluggy_item_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            from app.models.user import User
            result = await session.execute(
                select(User).where(User.id == item.user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return

        bank_name = item.connector_name or "seu banco"
        message = (
            f"⚠️ Houve um problema com a conexão do {bank_name}.\n\n"
            f"Status: {status}\n\n"
            f"Pode ser necessário reconectar. "
            f"Envie \"conectar banco\" para gerar um novo link."
        )

        client = WhatsAppClient()
        await client.send_text(to=user.phone, text=message)
        logger.info(f"📲 Notificação de erro enviada para {user.phone}")

    except Exception as e:
        logger.error(f"❌ Erro ao notificar user sobre item error: {e}")
