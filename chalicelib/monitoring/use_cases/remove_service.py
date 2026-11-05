from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.ports import ServiceRepository


class RemoveService:
    """Remove o serviço do monitoramento. O histórico expira sozinho (TTL)."""

    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self, service_id: str) -> None:
        if not self._services.delete(service_id):
            raise ServiceNotFound(service_id)
