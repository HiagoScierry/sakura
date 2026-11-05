"""Eventos de negócio publicados no EventBridge (detail-type = nome da classe)."""
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.service import ServiceKind


class ServiceWentDown(BaseModel):
    service_id: str
    name: str
    kind: ServiceKind
    check: CheckResult


class ServiceRecovered(BaseModel):
    service_id: str
    name: str
    kind: ServiceKind
    check: CheckResult
    down_since: datetime

    @property
    def downtime(self) -> timedelta:
        return self.check.checked_at - self.down_since


StatusChanged = ServiceWentDown | ServiceRecovered

EVENT_TYPES: dict[str, type[StatusChanged]] = {
    cls.__name__: cls for cls in (ServiceWentDown, ServiceRecovered)
}


def parse_status_changed(detail_type: str, detail: dict[str, Any]) -> StatusChanged:
    return EVENT_TYPES[detail_type].model_validate(detail)
