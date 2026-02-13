"""
Rota de health check.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "SuvFin",
        "version": "1.0.0",
    }


@router.get("/")
async def root():
    return {
        "message": "SuvFin API — Finanças Pessoais pelo WhatsApp 💰",
        "docs": "/docs",
    }
