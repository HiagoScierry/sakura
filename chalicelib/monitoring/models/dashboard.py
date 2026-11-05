"""Visão consolidada da situação dos serviços."""
from typing import Self

from pydantic import BaseModel

from chalicelib.monitoring.models.service import Health, Service, ServiceKind


class ServiceOverview(BaseModel):
    id: str
    name: str
    kind: ServiceKind
    enabled: bool
    health: Health | None

    @classmethod
    def of(cls, service: Service) -> Self:
        return cls(id=service.id, name=service.name, kind=service.kind,
                   enabled=service.is_enabled, health=service.health)


class Dashboard(BaseModel):
    """Situação atual. `ok` só é falso se algum serviço habilitado estiver fora."""
    ok: bool
    monitored: list[ServiceOverview]
    down: list[ServiceOverview]
    never_checked: list[ServiceOverview]
    disabled: list[ServiceOverview]
