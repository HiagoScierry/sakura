import json

from chalicelib.monitoring.models.service import HttpServiceSpec
from chalicelib.monitoring.probes.base import ProbeFailed, expect_status, json_mismatch, parse_json
from chalicelib.shared.http import HttpClient, HttpRequest
from chalicelib.shared.secrets import SecretStore


class HttpProbe:
    """APIs e monólitos: status esperado e, opcionalmente, texto ou JSON esperado na resposta."""

    def __init__(self, http: HttpClient, secrets: SecretStore) -> None:
        self._http = http
        self._secrets = secrets

    def probe(self, spec: HttpServiceSpec) -> int | None:
        headers = {k: self._secrets.render(v) for k, v in spec.headers.items()}
        body: bytes | None = None
        if spec.body is not None:
            raw = spec.body if isinstance(spec.body, str) else json.dumps(spec.body)
            if not isinstance(spec.body, str):
                headers.setdefault('Content-Type', 'application/json')
            body = self._secrets.render(raw).encode()

        response = self._http.send(HttpRequest(
            url=self._secrets.render(spec.url), method=spec.method,
            headers=headers, body=body, timeout=spec.timeout_seconds,
        ))

        expect_status(response, spec.expected_status)
        if spec.expect_contains and spec.expect_contains not in response.text:
            raise ProbeFailed(f'Resposta não contém "{spec.expect_contains}"', response.status)
        if spec.expect_json:
            mismatch = json_mismatch(spec.expect_json, parse_json(response))
            if mismatch:
                raise ProbeFailed(mismatch, response.status)
        return response.status
