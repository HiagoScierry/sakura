import re
from typing import Any

_PLACEHOLDER = re.compile(r'\{\{ssm:([^}]+)\}\}')


class SsmSecretStore:
    """Lê parâmetros SecureString do SSM com cache por container Lambda."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        if name not in self._cache:
            response = self._client.get_parameter(Name=name, WithDecryption=True)
            self._cache[name] = response['Parameter']['Value']
        return self._cache[name]

    def render(self, text: str) -> str:
        return _PLACEHOLDER.sub(lambda m: self.get(m.group(1).strip()), text)
