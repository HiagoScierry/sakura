import json
import time
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from chalicelib.monitoring.models.check import CheckResult
from chalicelib.monitoring.models.service import Health, Service


def _to_item(data: Any) -> Any:
    # DynamoDB não aceita float; converte para Decimal
    if isinstance(data, BaseModel):
        data = data.model_dump(mode='json')
    return json.loads(json.dumps(data), parse_float=Decimal)


def _from_item(item: Any) -> Any:
    return json.loads(json.dumps(item, default=lambda d: int(d) if d % 1 == 0 else float(d)))


class DynamoServiceRepository:
    """Item: { id, spec, health, created_at, updated_at }."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def list(self) -> list[Service]:
        response = self._table.scan()
        items = response['Items']
        while 'LastEvaluatedKey' in response:
            response = self._table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        return [Service.model_validate(_from_item(item)) for item in items]

    def get(self, service_id: str) -> Service | None:
        item = self._table.get_item(Key={'id': service_id}).get('Item')
        return Service.model_validate(_from_item(item)) if item else None

    def add(self, service: Service) -> None:
        self._table.put_item(Item=_to_item(service), ConditionExpression='attribute_not_exists(id)')

    def save_spec(self, service: Service) -> bool:
        return self._update(service.id, {
            'spec': _to_item(service.spec), 'updated_at': service.updated_at.isoformat()})

    def save_health(self, service_id: str, health: Health) -> None:
        self._update(service_id, {'health': _to_item(health)})

    def delete(self, service_id: str) -> bool:
        response = self._table.delete_item(Key={'id': service_id}, ReturnValues='ALL_OLD')
        return 'Attributes' in response

    def _update(self, service_id: str, values: dict[str, Any]) -> bool:
        try:
            self._table.update_item(
                Key={'id': service_id},
                UpdateExpression='SET ' + ', '.join(f'#{k} = :{k}' for k in values),
                ConditionExpression='attribute_exists(id)',
                ExpressionAttributeNames={f'#{k}': k for k in values},
                ExpressionAttributeValues={f':{k}': v for k, v in values.items()},
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False
        return True


class DynamoCheckHistory:
    """Item: CheckResult + `expires_at` (TTL)."""

    def __init__(self, table: Any, ttl_days: int) -> None:
        self._table = table
        self._ttl_seconds = ttl_days * 86400

    def add(self, check: CheckResult) -> None:
        self._table.put_item(Item={**_to_item(check), 'expires_at': int(time.time()) + self._ttl_seconds})

    def recent(self, service_id: str, limit: int) -> list[CheckResult]:
        response = self._table.query(
            KeyConditionExpression=Key('service_id').eq(service_id),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [CheckResult.model_validate(_from_item(item)) for item in response['Items']]
