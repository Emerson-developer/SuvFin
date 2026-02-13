"""Tool: Relatório por período."""

from datetime import date, datetime, timedelta
from app.services.finance.report_service import ReportService


async def relatorio_periodo(
    user_id: str,
    periodo: str = None,
    data_inicio: str = None,
    data_fim: str = None,
) -> str:
    """Gera relatório financeiro por período."""
    service = ReportService()
    today = date.today()

    # Determinar datas com base no período
    if data_inicio and data_fim:
        try:
            start = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            end = datetime.strptime(data_fim, "%Y-%m-%d").date()
        except ValueError:
            return "❌ Data inválida. Use o formato YYYY-MM-DD."
    elif periodo:
        start, end = _parse_periodo(periodo, today)
    else:
        # Padrão: mês atual
        start = today.replace(day=1)
        end = today

    report = await service.generate_period_report(user_id, start, end)

    if report["transaction_count"] == 0:
        return f"📊 Nenhum lançamento encontrado de {start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}."

    lines = [
        f"📊 *Relatório: {start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}*\n",
        f"🟢 Entradas: R$ {report['total_income']:,.2f}",
        f"🔴 Saídas: R$ {report['total_expense']:,.2f}",
        f"💰 Saldo: R$ {report['balance']:,.2f}\n",
        f"📋 Total de lançamentos: {report['transaction_count']}\n",
    ]

    if report["by_category"]:
        lines.append("📂 *Por categoria:*")
        for cat in report["by_category"][:10]:
            emoji = cat.get("emoji", "📦")
            lines.append(
                f"  {emoji} {cat['name']}: R$ {cat['total']:,.2f} "
                f"({cat['count']}x)"
            )

    return "\n".join(lines)


def _parse_periodo(periodo: str, today: date) -> tuple[date, date]:
    """Interpreta período em linguagem natural."""
    p = periodo.lower().strip()

    if "hoje" in p:
        return today, today
    elif "ontem" in p:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif "semana" in p:
        start = today - timedelta(days=today.weekday())
        return start, today
    elif "mês" in p or "mes" in p:
        start = today.replace(day=1)
        return start, today
    elif "ano" in p:
        start = today.replace(month=1, day=1)
        return start, today
    elif "últimos" in p or "ultimos" in p:
        # "últimos 30 dias", "últimos 7 dias"
        import re
        match = re.search(r"(\d+)", p)
        if match:
            days = int(match.group(1))
            start = today - timedelta(days=days)
            return start, today

    # Fallback: mês atual
    start = today.replace(day=1)
    return start, today
