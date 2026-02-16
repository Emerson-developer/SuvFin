"""
Rotas de pagamento — Integração com AbacatePay.

Endpoints:
  POST /payment/create-link  — Gera link de pagamento PIX (Básico, Pro, Premium)
  POST /payment/webhook      — Recebe notificações do AbacatePay (pagamento confirmado)
  GET  /payment/status/{phone} — Consulta status de pagamento de um usuário
"""

from datetime import datetime

from fastapi import APIRouter, Request, Query, HTTPException
from loguru import logger
from sqlalchemy import select

from app.config.database import async_session
from app.config.settings import settings
from app.models.user import User, LicenseType
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import (
    CreateBillingRequest,
    CreateBillingResponse,
    PaymentStatusResponse,
)
from app.services.payment.abacatepay_service import AbacatePayService, AbacatePayError
from app.services.license.license_service import LicenseService
from app.services.whatsapp.client import WhatsAppClient

router = APIRouter(prefix="/payment", tags=["payment"])

# Router separado para o webhook externo do AbacatePay
# O AbacatePay envia para /webhooks/abacatepay?webhookSecret=<secret>
webhook_router = APIRouter(tags=["payment"])


@router.post("/create-link", response_model=CreateBillingResponse)
async def create_payment_link(body: CreateBillingRequest):
    """
    Gera link de pagamento PIX para upgrade de plano.

    Planos: BASICO (R$9,90), PRO (R$19,90), PREMIUM (R$34,90)
    Períodos: MONTHLY ou ANNUAL (-20%)
    """
    plan = body.plan.upper()
    period = body.period.upper()

    if plan not in ("BASICO", "PRO", "PREMIUM"):
        raise HTTPException(status_code=400, detail="Plano inválido. Use: BASICO, PRO ou PREMIUM")
    if period not in ("MONTHLY", "ANNUAL"):
        raise HTTPException(status_code=400, detail="Período inválido. Use: MONTHLY ou ANNUAL")

    license_service = LicenseService()
    user, _ = await license_service.get_or_create_user(body.phone, body.name)

    # Verificar se já existe cobrança pendente para o mesmo plano
    async with async_session() as session:
        stmt = select(Payment).where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.PENDING,
        )
        result = await session.execute(stmt)
        existing_payment = result.scalar_one_or_none()

        if existing_payment and existing_payment.payment_url:
            logger.info(f"Cobrança pendente existente para {body.phone}")
            return CreateBillingResponse(
                billing_id=existing_payment.abacatepay_billing_id,
                payment_url=existing_payment.payment_url,
                amount_cents=existing_payment.amount_cents,
                status="PENDING",
                plan=existing_payment.plan_type or "PRO",
                period=existing_payment.billing_period or "MONTHLY",
                message="Você já tem um pagamento pendente. Use o link abaixo:",
            )

    # Montar dados do cliente para AbacatePay
    customer_data = None
    if body.email and body.name and body.tax_id:
        customer_data = {
            "name": body.name,
            "cellphone": body.phone,
            "email": body.email,
            "taxId": body.tax_id,
        }

    # Criar cobrança no AbacatePay
    try:
        abacatepay = AbacatePayService()
        price_cents = abacatepay.get_plan_price(plan, period)
        billing = await abacatepay.create_plan_billing(
            user_id=str(user.id),
            user_phone=body.phone,
            plan=plan,
            period=period,
            customer_data=customer_data,
        )
    except AbacatePayError as e:
        logger.error(f"Erro AbacatePay ao criar cobrança: {e}")
        raise HTTPException(
            status_code=502,
            detail="Erro ao gerar link de pagamento. Tente novamente.",
        )

    # Salvar cobrança no banco local
    async with async_session() as session:
        payment = Payment(
            user_id=user.id,
            abacatepay_billing_id=billing.get("id", ""),
            abacatepay_customer_id=billing.get("customer", {}).get("id") if billing.get("customer") else None,
            amount_cents=price_cents,
            plan_type=plan,
            billing_period=period,
            status=PaymentStatus.PENDING,
            payment_url=billing.get("url", ""),
        )
        session.add(payment)
        await session.commit()

    period_label = "mensal" if period == "MONTHLY" else "anual"
    logger.info(
        f"✅ Link criado para {body.phone}: {plan} {period_label} — {billing.get('url')}"
    )

    return CreateBillingResponse(
        billing_id=billing.get("id", ""),
        payment_url=billing.get("url", ""),
        amount_cents=price_cents,
        status="PENDING",
        plan=plan,
        period=period,
        message=f"Link de pagamento {plan} ({period_label}) criado! Pague via PIX:",
    )


