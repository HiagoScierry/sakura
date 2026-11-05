"""Toda a infraestrutura do monitor num stack só: dados, fila e o app Chalice."""
import os
from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, CfnResource, Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sqs as sqs
from chalice.cdk import Chalice
from constructs import Construct

APP_DIR = Path(__file__).resolve().parents[2]

# Worker que verifica um serviço. Pior caso hoje: 4 tentativas x 30s x 2 requisições (Supabase) = 240s.
CHECK_WORKER_TIMEOUT = Duration.minutes(5)


class MonitorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        is_prod = stage == 'prod'
        ssm_prefix = f'chalice-api/{stage}'
        check_queue_name = f'chalice-api-checks-{stage}'

        # -------------------------------------------------------------------
        # Dados
        # -------------------------------------------------------------------
        services = dynamodb.TableV2(
            self, 'Services',
            partition_key=dynamodb.Attribute(name='id', type=dynamodb.AttributeType.STRING),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True),
            removal_policy=RemovalPolicy.RETAIN,  # o cadastro não some junto com o stack
        )

        check_history = dynamodb.TableV2(
            self, 'CheckHistory',
            partition_key=dynamodb.Attribute(name='service_id', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name='checked_at', type=dynamodb.AttributeType.STRING),
            time_to_live_attribute='expires_at',
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
        )

        # -------------------------------------------------------------------
        # Fila do fan-out: uma mensagem por serviço a cada hora
        # -------------------------------------------------------------------
        dead_letters = sqs.Queue(
            self, 'CheckDeadLetters',
            queue_name=f'{check_queue_name}-dlq',
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )
        checks = sqs.Queue(
            self, 'Checks',
            queue_name=check_queue_name,  # nome fixo: o Chalice precisa dele ao empacotar o gatilho SQS
            visibility_timeout=Duration.seconds(CHECK_WORKER_TIMEOUT.to_seconds() * 6),  # recomendação AWS
            retention_period=Duration.hours(1),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(queue=dead_letters, max_receive_count=3),
        )

        # -------------------------------------------------------------------
        # App Chalice: API, agendamentos, worker SQS e notificações
        # -------------------------------------------------------------------
        # `chalicelib.config` lê o nome da fila no import, e o Chalice empacota neste mesmo processo
        os.environ['CHECK_QUEUE_NAME'] = check_queue_name
        app = Chalice(
            self, 'App',
            source_dir=str(APP_DIR),
            stage_config={
                'api_gateway_stage': 'api',
                'lambda_timeout': 30,
                'environment_variables': {
                    'SERVICES_TABLE': services.table_name,
                    'CHECK_HISTORY_TABLE': check_history.table_name,
                    'CHECK_HISTORY_TTL_DAYS': '30',
                    'CHECK_QUEUE_NAME': check_queue_name,
                    'EVENT_BUS_NAME': 'default',
                    'API_TOKEN_PARAM': f'/{ssm_prefix}/api-token',
                    'TELEGRAM_BOT_TOKEN_PARAM': f'/{ssm_prefix}/telegram-bot-token',
                    'TELEGRAM_CHAT_ID_PARAM': f'/{ssm_prefix}/telegram-chat-id',
                },
            },
        )
        worker: CfnResource = app.get_resource('CheckService')
        worker.add_property_override('Timeout', int(CHECK_WORKER_TIMEOUT.to_seconds()))
        # O gatilho SQS referencia a fila pelo nome; garante que ela seja criada antes do worker
        worker.add_resource_dependency(checks.node.default_child)  # type: ignore[arg-type]

        # -------------------------------------------------------------------
        # Permissões, geradas a partir dos recursos
        # -------------------------------------------------------------------
        role = app.get_role('DefaultRole')
        services.grant_read_write_data(role)
        check_history.grant_read_write_data(role)
        checks.grant_send_messages(role)
        checks.grant_consume_messages(role)
        events.EventBus.from_event_bus_name(self, 'DefaultBus', 'default').grant_put_events_to(role)
        role.add_to_principal_policy(iam.PolicyStatement(
            actions=['ssm:GetParameter'],
            resources=[self.format_arn(service='ssm', resource='parameter', resource_name=f'{ssm_prefix}/*')],
        ))

        # -------------------------------------------------------------------
        # Outputs (usados pelo `make local` para apontar o app local para este stage)
        # -------------------------------------------------------------------
        CfnOutput(self, 'ServicesTableName', value=services.table_name)
        CfnOutput(self, 'CheckHistoryTableName', value=check_history.table_name)
        CfnOutput(self, 'CheckQueueName', value=checks.queue_name)
