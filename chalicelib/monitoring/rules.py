"""Regras de negócio do monitoramento.

Cada regra fica numa política com nome próprio, para ser lida (e testada) isoladamente.
"""
from enum import StrEnum

from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown, StatusChanged
from chalicelib.monitoring.models.service import Service, ServiceSpec


class Trigger(StrEnum):
    SCHEDULED = 'scheduled'
    MANUAL = 'manual'


class MonitoringPolicy:
    """Quais serviços são verificados.

    - A verificação agendada (de hora em hora) cobre apenas serviços habilitados.
    - A verificação manual roda em qualquer serviço, inclusive desabilitado
      (útil para testar um cadastro antes de habilitá-lo).
    """

    @staticmethod
    def should_check(service: Service, trigger: Trigger) -> bool:
        return trigger == Trigger.MANUAL or service.is_enabled


class RetryPolicy:
    """Quando um serviço é considerado fora.

    - Só é declarado fora depois que todas as tentativas falham (1 + `retries` do cadastro).
    - Evita alarme falso por uma oscilação pontual de rede.
    """

    @staticmethod
    def attempts(spec: ServiceSpec) -> int:
        return 1 + spec.retries


class AlertPolicy:
    """Quando uma verificação vira alerta.

    - Alerta quando o estado vira: no ar -> fora (queda) ou fora -> no ar (recuperação).
    - Serviço novo (nunca verificado) que já nasce fora gera alerta de queda.
    - Serviço novo que está no ar NÃO é novidade: não alerta.
    - Serviço que continua fora não alerta de novo (o lembrete fica com o resumo diário).
    """

    @staticmethod
    def event_for(service: Service, check: CheckResult) -> StatusChanged | None:
        health = service.health
        if check.state == 'down' and (health is None or health.state == 'up'):
            return ServiceWentDown(service_id=service.id, name=service.name, kind=service.kind, check=check)
        if check.state == 'up' and health is not None and health.state == 'down':
            return ServiceRecovered(service_id=service.id, name=service.name, kind=service.kind,
                                    check=check, down_since=health.since)
        return None
