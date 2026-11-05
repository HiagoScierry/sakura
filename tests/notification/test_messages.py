from datetime import datetime, timedelta, timezone

from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.dashboard import ServiceOverview
from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown
from chalicelib.monitoring.models.service import Health
from chalicelib.notification import messages
from chalicelib.notification.models import DailyReport

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)  # 09:00 em Brasília


def check(state: str, **fields) -> CheckResult:
    return CheckResult(state=state, latency_ms=120, service_id='1', checked_at=NOW, **fields)


def overview(name: str, state: str | None, since_hours: int = 1, reason: str | None = None) -> ServiceOverview:
    health = None
    if state:
        health = Health(state=state, reason=reason, latency_ms=50, checked_at=NOW,
                        since=NOW - timedelta(hours=since_hours))
    return ServiceOverview(id=name, name=name, kind='api', enabled=True, health=health)


def test_went_down_message_is_specific_and_escaped():
    text = messages.service_went_down(ServiceWentDown(
        service_id='1', name='ERP <prod>', kind='monolith',
        check=check('down', reason='HTTP 503', http_status=503)))
    assert text.splitlines()[0] == '🔴 <b>ERP &lt;prod&gt; está fora do ar</b>'
    assert '<b>Motivo:</b> HTTP 503' in text
    assert '<b>HTTP:</b> 503' in text
    assert '<b>Detectado:</b> 04/11/2026 09:00 (Brasília)' in text


def test_recovered_message_shows_downtime():
    text = messages.service_recovered(ServiceRecovered(
        service_id='1', name='ERP', kind='monolith', check=check('up'),
        down_since=NOW - timedelta(hours=2, minutes=15)))
    assert 'ERP voltou a funcionar' in text
    assert '<b>Ficou fora por:</b> 2h 15min' in text


def test_daily_report_all_up_is_generic():
    report = DailyReport(generated_at=NOW, monitored=[overview('A', 'up'), overview('B', 'up')],
                         down=[], never_checked=[])
    text = messages.daily_report(report)
    assert text.startswith('✅ <b>Monitor: tudo rodando</b>')
    assert '2 serviço(s) verificados e no ar.' in text
    assert '04/11/2026 09:00 (Brasília)' in text


def test_daily_report_lists_what_is_still_down():
    erp = overview('ERP', 'down', since_hours=26, reason='HTTP 500')
    novo = overview('Novo', None)
    report = DailyReport(generated_at=NOW, monitored=[overview('API', 'up'), erp, novo],
                         down=[erp], never_checked=[novo])
    text = messages.daily_report(report)
    assert text.startswith('⚠️ <b>Monitor: 1 de 3 serviço(s) fora do ar</b>')
    assert '🔴 <b>ERP</b> (api): HTTP 500 · fora há 1d 2h' in text
    assert '⏳ Ainda sem verificação: Novo' in text


def test_daily_report_without_services():
    report = DailyReport(generated_at=NOW, monitored=[], down=[], never_checked=[])
    assert 'Nenhum serviço habilitado' in messages.daily_report(report)
