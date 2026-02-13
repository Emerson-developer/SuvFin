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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/suvfin"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # S3 / R2
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "suvfin-receipts"
    S3_REGION: str = "auto"

    # AbacatePay
    ABACATEPAY_API_KEY: str = ""
    ABACATEPAY_WEBHOOK_SECRET: str = ""
    PREMIUM_PRICE_CENTS: int = 990  # R$ 9,90 em centavos

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
