"""
Serviço de sincronização Pluggy → SuvFin.
Importa contas e transações do Pluggy para as tabelas locais.
Gerencia registro/desregistro de conexões e mapeamento de categorias.
"""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config.database import async_session
from app.models.pluggy_connection_config import PluggyConnectionConfig
from app.models.pluggy_item import PluggyItem
from app.models.pluggy_account import PluggyAccount
from app.models.pluggy_transaction import PluggyTransaction
from app.models.category import Category
from app.services.pluggy.client import PluggyClient

# Mapeamento de categorias Pluggy → categorias padrão SuvFin
PLUGGY_CATEGORY_MAP = {
    # Alimentação
    "food": "Alimentação",
    "restaurants": "Alimentação",
    "groceries": "Alimentação",
    "food and drink": "Alimentação",
    # Transporte
    "transportation": "Transporte",
    "travel": "Transporte",
    "gas": "Transporte",
    # Moradia
    "housing": "Moradia",
    "rent": "Moradia",
    "utilities": "Moradia",
    # Saúde
    "health": "Saúde",
    "healthcare": "Saúde",
    "pharmacy": "Saúde",
    # Educação
    "education": "Educação",
    # Lazer
    "entertainment": "Lazer",
    "recreation": "Lazer",
    # Vestuário
    "clothing": "Vestuário",
    "shopping": "Vestuário",
    # Serviços
    "services": "Serviços",
    "bills": "Serviços",
    "subscription": "Serviços",
    # Salário/Renda
    "income": "Salário",
    "salary": "Salário",
    "payroll": "Salário",
    # Investimentos
    "investments": "Investimentos",
    # Transferências e outros
    "transfer": "Outros",
    "other": "Outros",
}


