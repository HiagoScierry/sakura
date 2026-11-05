from typing import Any

from chalicelib.monitoring.models.check import CheckRequest

SQS_BATCH_LIMIT = 10


class SqsCheckQueue:
    def __init__(self, client: Any, queue_name: str) -> None:
        self._client = client
        self._queue_name = queue_name
        self._queue_url: str | None = None

    def enqueue(self, requests: list[CheckRequest]) -> None:
        for start in range(0, len(requests), SQS_BATCH_LIMIT):
            chunk = requests[start:start + SQS_BATCH_LIMIT]
            response = self._client.send_message_batch(QueueUrl=self._url(), Entries=[
                {'Id': str(i), 'MessageBody': request.model_dump_json()}
                for i, request in enumerate(chunk)
            ])
            if response.get('Failed'):
                raise RuntimeError(f"Falha ao enfileirar verificações: {response['Failed']}")

    def _url(self) -> str:
        if self._queue_url is None:
            self._queue_url = self._client.get_queue_url(QueueName=self._queue_name)['QueueUrl']
        return self._queue_url
