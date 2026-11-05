from chalicelib.monitoring.rules import Trigger
from chalicelib.notification.rules import DailyReportPolicy


def test_notify_status_change_sends_one_message_per_flip(world):
    world.add_service('1', name='ERP')
    world.http.respond(500)
    world.container.monitoring.check_service.execute('1', Trigger.MANUAL)
    world.http.respond(200)
    world.container.monitoring.check_service.execute('1', Trigger.MANUAL)

    for event in world.publisher.events:
        world.container.notification.notify_status_change.execute(event)

    assert len(world.sender.messages) == 2
    assert 'ERP está fora do ar' in world.sender.messages[0]
    assert 'ERP voltou a funcionar' in world.sender.messages[1]


def test_send_daily_report(world):
    world.add_service('1')
    world.container.monitoring.check_service.execute('1', Trigger.MANUAL)

    report = world.container.notification.send_daily_report.execute()

    assert DailyReportPolicy.situation(report) == 'all_up'
    assert 'tudo rodando' in world.sender.messages[0]
