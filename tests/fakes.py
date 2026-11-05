"""Implementações em memória dos ports, usadas nos testes."""
from collections.abc import Callable

from chalicelib.monitoring.models.check import CheckRequest, CheckResult
from chalicelib.monitoring.models.events import StatusChanged
from chalicelib.monitoring.models.service import Health, Service
from chalicelib.shared.http import HttpRequest, HttpResponse


class InMemoryServiceRepository:
    def __init__(self) -> None:
        self.items: dict[str, Service] = {}

    def list(self) -> list[Service]:
        return list(self.items.values())

    def get(self, service_id: str) -> Service | None:
        return self.items.get(service_id)

    def add(self, service: Service) -> None:
        self.items[service.id] = service

    def save_spec(self, service: Service) -> bool:
        if service.id not in self.items:
            return False
        self.items[service.id] = self.items[service.id].model_copy(
            update={'spec': service.spec, 'updated_at': service.updated_at})
        return True

    def save_health(self, service_id: str, health: Health) -> None:
        self.items[service_id] = self.items[service_id].model_copy(update={'health': health})

    def delete(self, service_id: str) -> bool:
        return self.items.pop(service_id, None) is not None


class InMemoryCheckHistory:
    def __init__(self) -> None:
        self.items: list[CheckResult] = []

    def add(self, check: CheckResult) -> None:
        self.items.append(check)

    def recent(self, service_id: str, limit: int) -> list[CheckResult]:
        return [c for c in reversed(self.items) if c.service_id == service_id][:limit]


class FakeQueue:
    def __init__(self) -> None:
        self.messages: list[CheckRequest] = []

    def enqueue(self, requests: list[CheckRequest]) -> None:
        self.messages.extend(requests)


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[StatusChanged] = []

    def publish(self, event: StatusChanged) -> None:
        self.events.append(event)


class FakeSender:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


class FakeSecrets:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def get(self, name: str) -> str:
        return self.values[name]

    def render(self, text: str) -> str:
        for name, value in self.values.items():
            text = text.replace(f'{{{{ssm:{name}}}}}', value)
        return text


Responder = Callable[[HttpRequest], HttpResponse]


class FakeHttp:
    """Responde com `responder` e guarda as requisições feitas."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self.responder: Responder = lambda _: HttpResponse(200, '{}')

    def respond(self, status: int = 200, text: str = '{}') -> None:
        self.responder = lambda _: HttpResponse(status, text)

    def fail(self, error: Exception) -> None:
        def raise_error(_: HttpRequest) -> HttpResponse:
            raise error
        self.responder = raise_error

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self.responder(request)
