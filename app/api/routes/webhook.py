"""
Rotas do Webhook do WhatsApp (Meta Cloud API).
"""

from fastapi import APIRouter, Request, Response, Query, HTTPException, BackgroundTasks
from loguru import logger

from app.config.settings import settings
from app.services.whatsapp.parser import WhatsAppParser
from app.services.whatsapp.client import WhatsAppClient
from app.services.license.license_service import LicenseService
from app.services.mcp.processor import MCPProcessor

router = APIRouter(tags=["webhook"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Verificação do webhook da Meta (handshake).
    A Meta envia GET com hub.mode, hub.challenge e hub.verify_token.
    """
    logger.info(
        f"Webhook verification: mode={hub_mode}, token={hub_verify_token}"
    )

    if hub_mode == "subscribe" and hub_verify_token == settings.WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso ✅")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Webhook verification falhou ❌")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe mensagens do WhatsApp Cloud API.
    Responde 200 imediatamente e processa em background.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # A Meta espera 200 rápido — processa em background
    background_tasks.add_task(_process_webhook, payload)

    return {"status": "received"}


async def _process_webhook(payload: dict):
    """Processa o payload do webhook (executado em background)."""
    parser = WhatsAppParser()
    message = parser.extract(payload)

    if not message:
        logger.debug("Payload ignorado (sem mensagem de usuário)")
        return

    phone = message.phone
    name = message.name
    msg_type = message.type
    content = message.content
    message_id = message.message_id

    logger.info(
        f"📩 Mensagem recebida: phone={phone}, type={msg_type}, "
        f"content={content[:50] if isinstance(content, str) else content}"
    )

    client = WhatsAppClient()

    # Marcar mensagem como lida
    try:
        await client.mark_as_read(message_id)
    except Exception as e:
        logger.warning(f"Falha ao marcar como lida: {e}")

    # Verificar/criar usuário
    license_service = LicenseService()
    user = await license_service.get_or_create_user(phone, name)

    if not user.is_license_valid:
        # Gerar link de pagamento PIX via AbacatePay
        try:
            payment_url = await license_service.get_payment_link(phone)
            upgrade_msg = (
                "⏰ Seu período de teste expirou!\n\n"
                "Para continuar usando o SuvFin, faça upgrade para o plano Premium:\n\n"
                f"🔗 {payment_url}\n\n"
                "💰 R$ 9,90 — Pagamento único via PIX\n"
                "✅ Lançamentos ilimitados\n"
                "✅ Relatórios avançados\n"
                "✅ Suporte prioritário\n\n"
                "O link acima abre o pagamento PIX instantâneo! 🥑"
            )
        except Exception as e:
            logger.error(f"Erro ao gerar link de pagamento: {e}")
            upgrade_msg = (
                "⏰ Seu período de teste expirou!\n\n"
                "Para continuar usando o SuvFin, faça upgrade para o plano Premium!\n"
                "💰 R$ 9,90 — Lançamentos ilimitados e muito mais!\n\n"
                "Entre em contato para fazer o upgrade. 🚀"
            )

        await client.send_text(phone, upgrade_msg)
        return

    # Processar com MCP + LLM
    processor = MCPProcessor()
    response = await processor.process(
        user_id=str(user.id),
        phone=phone,
        message_type=msg_type,
        content=content,
        name=name,
    )

    # Enviar resposta
    await client.send_text(phone, response.text)

    # Se tiver mídia (gráfico, PDF), enviar
    if response.media and response.media_type:
        if "image" in response.media_type:
            await client.send_image(phone, response.media, caption="📊 Relatório")
        elif "pdf" in response.media_type:
            await client.send_document(
                phone, response.media, "relatorio_suvfin.pdf", caption="📄 Relatório"
            )

    logger.info(f"✅ Resposta enviada para {phone}")
