"""Regras de negócio do monitoramento, testadas isoladamente."""
from datetime import timedelta

import pytest

from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown
from chalicelib.monitoring.models.service import Health, Service, parse_spec
from chalicelib.monitoring.rules import AlertPolicy, MonitoringPolicy, RetryPolicy, Trigger
from chalicelib.shared.clock import utcnow


def service(state: str | None = None, since_hours: int = 0, enabled: bool = True) -> Service:
    spec = parse_spec({'type': 'api', 'name': 'API', 'url': 'https://api', 'enabled': enabled})
    svc = Service.register(spec, utcnow())
    if state is None:
        return svc
    now = utcnow()
    health = Health(state=state, latency_ms=1, checked_at=now, since=now - timedelta(hours=since_hours))
    return svc.model_copy(update={'health': health})


def check(state: str) -> CheckResult:
    return CheckResult(state=state, latency_ms=5, service_id='1', checked_at=utcnow())


class TestAlertPolicy:
    @pytest.mark.parametrize('previous, current, expected', [
        (None, 'up', None),                  # serviço novo no ar não é novidade
        (None, 'down', ServiceWentDown),     # serviço novo já fora alerta
        ('up', 'up', None),
        ('up', 'down', ServiceWentDown),     # queda
        ('down', 'down', None),              # continua fora: não repete
        ('down', 'up', ServiceRecovered),    # recuperação
    ])
    def test_alerts_only_when_state_flips(self, previous, current, expected):
        event = AlertPolicy.event_for(service(previous), check(current))
        assert type(event) is expected if expected else event is None

    def test_recovery_carries_how_long_it_was_down(self):
        event = AlertPolicy.event_for(service('down', since_hours=3), check('up'))
        assert isinstance(event, ServiceRecovered)
        assert timedelta(hours=2, minutes=59) < event.downtime <= timedelta(hours=3, seconds=1)


class TestMonitoringPolicy:
    def test_scheduled_checks_skip_disabled_services(self):
        assert MonitoringPolicy.should_check(service(enabled=True), Trigger.SCHEDULED)
        assert not MonitoringPolicy.should_check(service(enabled=False), Trigger.SCHEDULED)

    def test_manual_checks_run_on_any_service(self):
        assert MonitoringPolicy.should_check(service(enabled=False), Trigger.MANUAL)


class TestRetryPolicy:
    def test_attempts_are_one_plus_retries(self):
        assert RetryPolicy.attempts(parse_spec({'type': 'api', 'name': 'x', 'url': 'https://x', 'retries': 2})) == 3


class TestHealth:
    def test_since_is_kept_while_state_is_unchanged(self):
        previous = service('down', since_hours=5).health
        assert Health.after(previous, check('down')).since == previous.since

    def test_since_restarts_when_state_flips(self):
        new_check = check('up')
        assert Health.after(service('down', since_hours=5).health, new_check).since == new_check.checked_at
