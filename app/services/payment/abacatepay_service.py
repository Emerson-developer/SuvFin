"""
Serviço de integração com o AbacatePay — Gateway de pagamento PIX.

Documentação: https://abacatepay.readme.io/reference
Base URL: https://api.abacatepay.com/v1
Autenticação: Bearer token no header Authorization
"""

from typing import Optional

import httpx
from loguru import logger

from app.config.settings import settings


class AbacatePayService:
    """Cliente para a API do AbacatePay."""

    BASE_URL = "https://api.abacatepay.com/v1"

    def __init__(self):
        self.api_key = settings.ABACATEPAY_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    async def create_customer(
        self,
        name: str,
        cellphone: str,
        email: str,
        tax_id: str,
    ) -> dict:
        """
        Cria um novo cliente no AbacatePay.

        POST /customer/create
        Body: { name, cellphone, email, taxId }
        """
        payload = {
            "name": name,
            "cellphone": cellphone,
            "email": email,
            "taxId": tax_id,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.BASE_URL}/customer/create",
                json=payload,
                headers=self.headers,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"🥑 Cliente criado no AbacatePay: {data.get('data', {}).get('id')}")
                return data.get("data", {})
            else:
                logger.error(
                    f"❌ Erro ao criar cliente AbacatePay: "
                    f"{response.status_code} — {response.text}"
                )
                raise AbacatePayError(
                    f"Falha ao criar cliente: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

    async def list_customers(self) -> list[dict]:
        """
        Lista todos os clientes cadastrados.

        GET /customer/list
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE_URL}/customer/list",
                headers=self.headers,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.error(f"❌ Erro ao listar clientes: {response.status_code}")
                raise AbacatePayError(
                    f"Falha ao listar clientes: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

    # ------------------------------------------------------------------
    # Cobranças (Billing)
    # ------------------------------------------------------------------

    async def create_billing(
        self,
        product_external_id: str,
        product_name: str,
        product_description: str,
        quantity: int,
        price_cents: int,
        return_url: str,
        completion_url: str,
        customer_id: Optional[str] = None,
        customer: Optional[dict] = None,
    ) -> dict:
        """
        Cria uma nova cobrança PIX no AbacatePay.

        POST /billing/create
        Body:
          - frequency: "ONE_TIME" (único suportado)
          - methods: ["PIX"] (único suportado)
          - products: [{ externalId, name, description, quantity, price }]
          - returnUrl, completionUrl
          - customerId ou customer
        """
        payload = {
            "frequency": "ONE_TIME",
            "methods": ["PIX"],
            "products": [
                {
                    "externalId": product_external_id,
                    "name": product_name,
                    "description": product_description,
                    "quantity": quantity,
                    "price": price_cents,  # em centavos (mínimo 100 = R$1,00)
                }
            ],
            "returnUrl": return_url,
            "completionUrl": completion_url,
        }

        if customer_id:
            payload["customerId"] = customer_id
        elif customer:
            payload["customer"] = customer

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.BASE_URL}/billing/create",
                json=payload,
                headers=self.headers,
            )

            if response.status_code == 200:
                data = response.json()
                billing = data.get("data", {})
                logger.info(
                    f"🥑 Cobrança criada: {billing.get('id')} — "
                    f"R$ {price_cents / 100:.2f} — URL: {billing.get('url')}"
                )
                return billing
            else:
                logger.error(
                    f"❌ Erro ao criar cobrança AbacatePay: "
                    f"{response.status_code} — {response.text}"
                )
                raise AbacatePayError(
                    f"Falha ao criar cobrança: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

    async def list_billings(self) -> list[dict]:
        """
        Lista todas as cobranças.

        GET /billing/list
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE_URL}/billing/list",
                headers=self.headers,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.error(f"❌ Erro ao listar cobranças: {response.status_code}")
                raise AbacatePayError(
                    f"Falha ao listar cobranças: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

    # ------------------------------------------------------------------
    # Webhook helpers
    # ------------------------------------------------------------------

    def verify_webhook_secret(self, received_secret: str) -> bool:
        """
        Verifica se o secret recebido no webhook (query string) é válido.

        O AbacatePay envia o secret como: ?webhookSecret=<secret>
        """
        return received_secret == settings.ABACATEPAY_WEBHOOK_SECRET

    # ------------------------------------------------------------------
    # Métodos de conveniência
    # ------------------------------------------------------------------

    # Nomes e descrições dos planos
    PLAN_INFO = {
        "BASICO": {
            "name": "SuvFin Básico",
            "description": (
                "Plano Básico SuvFin — Registro de despesas e receitas, "
                "relatórios mensais básicos, até 100 transações/mês."
            ),
        },
        "PRO": {
            "name": "SuvFin Pro",
            "description": (
                "Plano Pro SuvFin — Transações ilimitadas, relatórios detalhados, "
                "alertas de gastos, metas financeiras e exportação CSV/PDF."
            ),
        },
        "PREMIUM": {
            "name": "SuvFin Premium",
            "description": (
                "Plano Premium SuvFin — Tudo do Pro + análise preditiva, "
                "consultoria por IA, múltiplas contas e suporte 24/7."
            ),
        },
    }

    def get_plan_price(self, plan: str, period: str) -> int:
        """Retorna o preço em centavos para o plano e período."""
        prices = {
            ("BASICO", "MONTHLY"): settings.PLAN_BASICO_MONTHLY_CENTS,
            ("BASICO", "ANNUAL"): settings.PLAN_BASICO_ANNUAL_CENTS,
            ("PRO", "MONTHLY"): settings.PLAN_PRO_MONTHLY_CENTS,
            ("PRO", "ANNUAL"): settings.PLAN_PRO_ANNUAL_CENTS,
            ("PREMIUM", "MONTHLY"): settings.PLAN_PREMIUM_MONTHLY_CENTS,
            ("PREMIUM", "ANNUAL"): settings.PLAN_PREMIUM_ANNUAL_CENTS,
        }
        return prices.get((plan.upper(), period.upper()), settings.PLAN_PRO_MONTHLY_CENTS)

    async def create_plan_billing(
        self,
        user_id: str,
        user_phone: str,
        plan: str = "PRO",
        period: str = "MONTHLY",
        customer_id: Optional[str] = None,
        customer_data: Optional[dict] = None,
    ) -> dict:
        """
        Cria cobrança para qualquer plano do SuvFin.
        plan: BASICO, PRO ou PREMIUM
        period: MONTHLY ou ANNUAL
        """
        plan = plan.upper()
        period = period.upper()
        info = self.PLAN_INFO.get(plan, self.PLAN_INFO["PRO"])
        price = self.get_plan_price(plan, period)
        period_label = "Mensal" if period == "MONTHLY" else "Anual"

        # Garantir URL válida para o AbacatePay
        base_url = settings.APP_URL.rstrip("/")
        if not base_url or not base_url.startswith("http"):
            base_url = "https://suvfin-production.up.railway.app"

        return await self.create_billing(
            product_external_id=f"suvfin-{plan.lower()}-{period.lower()}-{user_id}",
            product_name=f"{info['name']} ({period_label})",
            product_description=info["description"],
            quantity=1,
            price_cents=price,
            return_url=f"{base_url}/upgrade?phone={user_phone}",
            completion_url=f"{base_url}/upgrade/sucesso?phone={user_phone}",
            customer_id=customer_id,
            customer=customer_data,
        )

    async def create_premium_billing(
        self,
        user_id: str,
        user_phone: str,
        plan: str = "PRO",
        period: str = "MONTHLY",
        customer_id: Optional[str] = None,
        customer_data: Optional[dict] = None,
    ) -> dict:
        """Legado: redireciona para create_plan_billing."""
        return await self.create_plan_billing(
            user_id=user_id,
            user_phone=user_phone,
            plan=plan,
            period=period,
            customer_id=customer_id,
            customer_data=customer_data,
        )


class AbacatePayError(Exception):
    """Erro na comunicação com o AbacatePay."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
