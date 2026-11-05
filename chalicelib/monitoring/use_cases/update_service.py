from typing import Any

from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.models.service import Service, parse_spec
from chalicelib.monitoring.ports import ServiceRepository
from chalicelib.shared.clock import utcnow


class UpdateService:
    """Altera campos do cadastro. A configuração resultante é validada por inteiro.

    O histórico e a saúde atual são mantidos.
    """

    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self, service_id: str, changes: dict[str, Any]) -> Service:
        service = self._services.get(service_id)
        if service is None:
            raise ServiceNotFound(service_id)

        spec = parse_spec({**service.spec.model_dump(mode='json'), **changes})
        updated = service.with_spec(spec, utcnow())
        if not self._services.save_spec(updated):
            raise ServiceNotFound(service_id)
        return updated
