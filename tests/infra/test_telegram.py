import json

import pytest

from chalicelib.infra.telegram import TelegramError, TelegramSender
from tests.fakes import FakeHttp, FakeSecrets


def test_posts_to_bot_api():
    http = FakeHttp()
    http.respond(200, '{"ok": true, "result": {}}')
    sender = TelegramSender(http, FakeSecrets({'/tg/token': '123:ABC', '/tg/chat': '-100987'}), '/tg/token', '/tg/chat')

    sender.send('<b>oi</b>')

    request = http.requests[0]
    assert request.url == 'https://api.telegram.org/bot123:ABC/sendMessage'
    assert request.method == 'POST'
    assert json.loads(request.body) == {'chat_id': '-100987', 'text': '<b>oi</b>',
                                        'parse_mode': 'HTML', 'disable_web_page_preview': True}


def test_errors_raise_without_leaking_token():
    http = FakeHttp()
    http.respond(400, '{"ok": false, "description": "Bad Request: chat not found"}')
    sender = TelegramSender(http, FakeSecrets({'/t': 'SECRET-TOKEN', '/c': '1'}), '/t', '/c')
    with pytest.raises(TelegramError) as error:
        sender.send('oi')
    assert 'chat not found' in str(error.value) and 'SECRET-TOKEN' not in str(error.value)
