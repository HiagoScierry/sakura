import hmac

from chalice import AuthResponse, Blueprint
from chalice.app import AuthRequest

from chalicelib.container import get_container

bp = Blueprint(__name__)


@bp.authorizer()
def token_auth(auth_request: AuthRequest) -> AuthResponse:
    """Header "Authorization: Bearer <token>"; o token fica no SSM."""
    container = get_container()
    expected = container.secrets.get(container.settings.api_token_param)
    token = (auth_request.token or '').removeprefix('Bearer ').strip()
    if token and hmac.compare_digest(token, expected):
        return AuthResponse(routes=['*'], principal_id='monitor-admin')
    return AuthResponse(routes=[], principal_id='anonymous')
