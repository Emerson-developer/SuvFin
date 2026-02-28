from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do .env"""

    # App
    APP_NAME: str = "SuvFin"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000

    # WhatsApp Cloud API
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WEBHOOK_VERIFY_TOKEN: str = "suvfin_verify_token"
    FACEBOOK_APP_SECRET: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/suvfin"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MODEL_LIGHT: str = "claude-3-5-haiku-latest"

    # Otimização de custos LLM
    LLM_MAX_CONVERSATION_MESSAGES: int = 6  # Histórico de chat (não afeta dados financeiros)
    LLM_CONVERSATION_TTL: int = 3600  # TTL conversa em segundos (1 hora)
    LLM_CACHE_TTL: int = 300  # Cache de respostas em segundos (5 min)
    LLM_MAX_MESSAGES_PER_USER_HOUR: int = 30  # Rate limit por usuário/hora
    LLM_MAX_MESSAGES_PER_USER_DAY: int = 200  # Rate limit por usuário/dia
    LLM_COST_ALERT_DAILY_USD: float = 10.0  # Alerta de custo diário em USD

    # S3 / R2
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "suvfin-receipts"
    S3_REGION: str = "auto"

    # AbacatePay
    ABACATEPAY_API_KEY: str = ""
    ABACATEPAY_WEBHOOK_SECRET: str = ""

    # Preços dos planos (em centavos)
    PLAN_MONTHLY_CENTS: int = 1990       # R$ 19,90/mês
    PLAN_ANNUAL_CENTS: int = 19000       # R$ 190,00/ano

    # Legado (manter para compatibilidade — não usar)
    PLAN_BASICO_MONTHLY_CENTS: int = 1990
    PLAN_PRO_MONTHLY_CENTS: int = 1990
    PLAN_PREMIUM_MONTHLY_CENTS: int = 1990
    PLAN_BASICO_ANNUAL_CENTS: int = 19000
    PLAN_PRO_ANNUAL_CENTS: int = 19000
    PLAN_PREMIUM_ANNUAL_CENTS: int = 19000
    PREMIUM_PRICE_CENTS: int = 1990

    # App URLs
    APP_URL: str = "https://suvfin.com"
    SUVFIN_FRONTEND_URL: str = "https://suvfin.com"

    # Sentry
    SENTRY_DSN: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    @property
    def whatsapp_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
