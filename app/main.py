"""
SuvFin — Ponto de entrada da aplicação FastAPI.
"""

from contextlib import asynccontextmanager
import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config.settings import settings
from app.config.database import init_db
from app.config.redis_client import close_redis
from app.api.routes.webhook import router as webhook_router
from app.api.routes.health import router as health_router
from app.api.routes.payment import router as payment_router
from app.api.routes.payment import webhook_router as abacatepay_webhook_router
from app.api.routes.tokens import router as tokens_router
from app.api.routes.admin.auth import router as admin_auth_router
from app.api.routes.admin.plans import router as admin_plans_router
from app.api.routes.admin.contacts import router as admin_contacts_router
from app.api.routes.admin.subscriptions import router as admin_subscriptions_router
from app.api.routes.admin.conversations import router as admin_conversations_router
from app.api.routes.admin.messages import router as admin_messages_router
from app.api.routes.admin.dashboard import router as admin_dashboard_router
from app.api.middleware.signature import WebhookSignatureMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.services.finance.category_service import CategoryService
from app.services.admin.auth_service import AuthService


# --- Sentry (monitoramento de erros) ---
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.APP_ENV,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown da aplicação."""
    # STARTUP
    logger.info("🚀 Iniciando SuvFin...")

    # Garantir que as tabelas existam (create_all é idempotente)
    logger.info("🔧 Verificando/criando tabelas no banco...")
    await init_db()

    # Seed categorias padrão
    category_service = CategoryService()
    await category_service.seed_defaults()
    logger.info("📂 Categorias padrão carregadas")

    # Seed admin padrão (se não existir)
    auth_service = AuthService()
    existing_admin = await auth_service.get_admin_by_username("admin")
    if not existing_admin:
        await auth_service.create_admin("admin", "admin123")
        logger.info("🔑 Admin padrão criado (admin/admin123) — TROQUE A SENHA!")

    logger.info(f"✅ SuvFin rodando em {settings.APP_ENV} na porta {settings.APP_PORT}")

    yield

    # SHUTDOWN
    logger.info("🛑 Encerrando SuvFin...")
    await close_redis()
    logger.info("✅ Conexões encerradas")


# --- Criar app FastAPI ---
app = FastAPI(
    title="SuvFin API",
    description="Finanças Pessoais pelo WhatsApp com IA 💰",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(WebhookSignatureMiddleware)

# --- Rotas ---
app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(payment_router)
app.include_router(abacatepay_webhook_router)
app.include_router(tokens_router)

# --- Rotas Admin (painel) ---
admin_prefix = "/api/v1/admin"
app.include_router(admin_auth_router, prefix=admin_prefix)
app.include_router(admin_plans_router, prefix=admin_prefix)
app.include_router(admin_contacts_router, prefix=admin_prefix)
app.include_router(admin_subscriptions_router, prefix=admin_prefix)
app.include_router(admin_conversations_router, prefix=admin_prefix)
app.include_router(admin_messages_router, prefix=admin_prefix)
app.include_router(admin_dashboard_router, prefix=admin_prefix)

# --- Páginas estáticas ---
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/upgrade")
async def upgrade_page():
    """Página de upgrade para o plano Premium."""
    return FileResponse(
        os.path.join(static_dir, "upgrade.html"),
        media_type="text/html",
    )


@app.get("/upgrade/sucesso")
async def upgrade_success_page():
    """Página de sucesso após pagamento."""
    return FileResponse(
        os.path.join(static_dir, "upgrade.html"),
        media_type="text/html",
    )
