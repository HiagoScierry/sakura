from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.service import Health
from chalicelib.monitoring.ports import CheckHistory, EventPublisher, ServiceRepository
from chalicelib.monitoring.probes.prober import ServiceProber
from chalicelib.monitoring.rules import AlertPolicy, MonitoringPolicy, Trigger
from chalicelib.shared.clock import utcnow


class CheckService:
    """Verifica um serviço e registra o resultado.

    1. Confere se o serviço deve ser verificado (MonitoringPolicy).
    2. Sonda o serviço, com novas tentativas (RetryPolicy).
    3. Registra a verificação no histórico e atualiza a saúde do serviço.
    4. Se o estado virou, publica ServiceWentDown / ServiceRecovered (AlertPolicy).
    """

    def __init__(
        self,
        services: ServiceRepository,
        history: CheckHistory,
        prober: ServiceProber,
        publisher: EventPublisher,
    ) -> None:
        self._services = services
        self._history = history
        self._prober = prober
        self._publisher = publisher

    def execute(self, service_id: str, trigger: Trigger) -> CheckResult | None:
        """Retorna None quando a verificação agendada não se aplica mais
        (serviço removido ou desabilitado depois de enfileirado)."""
        service = self._services.get(service_id)
        if service is None:
            if trigger == Trigger.MANUAL:
                raise ServiceNotFound(service_id)
            return None
        if not MonitoringPolicy.should_check(service, trigger):
            return None

        outcome = self._prober.probe(service.spec)
        check = CheckResult(**outcome.model_dump(), service_id=service.id, checked_at=utcnow())
        event = AlertPolicy.event_for(service, check)

        self._history.add(check)
        self._services.save_health(service.id, Health.after(service.health, check))
        if event:
            self._publisher.publish(event)
        return check