class PluggySyncService:
    """Sincroniza dados do Pluggy com o banco local."""

    def __init__(self):
        self.client = PluggyClient()

    # ------------------------------------------------------------------
    # Gerenciamento de conexões
    # ------------------------------------------------------------------

    async def get_or_create_config(self, user_id: str) -> PluggyConnectionConfig:
        """Obtém ou cria PluggyConnectionConfig para o usuário (default max=2)."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyConnectionConfig).where(
                    PluggyConnectionConfig.user_id == user_id
                )
            )
            config = result.scalar_one_or_none()
            if config:
                return config

            config = PluggyConnectionConfig(user_id=user_id, max_connections=2)
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config

    async def register_connection(self, user_id: str, item_data: dict) -> PluggyItem:
        """Cria PluggyItem e incrementa active_connections."""
        async with async_session() as session:
            # Garantir config existe
            result = await session.execute(
                select(PluggyConnectionConfig).where(
                    PluggyConnectionConfig.user_id == user_id
                )
            )
            config = result.scalar_one_or_none()
            if not config:
                config = PluggyConnectionConfig(user_id=user_id, max_connections=2)
                session.add(config)
                await session.flush()

            # Criar item
            item = PluggyItem(
                user_id=user_id,
                pluggy_item_id=str(item_data.get("id")),
                connector_name=item_data.get("connector", {}).get("name"),
                connector_id=item_data.get("connector", {}).get("id"),
                status=item_data.get("status", "UPDATING"),
                connected_at=datetime.utcnow(),
            )
            session.add(item)

            # Incrementar active_connections
            config.active_connections = config.active_connections + 1
            await session.commit()
            await session.refresh(item)
            logger.info(
                f"🏦 Conexão registrada: user={user_id}, "
                f"item={item.pluggy_item_id}, banco={item.connector_name}"
            )
            return item

    async def unregister_connection(self, user_id: str, pluggy_item_id: str) -> None:
        """Desativa PluggyItem e decrementa active_connections."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(
                    PluggyItem.pluggy_item_id == pluggy_item_id,
                    PluggyItem.user_id == user_id,
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            item.is_active = False
            item.disconnected_at = datetime.utcnow()

            # Decrementar config
            result = await session.execute(
                select(PluggyConnectionConfig).where(
                    PluggyConnectionConfig.user_id == user_id
                )
            )
            config = result.scalar_one_or_none()
            if config and config.active_connections > 0:
                config.active_connections = config.active_connections - 1

            await session.commit()
            logger.info(f"🔌 Conexão desregistrada: item={pluggy_item_id}")

    # ------------------------------------------------------------------
    # Sync completo de um Item
    # ------------------------------------------------------------------

    async def sync_item(self, pluggy_item_id: str) -> None:
        """Sincroniza contas e transações de um Item do Pluggy."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(
                    PluggyItem.pluggy_item_id == pluggy_item_id,
                    PluggyItem.is_active.is_(True),
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                logger.warning(f"⚠️ Item {pluggy_item_id} não encontrado ou inativo")
                return

        # Buscar dados atualizados do Pluggy
        try:
            item_data = await self.client.get_item(pluggy_item_id)
        except Exception as e:
            logger.error(f"❌ Erro ao buscar item {pluggy_item_id}: {e}")
            return

        # Atualizar status do item local
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(PluggyItem.pluggy_item_id == pluggy_item_id)
            )
            item = result.scalar_one_or_none()
            if item:
                item.status = item_data.get("status", item.status)
                item.last_sync_at = datetime.utcnow()
                if item_data.get("consentExpiresAt"):
                    try:
                        item.consent_expires_at = datetime.fromisoformat(
                            item_data["consentExpiresAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass
                await session.commit()

        # Importar contas (apenas tipo BANK)
        try:
            accounts_data = await self.client.list_accounts(pluggy_item_id)
            bank_accounts = [a for a in accounts_data if a.get("type") == "BANK"]
            await self._import_accounts(pluggy_item_id, bank_accounts)
        except Exception as e:
            logger.error(f"❌ Erro ao importar contas: {e}")
            return

        # Importar transações de cada conta
        async with async_session() as session:
            result = await session.execute(
                select(PluggyAccount).where(
                    PluggyAccount.pluggy_item_id == (
                        select(PluggyItem.id).where(
                            PluggyItem.pluggy_item_id == pluggy_item_id
                        ).scalar_subquery()
                    )
                )
            )
            accounts = result.scalars().all()

        for account in accounts:
            try:
                transactions = await self.client.list_all_transactions(
                    account.pluggy_account_id
                )
                await self._import_transactions(account, transactions)
            except Exception as e:
                logger.error(
                    f"❌ Erro ao importar transações da conta "
                    f"{account.pluggy_account_id}: {e}"
                )

        logger.info(f"✅ Sync completo do item {pluggy_item_id}")

    # ------------------------------------------------------------------
    # Import contas
    # ------------------------------------------------------------------

    async def _import_accounts(
        self, pluggy_item_id: str, accounts_data: list[dict]
    ) -> None:
        """Cria ou atualiza PluggyAccounts a partir dos dados do Pluggy."""
        async with async_session() as session:
            # Buscar item local
            result = await session.execute(
                select(PluggyItem).where(PluggyItem.pluggy_item_id == pluggy_item_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            for acc in accounts_data:
                pluggy_account_id = str(acc.get("id"))
                bank_data = acc.get("bankData") or {}

                # Upsert
                stmt = pg_insert(PluggyAccount).values(
                    pluggy_item_id=item.id,
                    pluggy_account_id=pluggy_account_id,
                    user_id=item.user_id,
                    name=acc.get("name"),
                    type=acc.get("type", "BANK"),
                    subtype=acc.get("subtype"),
                    number=bank_data.get("number"),
                    balance=acc.get("balance"),
                    currency_code=acc.get("currencyCode", "BRL"),
                ).on_conflict_do_update(
                    index_elements=["pluggy_account_id"],
                    set_={
                        "name": acc.get("name"),
                        "balance": acc.get("balance"),
                        "subtype": acc.get("subtype"),
                        "number": bank_data.get("number"),
                        "currency_code": acc.get("currencyCode", "BRL"),
                        "updated_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)

            await session.commit()
            logger.info(
                f"📋 {len(accounts_data)} conta(s) importada(s) para item {pluggy_item_id}"
            )

    # ------------------------------------------------------------------
    # Import transações
    # ------------------------------------------------------------------

    async def _import_transactions(
        self, account: PluggyAccount, transactions_data: list[dict]
    ) -> None:
        """Upsert de transações do Pluggy para a tabela local."""
        if not transactions_data:
            return

        # Pré-carregar mapeamento de categorias
        category_cache = await self._load_category_cache()

        async with async_session() as session:
            for tx in transactions_data:
                pluggy_tx_id = str(tx.get("id"))
                pluggy_category = tx.get("category") or ""
                suvfin_category_id = self._map_category(pluggy_category, category_cache)

                # Extrair payment method
                payment_data = tx.get("paymentData") or {}
                payment_method = payment_data.get("paymentMethod")

                stmt = pg_insert(PluggyTransaction).values(
                    pluggy_account_id=account.id,
                    user_id=account.user_id,
                    pluggy_transaction_id=pluggy_tx_id,
                    description=tx.get("description"),
                    description_raw=tx.get("descriptionRaw"),
                    amount=tx.get("amount", 0),
                    date=tx.get("date", "")[:10],  # YYYY-MM-DD
                    type=tx.get("type", "DEBIT"),
                    status=tx.get("status", "POSTED"),
                    category=pluggy_category,
                    category_id=suvfin_category_id,
                    payment_method=payment_method,
                    currency_code=tx.get("currencyCode", "BRL"),
                ).on_conflict_do_update(
                    index_elements=["pluggy_transaction_id"],
                    set_={
                        "description": tx.get("description"),
                        "amount": tx.get("amount", 0),
                        "status": tx.get("status", "POSTED"),
                        "category": pluggy_category,
                        "category_id": suvfin_category_id,
                        "payment_method": payment_method,
                    },
                )
                await session.execute(stmt)

            await session.commit()
            logger.info(
                f"💳 {len(transactions_data)} transação(ões) importada(s) "
                f"para conta {account.pluggy_account_id}"
            )

    async def handle_deleted_transactions(self, transaction_ids: list[str]) -> None:
        """Remove transações deletadas pelo Pluggy."""
        if not transaction_ids:
            return
        async with async_session() as session:
            for tx_id in transaction_ids:
                result = await session.execute(
                    select(PluggyTransaction).where(
                        PluggyTransaction.pluggy_transaction_id == tx_id
                    )
                )
                tx = result.scalar_one_or_none()
                if tx:
                    await session.delete(tx)
            await session.commit()
            logger.info(f"🗑️ {len(transaction_ids)} transação(ões) removida(s)")

    async def handle_updated_transactions(self, transaction_ids: list[str]) -> None:
        """Re-importa transações atualizadas buscando dados frescos do Pluggy."""
        if not transaction_ids:
            return

        async with async_session() as session:
            for tx_id in transaction_ids:
                result = await session.execute(
                    select(PluggyTransaction).where(
                        PluggyTransaction.pluggy_transaction_id == tx_id
                    )
                )
                tx = result.scalar_one_or_none()
                if not tx:
                    continue

                # Buscar account para obter o pluggy_account_id
                result = await session.execute(
                    select(PluggyAccount).where(PluggyAccount.id == tx.pluggy_account_id)
                )
                account = result.scalar_one_or_none()
                if not account:
                    continue

        # Re-sync inteiro da conta é mais eficiente para batches
        # mas para poucos updates, buscamos individualmente
        # Neste caso, dispara sync completo do item
        if transaction_ids:
            async with async_session() as session:
                result = await session.execute(
                    select(PluggyTransaction).where(
                        PluggyTransaction.pluggy_transaction_id == transaction_ids[0]
                    )
                )
                tx = result.scalar_one_or_none()
                if tx:
                    result = await session.execute(
                        select(PluggyAccount).where(PluggyAccount.id == tx.pluggy_account_id)
                    )
                    account = result.scalar_one_or_none()
                    if account:
                        result = await session.execute(
                            select(PluggyItem).where(PluggyItem.id == account.pluggy_item_id)
                        )
                        item = result.scalar_one_or_none()
                        if item:
                            # Re-importar transações da conta
                            transactions = await self.client.list_all_transactions(
                                account.pluggy_account_id
                            )
                            await self._import_transactions(account, transactions)

    # ------------------------------------------------------------------
    # Buscar transações criadas via link da notificação
    # ------------------------------------------------------------------

    async def import_created_transactions(self, pluggy_item_id: str) -> None:
        """Importa novas transações de todas as contas de um item."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(
                    PluggyItem.pluggy_item_id == pluggy_item_id,
                    PluggyItem.is_active.is_(True),
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            result = await session.execute(
                select(PluggyAccount).where(PluggyAccount.pluggy_item_id == item.id)
            )
            accounts = result.scalars().all()

        for account in accounts:
            try:
                transactions = await self.client.list_all_transactions(
                    account.pluggy_account_id
                )
                await self._import_transactions(account, transactions)
            except Exception as e:
                logger.error(f"❌ Erro importando transações criadas: {e}")

    # ------------------------------------------------------------------
    # Atualizar status do item
    # ------------------------------------------------------------------

    async def update_item_status(self, pluggy_item_id: str, status: str) -> None:
        """Atualiza o status de um PluggyItem."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(PluggyItem.pluggy_item_id == pluggy_item_id)
            )
            item = result.scalar_one_or_none()
            if item:
                item.status = status
                item.updated_at = datetime.utcnow()
                await session.commit()

    # ------------------------------------------------------------------
    # Mapeamento de categorias
    # ------------------------------------------------------------------

    async def _load_category_cache(self) -> dict[str, str]:
        """Carrega todas as categorias default e retorna {nome_lower: id}."""
        async with async_session() as session:
            result = await session.execute(
                select(Category).where(Category.is_default.is_(True))
            )
            categories = result.scalars().all()
            return {cat.name.lower(): str(cat.id) for cat in categories}

    def _map_category(
        self, pluggy_category: str, category_cache: dict[str, str]
    ) -> Optional[str]:
        """Mapeia categoria do Pluggy para category_id do SuvFin."""
        if not pluggy_category:
            return None

        cat_lower = pluggy_category.lower().strip()

        # Match direto no mapa
        suvfin_name = PLUGGY_CATEGORY_MAP.get(cat_lower)
        if suvfin_name:
            return category_cache.get(suvfin_name.lower())

        # Match parcial: se alguma chave está contida na categoria Pluggy
        for key, suvfin_name in PLUGGY_CATEGORY_MAP.items():
            if key in cat_lower:
                return category_cache.get(suvfin_name.lower())

        return category_cache.get("outros")

    # ------------------------------------------------------------------
    # Queries de leitura (usadas pelos MCP tools)
    # ------------------------------------------------------------------

    async def get_user_items(self, user_id: str) -> list[PluggyItem]:
        """Lista items ativos de um usuário."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(
                    PluggyItem.user_id == user_id,
                    PluggyItem.is_active.is_(True),
                )
            )
            return result.scalars().all()

    async def get_user_accounts(self, user_id: str) -> list[PluggyAccount]:
        """Lista contas bancárias de um usuário."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyAccount)
                .join(PluggyItem, PluggyAccount.pluggy_item_id == PluggyItem.id)
                .where(
                    PluggyAccount.user_id == user_id,
                    PluggyItem.is_active.is_(True),
                )
            )
            return result.scalars().all()

    async def get_user_transactions(
        self,
        user_id: str,
        account_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
    ) -> list[PluggyTransaction]:
        """Lista transações importadas do usuário, com filtros opcionais."""
        async with async_session() as session:
            query = (
                select(PluggyTransaction)
                .where(PluggyTransaction.user_id == user_id)
                .order_by(PluggyTransaction.date.desc(), PluggyTransaction.created_at.desc())
            )

            if account_id:
                query = query.where(PluggyTransaction.pluggy_account_id == account_id)

            if date_from:
                query = query.where(PluggyTransaction.date >= date_from)

            if date_to:
                query = query.where(PluggyTransaction.date <= date_to)

            query = query.limit(limit)
            result = await session.execute(query)
            return result.scalars().all()

    async def get_item_by_connector_name(
        self, user_id: str, bank_name: str
    ) -> Optional[PluggyItem]:
        """Busca item ativo por nome do banco (match parcial, case-insensitive)."""
        async with async_session() as session:
            result = await session.execute(
                select(PluggyItem).where(
                    PluggyItem.user_id == user_id,
                    PluggyItem.is_active.is_(True),
                    PluggyItem.connector_name.ilike(f"%{bank_name}%"),
                )
            )
            return result.scalar_one_or_none()
