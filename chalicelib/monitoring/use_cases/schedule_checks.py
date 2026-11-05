from chalicelib.monitoring.models.check import CheckRequest
from chalicelib.monitoring.ports import CheckQueue, ServiceRepository
from chalicelib.monitoring.rules import MonitoringPolicy, Trigger
from chalicelib.shared.clock import utcnow


class ScheduleChecks:
    """Roda de hora em hora: enfileira uma verificação por serviço elegível.

    Cada verificação é processada isoladamente por CheckService (fan-out via fila),
    então um serviço lento não atrasa os outros.
    """

    def __init__(self, services: ServiceRepository, queue: CheckQueue) -> None:
        self._services = services
        self._queue = queue

    def execute(self) -> int:
        now = utcnow()
        requests = [
            CheckRequest(service_id=service.id, requested_at=now)
            for service in self._services.list()
            if MonitoringPolicy.should_check(service, Trigger.SCHEDULED)
        ]
        self._queue.enqueue(requests)
        return len(requests)
