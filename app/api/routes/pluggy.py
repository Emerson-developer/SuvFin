"""
Rotas da API Pluggy Open Finance.
Gerar connect token, listar contas, desconectar.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.pluggy.client import PluggyClient, PluggyError
from app.services.pluggy.sync_service import PluggySyncService
from app.schemas.pluggy import PluggyConnectResponse, PluggyAccountResponse

router = APIRouter(prefix="/api/v1/pluggy", tags=["pluggy"])


@router.post("/connect/{user_phone}", response_model=PluggyConnectResponse)
async def create_connect_token(user_phone: str):
    """
    Gera um Connect Token do Pluggy para o usuário conectar seu banco.
    Retorna a URL do Pluggy Connect widget.
    """
    client = PluggyClient()

    try:
        token = await client.create_connect_token(client_user_id=user_phone)
    except PluggyError as e:
        logger.error(f"❌ Erro ao gerar connect token: {e}")
        raise HTTPException(status_code=502, detail="Erro ao gerar link de conexão")

    connect_url = f"https://connect.pluggy.ai/?connect_token={token}"
    return PluggyConnectResponse(connect_url=connect_url)


@router.get("/accounts/{user_id}")
async def list_user_accounts(user_id: str):
    """Lista contas bancárias conectadas de um usuário."""
    sync_service = PluggySyncService()
    items = await sync_service.get_user_items(user_id)
    accounts = await sync_service.get_user_accounts(user_id)

    result = []
    item_map = {str(i.id): i for i in items}

    for acc in accounts:
        item = item_map.get(str(acc.pluggy_item_id))
        result.append(
            PluggyAccountResponse(
                id=str(acc.id),
                bank_name=item.connector_name if item else None,
                account_name=acc.name,
                subtype=acc.subtype,
                number=acc.number,
                balance=acc.balance,
                currency_code=acc.currency_code,
                last_sync_at=item.last_sync_at if item else None,
                status=item.status if item else "UNKNOWN",
            )
        )

    return result


@router.delete("/items/{pluggy_item_id}")
async def disconnect_item(pluggy_item_id: str, user_id: str):
    """Desconecta um Item (banco) do Pluggy."""
    client = PluggyClient()
    sync_service = PluggySyncService()

    try:
        await client.delete_item(pluggy_item_id)
    except PluggyError as e:
        logger.error(f"❌ Erro ao deletar item no Pluggy: {e}")
        # Continua para limpar local mesmo se falhar no Pluggy

    await sync_service.unregister_connection(user_id, pluggy_item_id)
    return {"status": "disconnected", "item_id": pluggy_item_id}
