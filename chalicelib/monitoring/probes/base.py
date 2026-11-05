import json
from typing import Any, Protocol, TypeVar

from chalicelib.shared.http import HttpResponse

S_contra = TypeVar('S_contra', contravariant=True)


class ProbeFailed(Exception):
    """O serviço respondeu, mas fora do esperado."""

    def __init__(self, reason: str, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class HealthProbe(Protocol[S_contra]):
    def probe(self, spec: S_contra) -> int | None:
        """Sonda o serviço uma vez e retorna o status HTTP final; lança ProbeFailed se estiver fora."""
        ...


def expect_status(response: HttpResponse, allowed: list[int] | None = None, label: str = '') -> None:
    ok = response.status in allowed if allowed else 200 <= response.status < 400
    if not ok:
        expected = f' (esperado {allowed})' if allowed else ''
        raise ProbeFailed(f'{label}HTTP {response.status}{expected}', response.status)


def parse_json(response: HttpResponse, label: str = '') -> Any:
    try:
        return json.loads(response.text)
    except ValueError:
        raise ProbeFailed(f'{label}resposta não é JSON válido', response.status)


def json_mismatch(expected: Any, actual: Any, path: str = '') -> str | None:
    """Retorna onde `actual` diverge de `expected` (comparação por subconjunto)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return f'{path or "raiz"}: esperado objeto'
        for key, value in expected.items():
            if key not in actual:
                return f'{path}{key}: ausente'
            mismatch = json_mismatch(value, actual[key], f'{path}{key}.')
            if mismatch:
                return mismatch
        return None
    if expected != actual:
        return f'{path.rstrip(".")}: esperado {expected!r}, recebido {actual!r}'
    return None
