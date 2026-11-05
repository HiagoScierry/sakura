"""Regras de negócio das notificações."""
from typing import Literal

from chalicelib.notification.models import DailyReport

ReportSituation = Literal['nothing_monitored', 'all_up', 'some_down']


class DailyReportPolicy:
    """Resumo diário (09:00 de Brasília).

    - Nenhum serviço habilitado -> avisa que não há nada monitorado.
    - Todos no ar -> mensagem genérica de "tudo rodando".
    - Algum fora -> lista cada serviço fora e há quanto tempo
      (lembrete: o alerta de queda já saiu uma vez, na hora em que caiu).
    - Serviços ainda nunca verificados são citados à parte; não contam como fora nem como no ar.
    """

    @staticmethod
    def situation(report: DailyReport) -> ReportSituation:
        if not report.monitored:
            return 'nothing_monitored'
        return 'some_down' if report.down else 'all_up'

    @staticmethod
    def up_count(report: DailyReport) -> int:
        return len(report.monitored) - len(report.down) - len(report.never_checked)
