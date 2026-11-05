"""Verificações: o resultado de sondar um serviço e o pedido enfileirado."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

HealthState = Literal['up', 'down']


class ProbeOutcome(BaseModel):
    """Resultado de sondar um serviço (já considerando as tentativas)."""
    state: HealthState
    reason: str | None = None
    http_status: int | None = None
    latency_ms: int


class CheckResult(ProbeOutcome):
    """Uma verificação registrada no histórico."""
    model_config = ConfigDict(extra='ignore')

    service_id: str
    checked_at: datetime


class CheckRequest(BaseModel):
    """Pedido de verificação enfileirado pelo agendamento."""
    service_id: str
    requested_at: datetime
