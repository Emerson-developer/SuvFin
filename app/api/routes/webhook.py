"""
Rotas do Webhook do WhatsApp (Meta Cloud API).
"""

import asyncio
import re

from fastapi import APIRouter, Request, Response, Query, HTTPException, BackgroundTasks
from loguru import logger

from app.config.settings import settings
from app.services.whatsapp.parser import WhatsAppParser
from app.services.whatsapp.client import WhatsAppClient
from app.services.license.license_service import LicenseService
from app.services.mcp.processor import MCPProcessor
from app.services.admin.message_service import MessageService

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


def _detect_plan_selection(text: str) -> tuple[str, str] | None:
    """
    Detecta se o usuário está escolhendo um plano pelo texto da mensagem.
    Retorna (plan, period) ou None.
    """
    t = text.lower().strip()
    # Normalizar acentos comuns
    t = t.replace("á", "a").replace("é", "e").replace("í", "i")

    # Detectar período (agora só temos Mensal e Anual)
    if re.search(r"\banual\b|\banuais\b|\bannual\b", t):
        return ("PRO", "ANNUAL")
    # Evitar falsos positivos com palavras comuns do português:
    # "mês" (normalizado para "mes") e "pro" (= "para o") são muito comuns.
    # Só ativar quando há intenção clara de assinar/pagar.
    elif re.search(r"\bplano\s+mensal\b|\bmensal\b|\bassinar\b|\bquero\s+(o\s+)?mensal\b|\bquero\s+(o\s+)?plano\b", t):
        return ("PRO", "MONTHLY")

    return None


def _is_plan_inquiry(text: str) -> bool:
    """
    Detecta se o usuário está perguntando sobre planos/upgrade/assinatura.
    Retorna True se a mensagem é sobre planos.
    """
    t = text.lower().strip()
    t = t.replace("á", "a").replace("é", "e").replace("í", "i")
    t = t.replace("ã", "a").replace("ç", "c").replace("ú", "u").replace("ó", "o")

    plan_patterns = [
        r"\bplanos?\b",
        r"\bupgrade\b",
        r"\bassinatura\b",
        r"\bassinar\b",
        r"\bquanto\s+custa\b",
        r"\bmudar\s+plano\b",
        r"\btrocar\s+plano\b",
        r"\bmelhorar\s+plano\b",
        r"\bquero\s+(fazer\s+)?upgrade\b",
        r"\bver\s+(os\s+)?planos?\b",
        r"\bsaber\s+(os\s+)?planos?\b",
        r"\bconhecer\s+(os\s+)?planos?\b",
        r"\bquais\s+(sao\s+)?(os\s+)?planos?\b",
        r"\bopcoes\s+de\s+plano\b",
        r"\bplanos\s+disponiveis\b",
    ]

    for pattern in plan_patterns:
        if re.search(pattern, t):
            return True
    return False


async def _send_plan_list(phone: str, client: WhatsAppClient) -> None:
    """Envia lista interativa com os planos disponíveis."""
    try:
        await client.send_interactive_list(
            to=phone,
            header_text="Escolha seu Plano",
            body_text=(
                "⏰ Seu período de teste expirou!\n\n"
                "Para continuar usando o SuvFin, escolha um plano abaixo.\n\n"
                "💡 O plano anual tem 20% de desconto!"
            ),
            footer_text="SuvFin — Seu financeiro no WhatsApp",
            button_text="Ver Planos",
            sections=[
                {
                    "title": "Planos Disponíveis",
                    "rows": [
                        {
                            "id": "plan_pro_monthly",
                            "title": "🟢 Plano Mensal",
                            "description": "R$ 19,90/mês • Registros ilimitados",
                        },
                        {
                            "id": "plan_pro_annual",
                            "title": "🏆 Plano Anual",
                            "description": "R$ 190/ano • Economize 20%",
                        },
                    ],
                },
            ],
        )
        logger.info(f"📋 Lista de planos enviada para {phone}")
    except Exception as e:
        logger.error(f"Erro ao enviar lista interativa para {phone}: {e}")
        # Fallback: texto simples
        await client.send_text(
            phone,
            (
                "⏰ *Seu período de teste expirou!*\n\n"
                "Escolha um plano para continuar:\n\n"
                "🟢 *Plano Mensal* — R$ 19,90/mês\n"
                "🏆 *Plano Anual* — R$ 190/ano _(economize 20%!)_\n\n"
                'Envie: _"Quero o Mensal"_ ou _"Quero o Anual"_'
            ),
        )


