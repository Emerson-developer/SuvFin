"""Tool: Relatório por categoria."""

from datetime import date, datetime
from app.services.finance.report_service import ReportService


async def relatorio_categoria(
    user_id: str,
    categoria: str = None,
    periodo: str = None,
) -> str:
    """Gera relatório agrupado por categoria."""
    service = ReportService()
    today = date.today()

    # Período padrão: mês atual
    start = today.replace(day=1)
    end = today

    report = await service.generate_category_report(
        user_id, start, end, category_filter=categoria
    )

    if not report:
        return "📊 Nenhum lançamento encontrado para este período/categoria."

    if categoria:
        # Relatório detalhado de uma categoria
        cat = report[0]
        lines = [
            f"📊 *{cat['emoji']} {cat['name']}*\n",
            f"💲 Total: R$ {cat['total']:,.2f}",
            f"📋 Lançamentos: {cat['count']}",
            f"📊 Média: R$ {cat['average']:,.2f}\n",
        ]
        if cat.get("transactions"):
            lines.append("📝 *Últimos lançamentos:*")
            for tx in cat["transactions"][:5]:
                lines.append(
                    f"  • {tx['description'] or 'Sem desc.'} — "
                    f"R$ {tx['amount']:,.2f} ({tx['date'].strftime('%d/%m')})"
                )
        return "\n".join(lines)

    # Relatório geral por categoria
    lines = [
        f"📊 *Gastos por Categoria*",
        f"📅 {start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}\n",
    ]
    for cat in report:
        bar_len = int((cat["percentage"] / 100) * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(
            f"{cat['emoji']} *{cat['name']}*\n"
            f"  R$ {cat['total']:,.2f} ({cat['percentage']:.0f}%)\n"
            f"  {bar}"
        )

    return "\n".join(lines)
