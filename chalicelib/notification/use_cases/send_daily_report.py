from chalicelib.monitoring.use_cases.get_dashboard import GetDashboard
from chalicelib.notification import messages
from chalicelib.notification.models import DailyReport
from chalicelib.notification.ports import MessageSender
from chalicelib.shared.clock import utcnow


class SendDailyReport:
    """Envia o resumo diário (regras em DailyReportPolicy)."""

    def __init__(self, get_dashboard: GetDashboard, sender: MessageSender) -> None:
        self._get_dashboard = get_dashboard
        self._sender = sender

    def execute(self) -> DailyReport:
        report = DailyReport.from_dashboard(self._get_dashboard.execute(), utcnow())
        self._sender.send(messages.daily_report(report))
        return report
