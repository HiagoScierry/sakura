import json

from chalicelib.shared.http import HttpClient, HttpRequest
from chalicelib.shared.secrets import SecretStore

TELEGRAM_API = 'https://api.telegram.org'
MAX_MESSAGE_LENGTH = 4096


class TelegramError(Exception):
    pass


class TelegramSender:
    """Envia mensagens via Bot API (sendMessage). Token e chat_id vêm do SSM."""

    def __init__(self, http: HttpClient, secrets: SecretStore, token_param: str, chat_id_param: str) -> None:
        self._http = http
        self._secrets = secrets
        self._token_param = token_param
        self._chat_id_param = chat_id_param

    def send(self, text: str) -> None:
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH - 1] + '…'
        token = self._secrets.get(self._token_param)
        response = self._http.send(HttpRequest(
            url=f'{TELEGRAM_API}/bot{token}/sendMessage',
            method='POST',
            headers={'Content-Type': 'application/json'},
            body=json.dumps({
                'chat_id': self._secrets.get(self._chat_id_param),
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            }).encode(),
            timeout=10,
        ))
        try:
            payload = json.loads(response.text)
        except ValueError:
            payload = {}
        if response.status != 200 or not payload.get('ok'):
            # Não inclui a URL na mensagem: ela contém o token do bot
            raise TelegramError(f"Telegram HTTP {response.status}: {payload.get('description', response.text[:200])}")
