import os
from typing import Self

from pydantic import BaseModel, Field

EVENT_SOURCE = 'chalice-api.monitoring'
# Precisa estar disponível no import (o Chalice lê no deploy para criar o gatilho SQS)
CHECK_QUEUE_NAME = os.environ.get('CHECK_QUEUE_NAME', 'chalice-api-checks-dev')


class Settings(BaseModel):
    services_table: str
    check_history_table: str
    check_history_ttl_days: int = Field(default=30, ge=1)
    check_queue_name: str = CHECK_QUEUE_NAME
    event_bus_name: str = 'default'
    api_token_param: str
    telegram_bot_token_param: str
    telegram_chat_id_param: str

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            services_table=os.environ['SERVICES_TABLE'],
            check_history_table=os.environ['CHECK_HISTORY_TABLE'],
            check_history_ttl_days=int(os.environ.get('CHECK_HISTORY_TTL_DAYS', '30')),
            event_bus_name=os.environ.get('EVENT_BUS_NAME', 'default'),
            api_token_param=os.environ['API_TOKEN_PARAM'],
            telegram_bot_token_param=os.environ['TELEGRAM_BOT_TOKEN_PARAM'],
            telegram_chat_id_param=os.environ['TELEGRAM_CHAT_ID_PARAM'],
        )
