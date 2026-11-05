from chalicelib.monitoring.models.service import (HttpServiceSpec, SupabaseServiceSpec,
                                                  ZapiServiceSpec, parse_spec)
from chalicelib.monitoring.probes.http import HttpProbe
from chalicelib.monitoring.probes.prober import ServiceProber
from chalicelib.monitoring.probes.supabase import SupabaseProbe
from chalicelib.monitoring.probes.zapi import ZapiProbe
from chalicelib.shared.http import HttpResponse
from tests.fakes import FakeHttp, FakeSecrets


def make_prober(http: FakeHttp, secrets: FakeSecrets) -> ServiceProber:
    return ServiceProber({
        HttpServiceSpec: HttpProbe(http, secrets),
        SupabaseServiceSpec: SupabaseProbe(http, secrets),
        ZapiServiceSpec: ZapiProbe(http, secrets),
    })


def probe(http: FakeHttp, secrets: FakeSecrets | None = None, **spec):
    return make_prober(http, secrets or FakeSecrets()).probe(parse_spec(spec))


def test_http_status_text_and_json_expectations():
    http = FakeHttp()
    spec = {'type': 'api', 'name': 'API', 'url': 'https://api', 'retries': 0}

    http.respond(503)
    assert probe(http, **spec).reason == 'HTTP 503'

    http.respond(200, 'pong')
    assert probe(http, **spec, expect_contains='pong').state == 'up'
    assert 'não contém' in probe(http, **spec, expect_contains='ok').reason

    http.respond(200, '{"db": {"ok": false}}')
    assert probe(http, **spec, expect_json={'db': {'ok': False}}).state == 'up'
    assert probe(http, **spec, expect_json={'db': {'ok': True}}).reason == 'db.ok: esperado True, recebido False'


def test_http_renders_ssm_placeholders():
    http = FakeHttp()
    probe(http, FakeSecrets({'/erp/token': 'abc'}), type='monolith', name='ERP',
          url='https://erp/health?k={{ssm:/erp/token}}', headers={'Authorization': 'Bearer {{ssm:/erp/token}}'},
          method='post', body={'ping': 1})
    request = http.requests[0]
    assert request.url == 'https://erp/health?k=abc'
    assert request.headers['Authorization'] == 'Bearer abc'
    assert request.method == 'POST' and request.body == b'{"ping": 1}'


def test_supabase_checks_auth_then_table():
    http, secrets = FakeHttp(), FakeSecrets({'/sb/key': 'KEY'})
    spec = {'type': 'supabase', 'name': 'DB', 'project_url': 'https://x.supabase.co',
            'api_key_param': '/sb/key', 'table': 'clientes', 'retries': 0}

    assert probe(http, secrets, **spec).state == 'up'
    assert [r.url for r in http.requests] == [
        'https://x.supabase.co/auth/v1/health',
        'https://x.supabase.co/rest/v1/clientes?select=*&limit=1',
    ]
    assert http.requests[0].headers['apikey'] == 'KEY'

    http.responder = lambda r: HttpResponse(200 if 'auth' in r.url else 500, '')
    assert probe(http, secrets, **spec).reason == 'PostgREST: HTTP 500 (esperado [200, 206])'


def test_zapi_requires_connected_instance_and_smartphone():
    http = FakeHttp()
    secrets = FakeSecrets({'/z/i': 'INST', '/z/t': 'TOK', '/z/c': 'CLI'})
    spec = {'type': 'zapi', 'name': 'Zap', 'instance_id_param': '/z/i', 'token_param': '/z/t',
            'client_token_param': '/z/c', 'require_smartphone': True, 'retries': 0}

    http.respond(200, '{"connected": true, "smartphoneConnected": true}')
    assert probe(http, secrets, **spec).state == 'up'
    assert http.requests[0].url == 'https://api.z-api.io/instances/INST/token/TOK/status'
    assert http.requests[0].headers['Client-Token'] == 'CLI'

    http.respond(200, '{"connected": false, "error": "You are not connected."}')
    assert probe(http, secrets, **spec).reason == 'Instância desconectada: You are not connected.'

    http.respond(200, '{"connected": true, "smartphoneConnected": false}')
    assert probe(http, secrets, **spec).reason == 'Celular desconectado da instância'


def test_prober_applies_retry_policy_and_catches_network_errors():
    http = FakeHttp()
    http.fail(TimeoutError('timed out'))
    outcome = probe(http, type='api', name='lento', url='https://lento', retries=2)
    assert outcome.state == 'down' and outcome.reason == 'TimeoutError: timed out'
    assert len(http.requests) == 3


def test_prober_stops_retrying_once_up():
    http = FakeHttp()
    statuses = iter([500, 200, 200])
    http.responder = lambda _: HttpResponse(next(statuses), '')
    assert probe(http, type='api', name='oscila', url='https://x', retries=2).state == 'up'
    assert len(http.requests) == 2
