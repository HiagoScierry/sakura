from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.ports import CheckHistory, ServiceRepository

MAX_LIMIT = 200


class GetCheckHistory:
    """Últimas verificações de um serviço, da mais recente para a mais antiga."""

    def __init__(self, services: ServiceRepository, history: CheckHistory) -> None:
        self._services = services
        self._history = history

    def execute(self, service_id: str, limit: int = 24) -> list[CheckResult]:
        if self._services.get(service_id) is None:
            raise ServiceNotFound(service_id)
        return self._history.recent(service_id, min(max(limit, 1), MAX_LIMIT))
