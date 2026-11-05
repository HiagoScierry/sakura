from chalice.test import Client

from app import app
from chalicelib.config import EVENT_SOURCE
from chalicelib.monitoring.models.events import ServiceWentDown
from chalicelib.monitoring.rules import Trigger


def scheduled_event(client):
    return client.events.generate_cw_event(source='aws.events', detail_type='Scheduled Event',
                                           detail={}, resources=[])


def test_hourly_schedule_fans_out_and_worker_checks(world):
    world.add_service('1')
    world.http.respond(500)
    with Client(app) as client:
        client.lambda_.invoke('schedule_checks', scheduled_event(client))
        body = world.queue.messages[0].model_dump_json()
        client.lambda_.invoke('check_service', client.events.generate_sqs_event(
            queue_name='chalice-api-checks-dev', message_bodies=[body]))

    assert world.history.items[0].state == 'down'
    assert isinstance(world.publisher.events[0], ServiceWentDown)


def test_status_change_event_is_sent_to_telegram(world):
    world.add_service('1', name='ERP')
    world.http.respond(500)
    world.container.monitoring.check_service.execute('1', Trigger.MANUAL)
    event = world.publisher.events[0]
    with Client(app) as client:
        client.lambda_.invoke('notify_status_change', client.events.generate_cw_event(
            source=EVENT_SOURCE, detail_type=type(event).__name__,
            detail=event.model_dump(mode='json'), resources=[]))
    assert 'ERP está fora do ar' in world.sender.messages[0]


def test_daily_report_job(world):
    with Client(app) as client:
        client.lambda_.invoke('send_daily_report', scheduled_event(client))
    assert 'Nenhum serviço habilitado' in world.sender.messages[0]
