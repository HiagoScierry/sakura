from typing import Protocol


class SecretStore(Protocol):
    def get(self, name: str) -> str: ...

    def render(self, text: str) -> str:
        """Substitui placeholders {{ssm:/param}} pelo valor do parâmetro."""
        ...
