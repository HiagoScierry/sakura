from typing import Any

from chalicelib.monitoring.models.service import Service, parse_spec
from chalicelib.monitoring.ports import ServiceRepository
from chalicelib.shared.clock import utcnow


class RegisterService:
    """Cadastra um novo serviço para monitorar. Payload inválido -> pydantic.ValidationError."""

    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self, payload: dict[str, Any]) -> Service:
        service = Service.register(parse_spec(payload), utcnow())
        self._services.add(service)
        return service
