import functools
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from chalice import BadRequestError, NotFoundError
from pydantic import ValidationError

from chalicelib.monitoring.errors import ServiceNotFound

P = ParamSpec('P')
R = TypeVar('R')


def http_errors(view: Callable[P, R]) -> Callable[P, R]:
    """Traduz erros de negócio/validação para respostas HTTP."""
    @functools.wraps(view)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return view(*args, **kwargs)
        except ServiceNotFound as e:
            raise NotFoundError(str(e))
        except ValidationError as e:
            raise BadRequestError(format_validation_error(e))
    return wrapper


def format_validation_error(error: ValidationError) -> str:
    return '; '.join(
        f"{'.'.join(str(p) for p in err['loc']) or 'corpo'}: {err['msg']}" for err in error.errors())


def json_object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise BadRequestError('O corpo deve ser um objeto JSON')
    return body
