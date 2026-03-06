"""
Rotas de subscriptions.
GET   /api/v1/admin/subscriptions
GET   /api/v1/admin/subscriptions/by-contact/{contact_id}
POST  /api/v1/admin/subscriptions
PATCH /api/v1/admin/subscriptions/{sub_id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.middleware.auth import get_current_admin
from app.schemas.subscription_schema import SubscriptionCreate, SubscriptionUpdate
from app.services.admin.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["admin-subscriptions"])


@router.get("")
async def list_subscriptions(
    contact_id: str = Query(None),
    plan_id: str = Query(None),
    status_filter: str = Query(None, alias="status"),
    _admin: dict = Depends(get_current_admin),
):
    """Lista todas as assinaturas com filtros opcionais."""
    service = SubscriptionService()
    subs = await service.get_all(
        contact_id=contact_id,
        plan_id=plan_id,
        status=status_filter,
    )
    return {"data": subs}


@router.get("/by-contact/{contact_id}")
async def get_subscription_by_contact(
    contact_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Retorna a assinatura de um contato específico."""
    service = SubscriptionService()
    sub = await service.get_by_contact(contact_id)
    return {"data": sub}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    _admin: dict = Depends(get_current_admin),
):
    """Cria uma nova assinatura para um contato."""
    service = SubscriptionService()
    try:
        sub = await service.create(body.model_dump())
        return {"data": sub}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{sub_id}")
async def update_subscription(
    sub_id: str,
    body: SubscriptionUpdate,
    _admin: dict = Depends(get_current_admin),
):
    """
    Altera subscription.
    Quando plan_id muda: recalcula started_at e expires_at baseado no billing_cycle.
    Sincroniza com users.license_type automaticamente.
    """
    service = SubscriptionService()
    data = body.model_dump(exclude_unset=True)
    sub = await service.update(sub_id, data)

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {"data": sub}
