"""Composition root: monta os casos de uso com as implementações concretas."""
from dataclasses import dataclass

import boto3

from chalicelib.config import EVENT_SOURCE, Settings
from chalicelib.infra.dynamo import DynamoCheckHistory, DynamoServiceRepository
from chalicelib.infra.eventbridge import EventBridgePublisher
from chalicelib.infra.http_client import UrllibHttpClient
from chalicelib.infra.sqs import SqsCheckQueue
from chalicelib.infra.ssm import SsmSecretStore
from chalicelib.infra.telegram import TelegramSender
from chalicelib.monitoring.models.service import (HttpServiceSpec, SupabaseServiceSpec,
                                                  ZapiServiceSpec)
from chalicelib.monitoring.ports import CheckHistory, CheckQueue, EventPublisher, ServiceRepository
from chalicelib.monitoring.probes.http import HttpProbe
from chalicelib.monitoring.probes.prober import ServiceProber
from chalicelib.monitoring.probes.supabase import SupabaseProbe
from chalicelib.monitoring.probes.zapi import ZapiProbe
from chalicelib.monitoring.use_cases.check_service import CheckService
from chalicelib.monitoring.use_cases.get_check_history import GetCheckHistory
from chalicelib.monitoring.use_cases.get_dashboard import GetDashboard
from chalicelib.monitoring.use_cases.get_service import GetService, ListServices
from chalicelib.monitoring.use_cases.register_service import RegisterService
from chalicelib.monitoring.use_cases.remove_service import RemoveService
from chalicelib.monitoring.use_cases.schedule_checks import ScheduleChecks
from chalicelib.monitoring.use_cases.update_service import UpdateService
from chalicelib.notification.ports import MessageSender
from chalicelib.notification.use_cases.notify_status_change import NotifyStatusChange
from chalicelib.notification.use_cases.send_daily_report import SendDailyReport
from chalicelib.shared.http import HttpClient
from chalicelib.shared.secrets import SecretStore


@dataclass(frozen=True)
class Monitoring:
    register_service: RegisterService
    update_service: UpdateService
    remove_service: RemoveService
    list_services: ListServices
    get_service: GetService
    schedule_checks: ScheduleChecks
    check_service: CheckService
    get_dashboard: GetDashboard
    get_check_history: GetCheckHistory


@dataclass(frozen=True)
class Notification:
    notify_status_change: NotifyStatusChange
    send_daily_report: SendDailyReport


@dataclass(frozen=True)
class Container:
    settings: Settings
    secrets: SecretStore
    monitoring: Monitoring
    notification: Notification


def wire(
    settings: Settings,
    *,
    services: ServiceRepository,
    history: CheckHistory,
    queue: CheckQueue,
    publisher: EventPublisher,
    secrets: SecretStore,
    http: HttpClient,
    sender: MessageSender,
) -> Container:
    """Liga os casos de uso às dependências recebidas (reaproveitado pelos testes)."""
    prober = ServiceProber({
        HttpServiceSpec: HttpProbe(http, secrets),
        SupabaseServiceSpec: SupabaseProbe(http, secrets),
        ZapiServiceSpec: ZapiProbe(http, secrets),
    })
    get_dashboard = GetDashboard(services)
    return Container(
        settings=settings,
        secrets=secrets,
        monitoring=Monitoring(
            register_service=RegisterService(services),
            update_service=UpdateService(services),
            remove_service=RemoveService(services),
            list_services=ListServices(services),
            get_service=GetService(services),
            schedule_checks=ScheduleChecks(services, queue),
            check_service=CheckService(services, history, prober, publisher),
            get_dashboard=get_dashboard,
            get_check_history=GetCheckHistory(services, history),
        ),
        notification=Notification(
            notify_status_change=NotifyStatusChange(sender),
            send_daily_report=SendDailyReport(get_dashboard, sender),
        ),
    )


def build_container(settings: Settings) -> Container:
    dynamodb = boto3.resource('dynamodb')
    secrets = SsmSecretStore(boto3.client('ssm'))
    http = UrllibHttpClient()
    return wire(
        settings,
        services=DynamoServiceRepository(dynamodb.Table(settings.services_table)),
        history=DynamoCheckHistory(dynamodb.Table(settings.check_history_table), settings.check_history_ttl_days),
        queue=SqsCheckQueue(boto3.client('sqs'), settings.check_queue_name),
        publisher=EventBridgePublisher(boto3.client('events'), settings.event_bus_name, EVENT_SOURCE),
        secrets=secrets,
        http=http,
        sender=TelegramSender(http, secrets, settings.telegram_bot_token_param, settings.telegram_chat_id_param),
    )


_container: Container | None = None


def get_container() -> Container:
    """Criado sob demanda e reaproveitado entre invocações do mesmo container Lambda."""
    global _container
    if _container is None:
        _container = build_container(Settings.from_env())
    return _container


def set_container(container: Container | None) -> None:
    """Permite substituir as dependências (testes)."""
    global _container
    _container = container
