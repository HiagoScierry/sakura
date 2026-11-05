from chalicelib.monitoring.models.service import ZapiServiceSpec
from chalicelib.monitoring.probes.base import ProbeFailed, expect_status, parse_json
from chalicelib.shared.http import HttpClient, HttpRequest
from chalicelib.shared.secrets import SecretStore


class ZapiProbe:
    """A instância precisa estar `connected`; com `require_smartphone`, o celular também."""

    def __init__(self, http: HttpClient, secrets: SecretStore) -> None:
        self._http = http
        self._secrets = secrets

    def probe(self, spec: ZapiServiceSpec) -> int | None:
        instance = self._secrets.get(spec.instance_id_param)
        token = self._secrets.get(spec.token_param)
        base = str(spec.base_url).rstrip('/')

        response = self._http.send(HttpRequest(
            url=f'{base}/instances/{instance}/token/{token}/status',
            headers={'Client-Token': self._secrets.get(spec.client_token_param)},
            timeout=spec.timeout_seconds,
        ))
        expect_status(response, [200])
        payload = parse_json(response)

        if payload.get('connected') is not True:
            raise ProbeFailed(f"Instância desconectada: {payload.get('error') or payload}", response.status)
        if spec.require_smartphone and payload.get('smartphoneConnected') is not True:
            raise ProbeFailed('Celular desconectado da instância', response.status)
        return response.status
