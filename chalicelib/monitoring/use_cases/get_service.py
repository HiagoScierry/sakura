from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.models.service import Service
from chalicelib.monitoring.ports import ServiceRepository


class ListServices:
    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self) -> list[Service]:
        return sorted(self._services.list(), key=lambda s: s.name)


class GetService:
    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self, service_id: str) -> Service:
        service = self._services.get(service_id)
        if service is None:
            raise ServiceNotFound(service_id)
        return service
