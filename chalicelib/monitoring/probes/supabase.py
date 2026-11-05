from chalicelib.monitoring.models.service import SupabaseServiceSpec
from chalicelib.monitoring.probes.base import expect_status
from chalicelib.shared.http import HttpClient, HttpRequest
from chalicelib.shared.secrets import SecretStore


class SupabaseProbe:
    """Auth (GoTrue) precisa responder 200; com `table`, um SELECT LIMIT 1 via PostgREST também."""

    def __init__(self, http: HttpClient, secrets: SecretStore) -> None:
        self._http = http
        self._secrets = secrets

    def probe(self, spec: SupabaseServiceSpec) -> int | None:
        base = str(spec.project_url).rstrip('/')
        key = self._secrets.get(spec.api_key_param)
        headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

        auth = self._http.send(HttpRequest(
            url=f'{base}/auth/v1/health', headers=headers, timeout=spec.timeout_seconds))
        expect_status(auth, [200], label='Auth: ')
        if spec.table is None:
            return auth.status

        rest = self._http.send(HttpRequest(
            url=f'{base}/rest/v1/{spec.table}?select=*&limit=1',
            headers=headers, timeout=spec.timeout_seconds))
        expect_status(rest, [200, 206], label='PostgREST: ')
        return rest.status
