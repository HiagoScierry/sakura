import pytest
from pydantic import ValidationError

from chalicelib.monitoring.models.service import (HttpServiceSpec, SupabaseServiceSpec,
                                                  ZapiServiceSpec, parse_spec)


def test_spec_type_is_chosen_by_type_field():
    assert isinstance(parse_spec({'type': 'monolith', 'name': 'ERP', 'url': 'https://erp/health'}), HttpServiceSpec)
    assert isinstance(parse_spec({'type': 'supabase', 'name': 'DB', 'project_url': 'https://x.supabase.co',
                                  'api_key_param': '/sb/key'}), SupabaseServiceSpec)
    assert isinstance(parse_spec({'type': 'zapi', 'name': 'Zap', 'instance_id_param': '/a',
                                  'token_param': '/b', 'client_token_param': '/c'}), ZapiServiceSpec)


@pytest.mark.parametrize('payload', [
    {'type': 'database', 'name': 'x'},
    {'type': 'api', 'name': 'x', 'url': 'ftp://x'},
    {'type': 'api', 'name': 'x', 'url': 'https://x', 'expected_status': [700]},
    {'type': 'api', 'name': 'x', 'url': 'https://x', 'project_url': 'https://y'},  # campo de outro tipo
    {'type': 'supabase', 'name': 'x', 'project_url': 'https://y', 'api_key_param': 'sem-barra'},
    {'type': 'zapi', 'name': 'x', 'instance_id_param': '/a', 'token_param': '/b'},
])
def test_invalid_specs_are_rejected(payload):
    with pytest.raises(ValidationError):
        parse_spec(payload)
