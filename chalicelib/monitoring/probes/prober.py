import time
from collections.abc import Mapping
from typing import Any

from chalicelib.monitoring.models.check import ProbeOutcome
from chalicelib.monitoring.models.service import ServiceSpec
from chalicelib.monitoring.probes.base import HealthProbe, ProbeFailed
from chalicelib.monitoring.rules import RetryPolicy


class ServiceProber:
    """Escolhe a sonda pelo tipo do serviço e aplica a RetryPolicy."""

    def __init__(self, probes: Mapping[type[Any], HealthProbe[Any]]) -> None:
        self._probes = probes

    def probe(self, spec: ServiceSpec) -> ProbeOutcome:
        outcome = self._attempt(spec)
        for _ in range(RetryPolicy.attempts(spec) - 1):
            if outcome.state == 'up':
                break
            outcome = self._attempt(spec)
        return outcome

    def _attempt(self, spec: ServiceSpec) -> ProbeOutcome:
        probe = self._probes[type(spec)]
        started = time.monotonic()
        try:
            http_status = probe.probe(spec)
            reason = None
        except ProbeFailed as e:
            http_status, reason = e.http_status, e.reason
        except Exception as e:  # timeout, DNS, SSL, parâmetro SSM inexistente...
            http_status, reason = None, f'{type(e).__name__}: {e}'
        return ProbeOutcome(
            state='down' if reason else 'up',
            reason=reason,
            http_status=http_status,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
