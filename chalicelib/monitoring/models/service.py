"""O serviço monitorado: cadastro (spec por tipo) e saúde atual."""
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator

from chalicelib.monitoring.models.check import CheckResult, HealthState

ServiceKind = Literal['api', 'monolith', 'supabase', 'zapi']
HttpMethod = Literal['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE']
HttpStatusCode = Annotated[int, Field(ge=100, le=599)]
SsmParameter = Annotated[str, Field(pattern=r'^/[\w./-]+$', description='Nome de parâmetro no SSM')]


# ---------------------------------------------------------------------------
# Especificação: como verificar cada tipo de serviço
# ---------------------------------------------------------------------------

class _BaseSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    timeout_seconds: float = Field(default=10, gt=0, le=30)
    retries: int = Field(default=1, ge=0, le=3)
    tags: list[str] = Field(default_factory=list)


class HttpServiceSpec(_BaseSpec):
    """APIs e monólitos. `url`, `headers` e `body` aceitam placeholders {{ssm:/param}}."""
    type: Literal['api', 'monolith']
    url: str
    method: HttpMethod = 'GET'
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | list[Any] | str | None = None
    expected_status: list[HttpStatusCode] | None = Field(default=None, min_length=1)
    expect_contains: str | None = None
    expect_json: dict[str, Any] | None = None

    @field_validator('url')
    @classmethod
    def _url_scheme(cls, value: str) -> str:
        if not value.startswith(('http://', 'https://')):
            raise ValueError('deve começar com http:// ou https://')
        return value

    @field_validator('method', mode='before')
    @classmethod
    def _upper_method(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class SupabaseServiceSpec(_BaseSpec):
    """Saudável = Auth respondendo e, se `table` for informada, PostgREST + banco respondendo."""
    type: Literal['supabase']
    project_url: HttpUrl
    api_key_param: SsmParameter
    table: str | None = Field(default=None, pattern=r'^[A-Za-z_][\w]*$')


class ZapiServiceSpec(_BaseSpec):
    """Saudável = instância conectada ao WhatsApp (e, opcionalmente, o celular também)."""
    type: Literal['zapi']
    instance_id_param: SsmParameter
    token_param: SsmParameter
    client_token_param: SsmParameter
    require_smartphone: bool = False
    base_url: HttpUrl = HttpUrl('https://api.z-api.io')


ServiceSpec = Annotated[
    HttpServiceSpec | SupabaseServiceSpec | ZapiServiceSpec, Field(discriminator='type')]
_spec_adapter: TypeAdapter[HttpServiceSpec | SupabaseServiceSpec | ZapiServiceSpec] = TypeAdapter(ServiceSpec)


def parse_spec(payload: dict[str, Any]) -> HttpServiceSpec | SupabaseServiceSpec | ZapiServiceSpec:
    """Valida o payload e devolve o spec do tipo certo. Lança pydantic.ValidationError."""
    return _spec_adapter.validate_python(payload)


# ---------------------------------------------------------------------------
# Saúde e serviço
# ---------------------------------------------------------------------------

class Health(BaseModel):
    """Última saúde conhecida. `since` marca quando o estado atual começou."""
    state: HealthState
    reason: str | None = None
    http_status: int | None = None
    latency_ms: int
    checked_at: datetime
    since: datetime

    @classmethod
    def after(cls, previous: 'Health | None', check: CheckResult) -> Self:
        continues = previous is not None and previous.state == check.state
        return cls(
            state=check.state,
            reason=check.reason,
            http_status=check.http_status,
            latency_ms=check.latency_ms,
            checked_at=check.checked_at,
            since=previous.since if previous and continues else check.checked_at,
        )


class Service(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: str
    spec: ServiceSpec
    health: Health | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def register(cls, spec: ServiceSpec, now: datetime) -> Self:
        return cls(id=str(uuid.uuid4()), spec=spec, created_at=now, updated_at=now)

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def kind(self) -> ServiceKind:
        return self.spec.type

    @property
    def is_enabled(self) -> bool:
        return self.spec.enabled

    @property
    def is_down(self) -> bool:
        return self.health is not None and self.health.state == 'down'

    @property
    def never_checked(self) -> bool:
        return self.health is None

    def with_spec(self, spec: ServiceSpec, now: datetime) -> Self:
        return self.model_copy(update={'spec': spec, 'updated_at': now})
