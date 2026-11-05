"""Cadastro de serviços monitorados."""
from typing import Any

from chalice import Blueprint, Response

from chalicelib.container import get_container
from chalicelib.entrypoints.api.auth import token_auth
from chalicelib.entrypoints.api.errors import http_errors, json_object

bp = Blueprint(__name__)


@bp.route('/services', methods=['GET'], authorizer=token_auth)
def list_services() -> dict[str, Any]:
    services = get_container().monitoring.list_services.execute()
    return {'services': [s.model_dump(mode='json') for s in services]}


@bp.route('/services', methods=['POST'], authorizer=token_auth)
@http_errors
def register_service() -> Response:
    payload = json_object(bp.current_request.json_body)
    service = get_container().monitoring.register_service.execute(payload)
    return Response(body=service.model_dump(mode='json'), status_code=201)


@bp.route('/services/{service_id}', methods=['GET'], authorizer=token_auth)
@http_errors
def get_service(service_id: str) -> dict[str, Any]:
    return get_container().monitoring.get_service.execute(service_id).model_dump(mode='json')


@bp.route('/services/{service_id}', methods=['PATCH'], authorizer=token_auth)
@http_errors
def update_service(service_id: str) -> dict[str, Any]:
    changes = json_object(bp.current_request.json_body)
    return get_container().monitoring.update_service.execute(service_id, changes).model_dump(mode='json')


@bp.route('/services/{service_id}', methods=['DELETE'], authorizer=token_auth)
@http_errors
def remove_service(service_id: str) -> Response:
    get_container().monitoring.remove_service.execute(service_id)
    return Response(body='', status_code=204)
