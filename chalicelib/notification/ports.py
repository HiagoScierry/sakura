from typing import Protocol


class MessageSender(Protocol):
    def send(self, text: str) -> None:
        """Envia uma mensagem (HTML simples) ao canal de notificação."""
        ...