async def _send_plan_list_active_user(phone: str, user, client: WhatsAppClient) -> None:
    """Envia lista de planos para usuário ativo que quer ver opções/upgrade."""
    current_plan = user.license_type.value if user.license_type else "FREE_TRIAL"
    plan_labels = {
        "FREE_TRIAL": "Teste Grátis",
        "BASICO": "⭐ Básico",
        "PRO": "⚡ Pro",
        "PREMIUM": "👑 Premium",
    }
    current_label = plan_labels.get(current_plan, current_plan)

    try:
        await client.send_interactive_list(
            to=phone,
            header_text="Nossos Planos",
            body_text=(
                f"Seu plano atual: *{current_label}*\n\n"
                "Confira os planos disponíveis:\n\n"
                "💡 O plano anual tem 20% de desconto!"
            ),
            footer_text="SuvFin — Seu financeiro no WhatsApp",
            button_text="Ver Planos",
            sections=[
                {
                    "title": "Planos Disponíveis",
                    "rows": [
                        {
                            "id": "plan_pro_monthly",
                            "title": "🟢 Plano Mensal",
                            "description": "R$ 19,90/mês • Registros ilimitados",
                        },
                        {
                            "id": "plan_pro_annual",
                            "title": "🏆 Plano Anual",
                            "description": "R$ 190/ano • Economize 20%",
                        },
                    ],
                },
            ],
        )
        logger.info(f"📋 Lista de planos enviada para usuário ativo {phone}")
    except Exception as e:
        logger.error(f"Erro ao enviar lista interativa para {phone}: {e}")
        # Fallback: texto simples
        await client.send_text(
            phone,
            (
                f"📋 *Planos SuvFin* (seu plano atual: {current_label})\n\n"
                "🟢 *Plano Mensal* — R$ 19,90/mês (registros ilimitados)\n"
                "🏆 *Plano Anual* — R$ 190/ano _(economize 20%!)_\n\n"
                'Envie: _"Quero o Mensal"_ ou _"Quero o Anual"_'
            ),
        )


