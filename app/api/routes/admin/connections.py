"""
Rotas admin para gerenciar conexões Open Finance dos usuários.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.middleware.auth import get_current_admin
from app.config.database import async_session
from app.models.pluggy_connection_config import PluggyConnectionConfig
from app.models.pluggy_item import PluggyItem
from app.models.user import User
from app.schemas.pluggy import PluggyConnectionConfigResponse, PluggyConnectionConfigUpdate

router = APIRouter(prefix="/connections", tags=["admin-connections"])


@router.get("")
async def list_connection_configs(
    _admin: dict = Depends(get_current_admin),
):
    """Lista todos os PluggyConnectionConfig com dados do usuário."""
    async with async_session() as session:
        result = await session.execute(
            select(PluggyConnectionConfig, User)
            .join(User, PluggyConnectionConfig.user_id == User.id)
            .order_by(PluggyConnectionConfig.active_connections.desc())
        )
        rows = result.all()

    return [
        PluggyConnectionConfigResponse(
            user_id=str(config.user_id),
            user_phone=user.phone,
            user_name=user.name,
            max_connections=config.max_connections,
            active_connections=config.active_connections,
            notes=config.notes,
        )
        for config, user in rows
    ]


@router.patch("/{user_id}")
async def update_connection_config(
    user_id: str,
    body: PluggyConnectionConfigUpdate,
    _admin: dict = Depends(get_current_admin),
):
    """Atualiza max_connections e/ou notes de um usuário."""
    async with async_session() as session:
        result = await session.execute(
            select(PluggyConnectionConfig).where(
                PluggyConnectionConfig.user_id == user_id
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail="Config não encontrada")

        if body.max_connections is not None:
            config.max_connections = body.max_connections
        if body.notes is not None:
            config.notes = body.notes

        await session.commit()

    return {"status": "updated", "user_id": user_id}


@router.get("/{user_id}/items")
async def list_user_items(
    user_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Lista conexões (PluggyItems) de um usuário específico."""
    async with async_session() as session:
        result = await session.execute(
            select(PluggyItem).where(PluggyItem.user_id == user_id)
            .order_by(PluggyItem.created_at.desc())
        )
        items = result.scalars().all()

    return [
        {
            "id": str(item.id),
            "pluggy_item_id": item.pluggy_item_id,
            "connector_name": item.connector_name,
            "status": item.status,
            "is_active": item.is_active,
            "connected_at": item.connected_at.isoformat() if item.connected_at else None,
            "disconnected_at": item.disconnected_at.isoformat() if item.disconnected_at else None,
            "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
        }
        for item in items
    ]
