"""
Cliente HTTP para a API do Pluggy Open Finance.

Documentação: https://docs.pluggy.ai
Base URL: https://api.pluggy.ai
Autenticação: POST /auth com clientId + clientSecret → apiKey (expira 2h)
"""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from app.config.settings import settings
from app.config.redis_client import redis_client

REDIS_API_KEY_KEY = "pluggy:api_key"
REDIS_API_KEY_TTL = 6600  # 1h50 (apiKey expira em 2h)


class PluggyError(Exception):
    """Erro genérico ao chamar a API do Pluggy."""

    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PluggyClient:
    """Cliente async para a REST API do Pluggy."""

    def __init__(self):
        self.base_url = settings.PLUGGY_BASE_URL
        self.client_id = settings.PLUGGY_CLIENT_ID
        self.client_secret = settings.PLUGGY_CLIENT_SECRET
        self.webhook_url = settings.PLUGGY_WEBHOOK_URL

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    async def _get_api_key(self) -> str:
        """Obtém apiKey do cache Redis ou autentica no Pluggy."""
        cached = await redis_client.get(REDIS_API_KEY_KEY)
        if cached:
            return cached

        api_key = await self._authenticate()
        await redis_client.set(REDIS_API_KEY_KEY, api_key, ex=REDIS_API_KEY_TTL)
        return api_key

    async def _authenticate(self) -> str:
        """POST /auth → apiKey (expira 2h)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/auth",
                json={
                    "clientId": self.client_id,
                    "clientSecret": self.client_secret,
                },
            )
            if response.status_code == 200:
                data = response.json()
                api_key = data.get("apiKey")
                if not api_key:
                    raise PluggyError("Pluggy auth retornou sem apiKey", 200, response.text)
                logger.info("🔑 Pluggy API autenticada com sucesso")
                return api_key
            else:
                logger.error(f"❌ Pluggy auth falhou: {response.status_code} — {response.text}")
                raise PluggyError(
                    f"Falha na autenticação Pluggy: {response.status_code}",
                    response.status_code,
                    response.text,
                )

    async def _headers(self) -> dict:
        api_key = await self._get_api_key()
        return {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Requests com retry
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        retries: int = 3,
    ) -> dict:
        """Faz request autenticado com retry em 429."""
        headers = await self._headers()

        for attempt in range(retries):
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    params=params,
                    headers=headers,
                )

            if response.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"⏳ Pluggy rate limit (429), aguardando {wait}s...")
                await asyncio.sleep(wait)
                continue

            if response.status_code == 401:
                # ApiKey expirou, limpar cache e reautenticar
                await redis_client.delete(REDIS_API_KEY_KEY)
                headers = await self._headers()
                continue

            if response.status_code in (200, 201):
                return response.json()

            if response.status_code == 204:
                return {}

            logger.error(
                f"❌ Pluggy {method} {path}: {response.status_code} — {response.text}"
            )
            raise PluggyError(
                f"Pluggy {method} {path} falhou: {response.status_code}",
                response.status_code,
                response.text,
            )

        raise PluggyError(f"Pluggy {method} {path} falhou após {retries} tentativas")

    # ------------------------------------------------------------------
    # Connect Token
    # ------------------------------------------------------------------

    async def create_connect_token(
        self,
        client_user_id: str,
        item_id: Optional[str] = None,
    ) -> str:
        """
        Cria um Connect Token para o Pluggy Connect widget.
        Retorna o accessToken (válido 30min).
        """
        payload: dict = {
            "clientUserId": client_user_id,
        }
        if self.webhook_url:
            payload["webhookUrl"] = self.webhook_url
        if item_id:
            payload["itemId"] = item_id  # Para reconectar item existente

        data = await self._request("POST", "/connect_token", json=payload)
        token = data.get("accessToken")
        if not token:
            raise PluggyError("Pluggy connect_token sem accessToken", 200, str(data))
        logger.info(f"🔗 Connect token criado para user {client_user_id}")
        return token

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def get_item(self, item_id: str) -> dict:
        """GET /items/{id} — Detalhes de um Item (conexão bancária)."""
        return await self._request("GET", f"/items/{item_id}")

    async def delete_item(self, item_id: str) -> dict:
        """DELETE /items/{id} — Desconectar/remover Item."""
        return await self._request("DELETE", f"/items/{item_id}")

    async def update_item(self, item_id: str) -> dict:
        """PATCH /items/{id} — Forçar resync do Item."""
        return await self._request("PATCH", f"/items/{item_id}")

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    async def list_accounts(self, item_id: str) -> list[dict]:
        """GET /accounts?itemId={id} — Lista contas do Item."""
        data = await self._request("GET", "/accounts", params={"itemId": item_id})
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page_size: int = 500,
        page: int = 1,
    ) -> dict:
        """
        GET /transactions — Lista transações de uma conta.
        Retorna dict com 'results', 'total', 'page', 'totalPages'.
        """
        params: dict = {
            "accountId": account_id,
            "pageSize": page_size,
            "page": page,
        }
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to

        return await self._request("GET", "/transactions", params=params)

    async def list_all_transactions(
        self,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Busca todas as transações paginando automaticamente."""
        all_results = []
        page = 1

        while True:
            data = await self.list_transactions(
                account_id=account_id,
                date_from=date_from,
                date_to=date_to,
                page=page,
            )
            results = data.get("results", [])
            all_results.extend(results)

            total_pages = data.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1

        return all_results