async def _handle_plan_selection(phone: str, plan_id: str, client: WhatsAppClient) -> None:
    """Processa seleção de plano (via lista interativa ou texto) e gera link de pagamento."""
    # Formato do ID: plan_{tipo}_{periodo}
    parts = plan_id.replace("plan_", "").rsplit("_", 1)
    if len(parts) != 2:
        await client.send_text(phone, "❌ Opção inválida. Tente novamente.")
        return

    plan_key, period_key = parts
    plan_map = {"basico": "BASICO", "pro": "PRO", "premium": "PREMIUM"}
    period_map = {"monthly": "MONTHLY", "annual": "ANNUAL"}

    plan = plan_map.get(plan_key)
    period = period_map.get(period_key)

    if not plan or not period:
        await client.send_text(phone, "❌ Opção inválida. Tente novamente.")
        return

    period_label = "Mensal" if period == "MONTHLY" else "Anual"
    plan_label = "🟢 Plano Mensal" if period == "MONTHLY" else "🏆 Plano Anual"
    price_label = "R$ 19,90/mês" if period == "MONTHLY" else "R$ 190/ano"
    features_monthly = (
        "✅ Tudo do período gratuito\n"
        "✅ Registros ilimitados\n"
        "✅ Relatórios avançados\n"
        "✅ Suporte prioritário\n"
        "✅ Cancele quando quiser"
    )
    features_annual = (
        "✅ Tudo do plano mensal\n"
        "✅ Economia de R$ 48,80/ano\n"
        "✅ Suporte VIP\n"
        "✅ Novos recursos primeiro\n"
        "✅ 2 meses grátis"
    )
    features = features_annual if period == "ANNUAL" else features_monthly

    try:
        license_service = LicenseService()
        payment_url = await license_service.get_payment_link(phone, plan=plan, period=period)

        plan_msg = (
            f"✨ *{plan_label} — {period_label}*\n\n"
            f"💰 *{price_label}*\n\n"
            f"{features}\n\n"
            f"🔗 Assine agora pelo link:\n{payment_url}\n\n"
            f"✅ Após o pagamento, seu plano é ativado automaticamente!"
        )
        await client.send_text(phone, plan_msg)
        logger.info(f"💳 Link gerado para {phone}: {period_label}")
    except Exception as e:
        logger.error(f"Erro ao gerar link para plano {plan}: {e}")
        await client.send_text(
            phone,
            "❌ Erro ao gerar o link de pagamento. Tente novamente em alguns instantes.",
        )


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

    # ── Seleção de plano via lista interativa ──
    # content vem com o ID (ex: "plan_basico_monthly") para msgs interativas
    if msg_type == "interactive" and isinstance(content, str) and content.startswith("plan_"):
        await _handle_plan_selection(phone, content, client)
        return

    # Verificar/criar usuário
    license_service = LicenseService()
    user, is_new_user = await license_service.get_or_create_user(phone, name)

    # Novo usuário — enviar mensagem de boas-vindas
    if is_new_user:
        display_name = name or "usuário"
        expires = user.license_expires_at
        expires_str = expires.strftime("%d/%m/%Y") if expires else "7 dias"
        welcome_msg = (
            f"Olá, {display_name}! 👋\n\n"
            f"🌟 *Bem-vindo(a) ao SuvFin!*\n\n"
            f"Sou seu assistente de finanças pessoais pelo WhatsApp. "
            f"Vou te ajudar a organizar sua vida financeira de forma simples e rápida!\n\n"
            f"🆓 Você ganhou um *período de teste grátis* até *{expires_str}*!\n\n"
            f"O que posso fazer por você:\n"
            f"📝 Registrar gastos e receitas\n"
            f"📊 Gerar relatórios por período e categoria\n"
            f"💰 Mostrar seu saldo atual\n"
            f"📸 Analisar comprovantes por foto\n"
            f"🗑️ Remover e editar lançamentos\n\n"
            f"Experimente agora! Envie algo como:\n"
            f'  _"Gastei 50 reais no almoço"_\n'
            f'  _"Qual meu saldo?"_\n'
            f'  _"Recebi 3000 de salário"_\n\n'
            f"Vamos começar? 🚀"
        )
        await client.send_text(phone, welcome_msg)
        logger.info(f"🌟 Novo usuário trial criado e boas-vindas enviada: {phone}")
        return

    if not user.is_license_valid:
        # Verificar se o usuário está escolhendo um plano por texto
        if msg_type == "text" and isinstance(content, str):
            selected = _detect_plan_selection(content)
            if selected:
                plan, period = selected
                await _handle_plan_selection(phone, f"plan_{plan.lower()}_{period.lower()}", client)
                return

        # Enviar lista interativa de planos
        await _send_plan_list(phone, client)
        return

    # ── Usuário ativo perguntando sobre planos/upgrade ──
    if msg_type == "text" and isinstance(content, str):
        # Usuários com plano pago ativo NÃO recebem link de cobrança.
        # Apenas FREE_TRIAL pode ser encaminhado para seleção de plano.
        from app.models.user import LicenseType as _LicenseType
        is_paid_user = user.license_type in (
            _LicenseType.PRO, _LicenseType.BASICO, _LicenseType.PREMIUM
        )

        if not is_paid_user:
            # Só tenta detectar seleção de plano para usuários não-pagos
            selected = _detect_plan_selection(content)
            if selected:
                plan, period = selected
                await _handle_plan_selection(phone, f"plan_{plan.lower()}_{period.lower()}", client)
                return

        # Checar se está perguntando sobre planos em geral
        # Usuários com plano pago ativo não recebem lista de upgrade —
        # a LLM responde normalmente via MCP com info do plano atual.
        if not is_paid_user and _is_plan_inquiry(content):
            await _send_plan_list_active_user(phone, user, client)
            return

    # ── Dual-write: persistir mensagem do usuário no PostgreSQL ──
    user_content_str = content if isinstance(content, str) else str(content)
    msg_service = MessageService()
    asyncio.create_task(
        msg_service.persist_bot_message(
            user_id=str(user.id),
            content=user_content_str,
            sender_type="user",
            message_type=msg_type if msg_type in ("text", "image", "audio", "document") else "text",
        )
    )

    # Processar com MCP + LLM
    from app.models.user import LicenseType as _LT
    _is_paid = user.license_type in (_LT.PRO, _LT.BASICO, _LT.PREMIUM)
    processor = MCPProcessor()
    response = await processor.process(
        user_id=str(user.id),
        phone=phone,
        message_type=msg_type,
        content=content,
        name=name,
        is_paid_user=_is_paid,
    )

    # Enviar resposta
    await client.send_text(phone, response.text)

    # ── Dual-write: persistir resposta do bot no PostgreSQL ──
    asyncio.create_task(
        msg_service.persist_bot_message(
            user_id=str(user.id),
            content=response.text,
            sender_type="admin",
            message_type="text",
        )
    )

    # Se tiver mídia (gráfico, PDF), enviar
    if response.media and response.media_type:
        if "image" in response.media_type:
            await client.send_image(phone, response.media, caption="📊 Relatório")
        elif "pdf" in response.media_type:
            await client.send_document(
                phone, response.media, "relatorio_suvfin.pdf", caption="📄 Relatório"
            )

    logger.info(f"✅ Resposta enviada para {phone}")
