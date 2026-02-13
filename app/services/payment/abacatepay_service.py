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

    async def create_premium_billing(
        self,
        user_id: str,
        user_phone: str,
        customer_id: Optional[str] = None,
        customer_data: Optional[dict] = None,
    ) -> dict:
        """
        Cria cobrança para upgrade Premium do SuvFin.
        Retorna o dict da cobrança com a URL de pagamento.
        """
        return await self.create_billing(
            product_external_id=f"suvfin-premium-{user_id}",
            product_name="SuvFin Premium",
            product_description=(
                "Plano Premium SuvFin — Lançamentos ilimitados, "
                "relatórios avançados e suporte prioritário."
            ),
            quantity=1,
            price_cents=settings.PREMIUM_PRICE_CENTS,
            return_url=f"{settings.APP_URL}/upgrade?phone={user_phone}",
            completion_url=f"{settings.APP_URL}/upgrade/sucesso?phone={user_phone}",
            customer_id=customer_id,
            customer=customer_data,
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