@router.post("/webhook")
@webhook_router.post("/webhooks/abacatepay")
async def abacatepay_webhook(
    request: Request,
    webhookSecret: str = Query(None, alias="webhookSecret"),
):
    """
    Webhook do AbacatePay — recebe notificações de pagamento.

    O AbacatePay envia o secret como query string: ?webhookSecret=<secret>
    e o payload com os dados da cobrança atualizada.
    """
    # 1. Verificar secret
    abacatepay = AbacatePayService()
    if not abacatepay.verify_webhook_secret(webhookSecret or ""):
        logger.warning(f"❌ Webhook AbacatePay com secret inválido: {webhookSecret}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2. Parsear payload
    try:
        payload = await request.json()
        logger.info(f"🥑 Webhook AbacatePay recebido: {payload}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # O payload contém os dados da cobrança (billing)
    # Estrutura: { "event": "billing.paid", "data": { "billing": { "id": "...", ... } } }
    data = payload.get("data", {})
    billing_data = data.get("billing", data) if isinstance(data, dict) else {}
    billing_id = billing_data.get("id", "")
    billing_status = billing_data.get("status", "")

    # Fallback: tentar pegar do nível superior se não achou
    if not billing_id:
        billing_id = data.get("id", "") or payload.get("id", "")
    if not billing_status:
        billing_status = data.get("status", "") or payload.get("status", "")

    if not billing_id:
        logger.warning("Webhook sem billing ID")
        return {"status": "ignored"}

    # Usar o tipo de evento como sinal de pagamento confirmado
    event_type = payload.get("event", "")
    if event_type == "billing.paid" and billing_status not in ("PAID",):
        logger.info(
            f"🥑 Evento '{event_type}' com status '{billing_status}' — "
            f"tratando como PAID"
        )
        billing_status = "PAID"

    logger.info(f"🥑 Cobrança {billing_id} → status: {billing_status} (event: {event_type})")

    # 3. Buscar pagamento local
    async with async_session() as session:
        stmt = select(Payment).where(
            Payment.abacatepay_billing_id == billing_id
        )
        result = await session.execute(stmt)
        payment = result.scalar_one_or_none()

        if not payment:
            # Pagamento não existe localmente — provavelmente criado direto no AbacatePay
            # Tentar criar usuário e pagamento a partir dos dados do webhook
            customer_data = billing_data.get("customer", {}) or data.get("customer", {}) or {}
            metadata = customer_data.get("metadata", {}) or billing_data.get("metadata", {}) or {}

            customer_phone = (
                customer_data.get("cellphone", "")
                or metadata.get("cellphone", "")
                or metadata.get("phone", "")
            )
            customer_name = customer_data.get("name", "") or metadata.get("name", "")
            customer_id = customer_data.get("id", "")
            amount = billing_data.get("amount") or data.get("amount") or settings.PREMIUM_PRICE_CENTS

            if not customer_phone:
                logger.warning(
                    f"Webhook sem billing local e sem telefone do cliente. "
                    f"billing_id={billing_id}, payload={payload}"
                )
                return {"status": "not_found", "reason": "no_phone"}

            # Normalizar telefone
            customer_phone = (
                customer_phone.replace(" ", "").replace("-", "")
                .replace("(", "").replace(")", "")
            )
            if not customer_phone.startswith("55") and len(customer_phone) <= 11:
                customer_phone = f"55{customer_phone}"

            logger.info(
                f"🆕 Criando usuário/pagamento via webhook direto. "
                f"phone={customer_phone}, name={customer_name}, billing={billing_id}"
            )

            # Criar ou buscar usuário
            license_service = LicenseService()
            user, _ = await license_service.get_or_create_user(
                phone=customer_phone,
                name=customer_name or "Usuário AbacatePay",
            )

            # Criar registro de pagamento
            payment = Payment(
                user_id=user.id,
                abacatepay_billing_id=billing_id,
                abacatepay_customer_id=customer_id or None,
                amount_cents=int(amount) if amount else settings.PREMIUM_PRICE_CENTS,
                status=PaymentStatus.PENDING,
                payment_url="",
            )
            session.add(payment)
            await session.flush()

            logger.info(f"✅ Pagamento criado via webhook: user={customer_phone}, billing={billing_id}")

        # 4. Atualizar status do pagamento
        old_status = payment.status
        new_status = _map_billing_status(billing_status)
        payment.status = new_status
        payment.updated_at = datetime.utcnow()

        if new_status == PaymentStatus.PAID and old_status != PaymentStatus.PAID:
            payment.paid_at = datetime.utcnow()

            # 5. Fazer upgrade do usuário para o plano pago
            plan_type = payment.plan_type or "PRO"
            billing_period = payment.billing_period or "MONTHLY"
            license_service = LicenseService()
            success = await license_service.upgrade_to_plan(
                user_id=str(payment.user_id),
                plan=plan_type,
                period=billing_period,
            )

            plan_names = {"BASICO": "Básico", "PRO": "Pro", "PREMIUM": "Premium"}
            plan_display = plan_names.get(plan_type, plan_type)

            if success:
                logger.info(f"🎉 Upgrade {plan_display} confirmado via pagamento {billing_id}")

                # 6. Notificar usuário via WhatsApp
                user_stmt = select(User).where(User.id == payment.user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()

                if user:
                    try:
                        client = WhatsAppClient()
                        await client.send_text(
                            user.phone,
                            f"🎉 *Pagamento confirmado!*\n\n"
                            f"Seu plano foi atualizado para *{plan_display}*! 🚀\n\n"
                            f"Obrigado por escolher o SuvFin! 💚🥑",
                        )
                    except Exception as e:
                        logger.error(f"Erro ao notificar usuário: {e}")
            else:
                logger.error(f"Falha ao fazer upgrade para billing: {billing_id}")

        await session.commit()

    return {"status": "processed", "billing_id": billing_id}


@router.get("/status/{phone}", response_model=PaymentStatusResponse)
async def get_payment_status(phone: str):
    """Consulta o status de pagamento/licença de um usuário pelo telefone."""
    async with async_session() as session:
        user_stmt = select(User).where(User.phone == phone)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        # Buscar último pagamento
        payment_stmt = (
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        payment_result = await session.execute(payment_stmt)
        last_payment = payment_result.scalar_one_or_none()

        return PaymentStatusResponse(
            user_phone=user.phone,
            license_type=user.license_type.value,
            is_premium=user.license_type in (LicenseType.BASICO, LicenseType.PRO, LicenseType.PREMIUM),
            plan=last_payment.plan_type if last_payment else None,
            period=last_payment.billing_period if last_payment else None,
            billing_id=last_payment.abacatepay_billing_id if last_payment else None,
            billing_status=last_payment.status.value if last_payment else None,
        )


def _map_billing_status(status: str) -> PaymentStatus:
    """Mapeia o status do AbacatePay para o PaymentStatus local."""
    mapping = {
        "PENDING": PaymentStatus.PENDING,
        "PAID": PaymentStatus.PAID,
        "ACTIVE": PaymentStatus.PAID,  # AbacatePay envia ACTIVE quando pago
        "COMPLETED": PaymentStatus.PAID,
        "EXPIRED": PaymentStatus.EXPIRED,
        "CANCELLED": PaymentStatus.CANCELLED,
        "REFUNDED": PaymentStatus.REFUNDED,
    }
    return mapping.get(status, PaymentStatus.PENDING)
