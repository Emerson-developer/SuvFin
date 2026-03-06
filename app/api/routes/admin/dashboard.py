"""
Rota de dashboard stats.
GET /api/v1/admin/dashboard/stats
"""

from fastapi import APIRouter, Depends

from app.api.middleware.auth import get_current_admin
from app.services.admin.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    _admin: dict = Depends(get_current_admin),
):
    """
    Endpoint de agregação para o Dashboard.
    Retorna todas as métricas em uma única chamada.
    """
    service = DashboardService()
    stats = await service.get_stats()
    return stats
