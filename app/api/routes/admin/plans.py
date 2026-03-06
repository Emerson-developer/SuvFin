"""
Rotas de planos.
GET /api/v1/admin/plans
GET /api/v1/admin/plans/{plan_id}
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.middleware.auth import get_current_admin
from app.config.database import async_session
from app.models.plan import Plan

router = APIRouter(prefix="/plans", tags=["admin-plans"])


@router.get("")
async def list_plans(
    active_only: bool = Query(False),
    _admin: dict = Depends(get_current_admin),
):
    """Lista todos os planos."""
    async with async_session() as session:
        stmt = select(Plan)
        if active_only:
            stmt = stmt.where(Plan.is_active.is_(True))

        result = await session.execute(stmt)
        plans = result.scalars().all()

        return {
            "data": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "price": float(p.price),
                    "features": p.features or [],
                    "billing_cycle": p.billing_cycle,
                    "is_active": p.is_active,
                    "created_at": p.created_at,
                }
                for p in plans
            ]
        }


@router.get("/{plan_id}")
async def get_plan(
    plan_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Retorna um plano específico."""
    async with async_session() as session:
        plan = await session.get(Plan, UUID(plan_id))
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        return {
            "data": {
                "id": str(plan.id),
                "name": plan.name,
                "price": float(plan.price),
                "features": plan.features or [],
                "billing_cycle": plan.billing_cycle,
                "is_active": plan.is_active,
                "created_at": plan.created_at,
            }
        }
