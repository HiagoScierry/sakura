import pytest
from pydantic import ValidationError

from chalicelib.monitoring.errors import ServiceNotFound
from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown
from chalicelib.monitoring.rules import Trigger


class TestServiceRegistry:
    def test_register_update_and_remove(self, world):
        m = world.container.monitoring
        service = m.register_service.execute({
            'type': 'supabase', 'name': 'Supabase prod',
            'project_url': 'https://x.supabase.co', 'api_key_param': '/sb/key'})
        assert world.services.get(service.id) is not None

        updated = m.update_service.execute(service.id, {'enabled': False})
        assert updated.is_enabled is False and updated.name == 'Supabase prod'

        m.remove_service.execute(service.id)
        with pytest.raises(ServiceNotFound):
            m.get_service.execute(service.id)

    def test_update_validates_the_resulting_spec(self, world):
        world.add_service('1')
        with pytest.raises(ValidationError):
            world.container.monitoring.update_service.execute('1', {'retries': 99})


class TestScheduleChecks:
    def test_enqueues_only_eligible_services(self, world):
        world.add_service('1')
        world.add_service('2', enabled=False)
        assert world.container.monitoring.schedule_checks.execute() == 1
        assert [m.service_id for m in world.queue.messages] == ['1']


class TestCheckService:
    def test_records_history_health_and_publishes_state_flips(self, world):
        world.add_service('1')
        check_service = world.container.monitoring.check_service

        for status in (200, 500, 500, 200):
            world.http.respond(status)
            check_service.execute('1', Trigger.SCHEDULED)

        assert [type(e) for e in world.publisher.events] == [ServiceWentDown, ServiceRecovered]
        assert world.publisher.events[0].check.reason == 'HTTP 500'
        assert [c.state for c in world.history.items] == ['up', 'down', 'down', 'up']
        assert world.services.get('1').health.state == 'up'

    def test_scheduled_check_is_skipped_for_disabled_or_removed_services(self, world):
        world.add_service('1', enabled=False)
        check_service = world.container.monitoring.check_service
        assert check_service.execute('1', Trigger.SCHEDULED) is None
        assert check_service.execute('removido', Trigger.SCHEDULED) is None
        assert world.http.requests == []

    def test_manual_check_runs_on_disabled_service(self, world):
        world.add_service('1', enabled=False)
        assert world.container.monitoring.check_service.execute('1', Trigger.MANUAL).state == 'up'
        with pytest.raises(ServiceNotFound):
            world.container.monitoring.check_service.execute('removido', Trigger.MANUAL)


class TestQueries:
    def test_dashboard(self, world):
        world.add_service('1', name='ERP')
        world.add_service('2', name='Novo')
        world.add_service('3', name='Off', enabled=False)
        world.http.respond(503)
        world.container.monitoring.check_service.execute('1', Trigger.MANUAL)

        dashboard = world.container.monitoring.get_dashboard.execute()
        assert dashboard.ok is False
        assert [s.name for s in dashboard.down] == ['ERP']
        assert [s.name for s in dashboard.never_checked] == ['Novo']
        assert [s.name for s in dashboard.disabled] == ['Off']

    def test_check_history(self, world):
        world.add_service('1')
        for _ in range(3):
            world.container.monitoring.check_service.execute('1', Trigger.MANUAL)
        assert len(world.container.monitoring.get_check_history.execute('1', limit=2)) == 2
        with pytest.raises(ServiceNotFound):
            world.container.monitoring.get_check_history.execute('removido')
