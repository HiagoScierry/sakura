from datetime import datetime, timedelta, timezone

from chalicelib.monitoring.models.dashboard import Dashboard, ServiceOverview
from chalicelib.monitoring.models.service import Health
from chalicelib.notification.models import DailyReport
from chalicelib.notification.rules import DailyReportPolicy

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def overview(name: str, state: str | None) -> ServiceOverview:
    health = Health(state=state, latency_ms=1, checked_at=NOW, since=NOW - timedelta(hours=1)) if state else None
    return ServiceOverview(id=name, name=name, kind='api', enabled=True, health=health)


def report(*services: ServiceOverview) -> DailyReport:
    down = [s for s in services if s.health and s.health.state == 'down']
    dashboard = Dashboard(ok=not down, monitored=list(services), down=down,
                          never_checked=[s for s in services if s.health is None], disabled=[])
    return DailyReport.from_dashboard(dashboard, NOW)


def test_nothing_monitored():
    assert DailyReportPolicy.situation(report()) == 'nothing_monitored'


def test_all_up():
    assert DailyReportPolicy.situation(report(overview('A', 'up'), overview('B', 'up'))) == 'all_up'


def test_any_down():
    assert DailyReportPolicy.situation(report(overview('A', 'up'), overview('B', 'down'))) == 'some_down'


def test_never_checked_services_do_not_count_as_down_nor_up():
    r = report(overview('A', 'up'), overview('Novo', None))
    assert DailyReportPolicy.situation(r) == 'all_up' and DailyReportPolicy.up_count(r) == 1
