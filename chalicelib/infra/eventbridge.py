from typing import Any

from chalicelib.monitoring.models.events import StatusChanged


class EventBridgePublisher:
    def __init__(self, client: Any, bus_name: str, source: str) -> None:
        self._client = client
        self._bus_name = bus_name
        self._source = source

    def publish(self, event: StatusChanged) -> None:
        response = self._client.put_events(Entries=[{
            'Source': self._source,
            'DetailType': type(event).__name__,
            'Detail': event.model_dump_json(),
            'EventBusName': self._bus_name,
        }])
        if response.get('FailedEntryCount'):
            raise RuntimeError(f"Falha ao publicar evento: {response['Entries']}")
