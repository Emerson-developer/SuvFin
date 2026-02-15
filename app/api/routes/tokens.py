"""
Rota de monitoramento de tokens e custos da API Claude.
"""

from datetime import date, timedelta
from fastapi import APIRouter, Query
from app.config.redis_client import redis_client
from app.config.settings import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tokens/today")
async def get_today_usage():
    """Retorna uso de tokens do dia atual."""
    today = date.today().isoformat()
    return await _get_usage_for_date(today)


@router.get("/tokens/summary")
async def get_usage_summary(days: int = Query(default=7, le=30)):
    """Retorna resumo de uso dos últimos N dias."""
    results = []
    total_cost = 0.0

    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        usage = await _get_usage_for_date(d)
        results.append(usage)
        total_cost += usage.get("estimated_cost_usd", 0)

    return {
        "period_days": days,
        "total_estimated_cost_usd": round(total_cost, 4),
        "daily_breakdown": results,
        "model_primary": settings.ANTHROPIC_MODEL,
        "model_light": settings.ANTHROPIC_MODEL_LIGHT,
        "config": {
            "max_conversation_messages": settings.LLM_MAX_CONVERSATION_MESSAGES,
            "cache_ttl_seconds": settings.LLM_CACHE_TTL,
            "rate_limit_hour": settings.LLM_MAX_MESSAGES_PER_USER_HOUR,
            "rate_limit_day": settings.LLM_MAX_MESSAGES_PER_USER_DAY,
            "cost_alert_daily_usd": settings.LLM_COST_ALERT_DAILY_USD,
        },
    }


@router.get("/tokens/user/{phone}")
async def get_user_usage(phone: str, days: int = Query(default=7, le=30)):
    """Retorna uso de tokens de um usuário específico."""
    results = []

    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        key = f"tokens:user:{phone}:{d}"

        try:
            data = await redis_client.hgetall(key)
            if data:
                input_t = int(data.get("input", 0))
                output_t = int(data.get("output", 0))
                results.append({
                    "date": d,
                    "input_tokens": input_t,
                    "output_tokens": output_t,
                    "cache_read_tokens": int(data.get("cache_read", 0)),
                    "requests": int(data.get("requests", 0)),
                    "estimated_cost_usd": round(
                        (input_t / 1_000_000) * 3.00
                        + (output_t / 1_000_000) * 15.00,
                        4,
                    ),
                })
        except Exception:
            pass

    return {
        "phone": phone,
        "period_days": days,
        "daily_usage": results,
        "total_cost_usd": round(
            sum(d.get("estimated_cost_usd", 0) for d in results), 4
        ),
    }


async def _get_usage_for_date(d: str) -> dict:
    """Retorna métricas de uso para uma data."""
    key = f"tokens:global:{d}"

    try:
        data = await redis_client.hgetall(key)
    except Exception:
        data = {}

    input_t = int(data.get("input", 0))
    output_t = int(data.get("output", 0))
    cache_read = int(data.get("cache_read", 0))
    cache_create = int(data.get("cache_create", 0))
    requests = int(data.get("requests", 0))

    # Custo estimado (Sonnet 4 prices)
    cost_input = (input_t / 1_000_000) * 3.00
    cost_output = (output_t / 1_000_000) * 15.00
    cost_total = cost_input + cost_output

    # Economia do cache (tokens lidos do cache não foram cobrados como input)
    cache_savings = (cache_read / 1_000_000) * 3.00 * 0.9  # 90% desconto no cache

    return {
        "date": d,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "cache_read_tokens": cache_read,
        "cache_create_tokens": cache_create,
        "total_requests": requests,
        "estimated_cost_usd": round(cost_total, 4),
        "estimated_cache_savings_usd": round(cache_savings, 4),
        "avg_tokens_per_request": round(
            (input_t + output_t) / max(requests, 1), 1
        ),
    }
