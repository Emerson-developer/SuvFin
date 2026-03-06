"""
Serviço de dashboard — queries agregadas para o painel admin.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_, desc, text

from app.config.database import async_session
from app.models.user import User
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.conversation import Conversation
from app.models.message import Message


class DashboardService:
    """Agregações para o dashboard admin."""

    async def get_stats(self) -> dict:
        """
        Retorna todas as métricas do dashboard em uma única query batch.
        """
        async with async_session() as session:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            two_days_ago = now - timedelta(days=2)
            seven_days_ago = now - timedelta(days=7)

            # --- Contatos ---
            total_contacts_r = await session.execute(
                select(func.count(User.id))
            )
            total_contacts = total_contacts_r.scalar() or 0

            active_contacts_r = await session.execute(
                select(func.count(User.id)).where(User.is_active.is_(True))
            )
            active_contacts = active_contacts_r.scalar() or 0

            # --- Conversas abertas ---
            open_convs_r = await session.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.status == "open"
                )
            )
            open_conversations = open_convs_r.scalar() or 0

            # --- Mensagens hoje ---
            msgs_today_r = await session.execute(
                select(func.count(Message.id)).where(
                    Message.created_at >= today_start
                )
            )
            messages_today = msgs_today_r.scalar() or 0

            # --- Subscriptions por status ---
            past_due_r = await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "past_due"
                )
            )
            past_due_subscriptions = past_due_r.scalar() or 0

            trial_r = await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "trial"
                )
            )
            trial_subscriptions = trial_r.scalar() or 0

            # --- Distribuição por plano ---
            plan_dist_r = await session.execute(
                select(
                    Plan.id,
                    Plan.name,
                    func.count(Subscription.id).label("count"),
                )
                .outerjoin(Subscription, Subscription.plan_id == Plan.id)
                .where(Plan.is_active.is_(True))
                .group_by(Plan.id, Plan.name)
            )
            plan_distribution = [
                {
                    "plan_id": str(row[0]),
                    "plan_name": row[1],
                    "count": row[2],
                }
                for row in plan_dist_r.all()
            ]

            # --- Contatos inativos ---
            inactive_contacts = await self._get_inactive_contacts(
                session, two_days_ago, seven_days_ago
            )

            # --- Conversas abertas recentes (top 5) ---
            recent_open = await self._get_recent_open_conversations(
                session, two_days_ago, 5
            )

            return {
                "total_contacts": total_contacts,
                "active_contacts": active_contacts,
                "open_conversations": open_conversations,
                "messages_today": messages_today,
                "past_due_subscriptions": past_due_subscriptions,
                "trial_subscriptions": trial_subscriptions,
                "plan_distribution": plan_distribution,
                "inactive_contacts": inactive_contacts,
                "recent_open_conversations": recent_open,
            }

    async def _get_inactive_contacts(
        self, session, two_days_ago: datetime, seven_days_ago: datetime,
    ) -> list[dict]:
        """
        Contatos ativos cuja última mensagem do user é > 2 dias atrás ou nunca.
        """
        # Using raw SQL for the FILTER clause which is PostgreSQL-specific
        stmt = text("""
            SELECT
                u.id AS contact_id,
                u.name,
                u.avatar_url,
                MAX(m.created_at) FILTER (WHERE m.sender_type = 'user') AS last_user_message_at
            FROM users u
            LEFT JOIN conversations conv ON conv.user_id = u.id
            LEFT JOIN messages m ON m.conversation_id = conv.id
            WHERE u.is_active = true
            GROUP BY u.id, u.name, u.avatar_url
            HAVING
                MAX(m.created_at) FILTER (WHERE m.sender_type = 'user') < :two_days_ago
                OR MAX(m.created_at) FILTER (WHERE m.sender_type = 'user') IS NULL
            ORDER BY last_user_message_at ASC NULLS FIRST
            LIMIT 20
        """)

        result = await session.execute(stmt, {
            "two_days_ago": two_days_ago,
        })

        contacts = []
        for row in result.all():
            last_msg_at = row[3]
            if last_msg_at is None:
                level = "never"
            elif last_msg_at < seven_days_ago:
                level = "critical"
            else:
                level = "warning"

            contacts.append({
                "contact_id": str(row[0]),
                "name": row[1],
                "avatar_url": row[2],
                "last_user_message_at": last_msg_at,
                "level": level,
            })

        return contacts

    async def _get_recent_open_conversations(
        self, session, two_days_ago: datetime, limit: int = 5,
    ) -> list[dict]:
        """Top N conversas abertas por last_message_at."""
        stmt = (
            select(Conversation)
            .join(User, User.id == Conversation.user_id)
            .where(Conversation.status == "open")
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        conversations = result.scalars().all()

        items = []
        for conv in conversations:
            # Last message
            last_msg_r = await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(desc(Message.created_at))
                .limit(1)
            )
            last_msg = last_msg_r.scalar_one_or_none()

            # Unread count
            unread_r = await session.execute(
                select(func.count(Message.id)).where(
                    and_(
                        Message.conversation_id == conv.id,
                        Message.sender_type == "user",
                        Message.status != "read",
                    )
                )
            )
            unread_count = unread_r.scalar() or 0

            # User info
            user = await session.get(User, conv.user_id)

            # Inactivity level
            last_user_msg_r = await session.execute(
                select(func.max(Message.created_at)).where(
                    and_(
                        Message.conversation_id == conv.id,
                        Message.sender_type == "user",
                    )
                )
            )
            last_user_at = last_user_msg_r.scalar()
            if last_user_at is None:
                inactivity = "never"
            elif last_user_at < two_days_ago:
                inactivity = "critical" if last_user_at < (two_days_ago - timedelta(days=5)) else "warning"
            else:
                inactivity = "active"

            items.append({
                "id": str(conv.id),
                "contact_id": str(conv.user_id),
                "contact_name": user.name if user else None,
                "contact_avatar": user.avatar_url if user else None,
                "last_message_at": conv.last_message_at,
                "last_message_content": last_msg.content if last_msg else None,
                "unread_count": unread_count,
                "inactivity_level": inactivity,
            })

        return items
