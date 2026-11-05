from chalicelib.monitoring.models.events import ServiceRecovered, ServiceWentDown, StatusChanged
from chalicelib.notification import messages
from chalicelib.notification.ports import MessageSender


class NotifyStatusChange:
    """Avisa na hora em que um serviço cai ou volta.

    Cada queda/recuperação gera exatamente uma mensagem: quem decide se houve
    mudança é a AlertPolicy do monitoramento.
    """

    def __init__(self, sender: MessageSender) -> None:
        self._sender = sender

    def execute(self, event: StatusChanged) -> None:
        match event:
            case ServiceWentDown():
                self._sender.send(messages.service_went_down(event))
            case ServiceRecovered():
                self._sender.send(messages.service_recovered(event))
