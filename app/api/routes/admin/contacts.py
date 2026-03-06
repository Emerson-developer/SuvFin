"""
Rotas de contatos (mapeados sobre users).
GET    /api/v1/admin/contacts
GET    /api/v1/admin/contacts/{contact_id}
POST   /api/v1/admin/contacts
PATCH  /api/v1/admin/contacts/{contact_id}
DELETE /api/v1/admin/contacts/{contact_id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.api.middleware.auth import get_current_admin
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.admin.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["admin-contacts"])


@router.get("")
async def list_contacts(
    search: str = Query(None),
    status_filter: str = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _admin: dict = Depends(get_current_admin),
):
    """
    Lista todos os contatos com subscription + plan aninhados.
    Suporta busca em name, phone, email e filtro por status de assinatura.
    """
    service = ContactService()
    result = await service.get_all(
        search=search,
        status=status_filter,
        page=page,
        limit=limit,
    )
    return result


@router.get("/{contact_id}")
async def get_contact(
    contact_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """
    Retorna um contato completo com subscription, plan, conversation e recent_messages.
    """
    service = ContactService()
    contact = await service.get_by_id(contact_id)

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return {"data": contact}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    _admin: dict = Depends(get_current_admin),
):
    """
    Cria um novo contato.
    Se plan_id for fornecido, cria também subscription + conversation em uma transação.
    """
    if not body.phone_number:
        raise HTTPException(status_code=422, detail="phone_number is required")

    service = ContactService()

    try:
        # If plan_id provided → create contact + subscription + conversation
        if body.plan_id:
            result = await service.create_full(body.model_dump())
            return {"data": result}

        # Otherwise → just create the contact
        contact = await service.create(body.model_dump())
        return {"data": contact}
    except ValueError as e:
        msg = str(e)
        if msg.startswith("CONFLICT:"):
            raise HTTPException(status_code=409, detail=msg.split(":", 1)[1])
        if msg.startswith("NOT_FOUND:"):
            raise HTTPException(status_code=404, detail=msg.split(":", 1)[1])
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: str,
    body: ContactUpdate,
    _admin: dict = Depends(get_current_admin),
):
    """Edita um contato (PATCH parcial)."""
    service = ContactService()
    data = body.model_dump(exclude_unset=True)
    contact = await service.update(contact_id, data)

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return {"data": contact}


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Remove um contato (e em cascata: subscription, conversation, messages)."""
    service = ContactService()
    deleted = await service.delete(contact_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")

    return JSONResponse(status_code=204, content=None)
