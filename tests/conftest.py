from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from chalicelib.config import Settings
from chalicelib.container import Container, set_container, wire
from chalicelib.monitoring.models.service import Service, parse_spec
from chalicelib.shared.clock import utcnow
from tests.fakes import (FakeHttp, FakePublisher, FakeQueue, FakeSecrets, FakeSender,
                         InMemoryCheckHistory, InMemoryServiceRepository)

API_TOKEN = 'segredo-de-teste'


@dataclass
class World:
    """Container real montado com fakes, expostos para asserções."""
    container: Container
    services: InMemoryServiceRepository
    history: InMemoryCheckHistory
    queue: FakeQueue
    publisher: FakePublisher
    sender: FakeSender
    secrets: FakeSecrets
    http: FakeHttp

    def add_service(self, service_id: str = '1', **spec: Any) -> Service:
        payload = {'type': 'api', 'name': 'API', 'url': 'https://api/health', 'retries': 0, **spec}
        service = Service.register(parse_spec(payload), utcnow()).model_copy(update={'id': service_id})
        self.services.add(service)
        return service


@pytest.fixture
def world() -> Iterator[World]:
    settings = Settings(
        services_table='s', check_history_table='h', api_token_param='/test/api-token',
        telegram_bot_token_param='/test/tg-token', telegram_chat_id_param='/test/tg-chat')
    services, history = InMemoryServiceRepository(), InMemoryCheckHistory()
    queue, publisher, sender = FakeQueue(), FakePublisher(), FakeSender()
    secrets, http = FakeSecrets({settings.api_token_param: API_TOKEN}), FakeHttp()

    container = wire(settings, services=services, history=history, queue=queue,
                     publisher=publisher, secrets=secrets, http=http, sender=sender)
    set_container(container)
    yield World(container, services, history, queue, publisher, sender, secrets, http)
    set_container(None)
