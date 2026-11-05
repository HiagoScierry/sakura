from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class HttpRequest:
    url: str
    method: str = 'GET'
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 10


@dataclass(frozen=True)
class HttpResponse:
    status: int
    text: str


class HttpClient(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse:
        """Retorna a resposta mesmo para 4xx/5xx; lança exceção em falha de rede/timeout."""
        ...
