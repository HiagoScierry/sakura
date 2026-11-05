import json

from chalice.test import Client

from app import app
from tests.conftest import API_TOKEN

AUTH = {'Authorization': f'Bearer {API_TOKEN}', 'Content-Type': 'application/json'}


def call(client, method, path, body=None, headers=AUTH):
    return getattr(client.http, method)(path, headers=headers, body=json.dumps(body) if body else None)


def test_health_is_public_and_the_rest_requires_token(world):
    with Client(app) as client:
        assert client.http.get('/').status_code == 200
        assert client.http.get('/services').status_code in (401, 403)
        assert call(client, 'get', '/services', headers={'Authorization': 'Bearer errado'}).status_code in (401, 403)
        assert call(client, 'get', '/services').status_code == 200


def test_service_registry(world):
    with Client(app) as client:
        created = call(client, 'post', '/services', {
            'type': 'supabase', 'name': 'Supabase prod', 'project_url': 'https://x.supabase.co',
            'api_key_param': '/sb/key'})
        assert created.status_code == 201
        service_id = created.json_body['id']

        updated = call(client, 'patch', f'/services/{service_id}', {'enabled': False})
        assert updated.json_body['spec']['enabled'] is False

        assert call(client, 'delete', f'/services/{service_id}').status_code == 204
        assert call(client, 'get', f'/services/{service_id}').status_code == 404


def test_validation_errors_are_400_with_field_path(world):
    with Client(app) as client:
        response = call(client, 'post', '/services', {'type': 'api', 'name': 'x', 'url': 'nada'})
        assert response.status_code == 400 and 'api.url' in response.json_body['Message']


def test_dashboard_checks_and_history(world):
    world.add_service('1', name='ERP')
    world.http.respond(503)
    with Client(app) as client:
        assert call(client, 'post', '/services/1/checks').json_body['reason'] == 'HTTP 503'
        assert call(client, 'post', '/services/x/checks').status_code == 404
        assert call(client, 'get', '/dashboard').json_body['down'][0]['name'] == 'ERP'
        assert call(client, 'get', '/services/1/checks').json_body['checks'][0]['state'] == 'down'
        assert call(client, 'post', '/checks').json_body == {'enqueued': 1}
