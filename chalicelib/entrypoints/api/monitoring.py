"""Situação dos serviços, histórico e verificação manual."""
from typing import Any

from chalice import BadRequestError, Blueprint, Response

from chalicelib.container import get_container
from chalicelib.entrypoints.api.auth import token_auth
from chalicelib.entrypoints.api.errors import http_errors
from chalicelib.monitoring.rules import Trigger

bp = Blueprint(__name__)


@bp.route('/', methods=['GET'])
def health() -> dict[str, str]:
    return {'status': 'ok'}


@bp.route('/dashboard', methods=['GET'], authorizer=token_auth)
def dashboard() -> dict[str, Any]:
    return get_container().monitoring.get_dashboard.execute().model_dump(mode='json')


@bp.route('/services/{service_id}/checks', methods=['GET'], authorizer=token_auth)
@http_errors
def check_history(service_id: str) -> dict[str, Any]:
    params = bp.current_request.query_params
    try:
        limit = int(params.get('limit', '24') if params else '24')
    except ValueError:
        raise BadRequestError("'limit' deve ser um número inteiro")
    checks = get_container().monitoring.get_check_history.execute(service_id, limit)
    return {'checks': [c.model_dump(mode='json') for c in checks]}


@bp.route('/services/{service_id}/checks', methods=['POST'], authorizer=token_auth)
@http_errors
def check_now(service_id: str) -> dict[str, Any]:
    """Verificação manual e síncrona (inclusive de serviço desabilitado)."""
    check = get_container().monitoring.check_service.execute(service_id, Trigger.MANUAL)
    return check.model_dump(mode='json') if check else {}


@bp.route('/checks', methods=['POST'], authorizer=token_auth)
def schedule_checks_now() -> Response:
    """Enfileira a verificação de todos os serviços habilitados (assíncrono)."""
    return Response(body={'enqueued': get_container().monitoring.schedule_checks.execute()}, status_code=202)
