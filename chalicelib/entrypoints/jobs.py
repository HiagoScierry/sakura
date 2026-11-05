"""Gatilhos de eventos: cada handler só traduz o evento e chama um caso de uso."""
from chalice import Blueprint, Cron, Rate
from chalice.app import CloudWatchEvent, SQSEvent

from chalicelib.config import CHECK_QUEUE_NAME, EVENT_SOURCE
from chalicelib.container import get_container
from chalicelib.monitoring.models.check import CheckRequest
from chalicelib.monitoring.models.events import EVENT_TYPES, parse_status_changed
from chalicelib.monitoring.rules import Trigger

bp = Blueprint(__name__)


@bp.schedule(Rate(1, unit=Rate.HOURS))
def schedule_checks(event: CloudWatchEvent) -> None:
    total = get_container().monitoring.schedule_checks.execute()
    bp.log.info('%d verificações enfileiradas', total)


@bp.on_sqs_message(queue=CHECK_QUEUE_NAME, batch_size=1)
def check_service(event: SQSEvent) -> None:
    """Exceções devolvem a mensagem à fila (e, após 3 tentativas, à DLQ)."""
    use_case = get_container().monitoring.check_service
    for record in event:
        request = CheckRequest.model_validate_json(record.body)
        check = use_case.execute(request.service_id, Trigger.SCHEDULED)
        if check:
            bp.log.info('%s: %s %s', request.service_id, check.state, check.reason or '')


@bp.on_cw_event({'source': [EVENT_SOURCE], 'detail-type': list(EVENT_TYPES)})
def notify_status_change(event: CloudWatchEvent) -> None:
    status_changed = parse_status_changed(event.detail_type, event.detail)
    get_container().notification.notify_status_change.execute(status_changed)


# 09:00 em Brasília (12:00 UTC)
@bp.schedule(Cron(0, 12, '*', '*', '?', '*'))
def send_daily_report(event: CloudWatchEvent) -> None:
    get_container().notification.send_daily_report.execute()
