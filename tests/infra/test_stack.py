"""Garantias do stack CDK (sintetiza o app Chalice de verdade; leva alguns segundos)."""
import sys
from pathlib import Path

import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
from stacks.monitor_stack import MonitorStack  # noqa: E402


@pytest.fixture(scope='module')
def template(tmp_path_factory: pytest.TempPathFactory, monkeypatch_module: pytest.MonkeyPatch) -> Template:
    monkeypatch_module.chdir(tmp_path_factory.mktemp('cdk'))  # chalice.out vai para um diretório temporário
    return Template.from_stack(MonitorStack(App(), 'test', stage='test'))


@pytest.fixture(scope='module')
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def test_tables_and_queues(template: Template) -> None:
    template.resource_count_is('AWS::DynamoDB::GlobalTable', 2)
    template.has_resource('AWS::DynamoDB::GlobalTable', {
        'DeletionPolicy': 'Retain',
        'Properties': Match.object_like({'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}]}),
    })
    template.has_resource_properties('AWS::SQS::Queue', {
        'QueueName': 'chalice-api-checks-test',
        'VisibilityTimeout': 1800,
        'RedrivePolicy': Match.object_like({'maxReceiveCount': 3}),
    })


def test_worker_fits_worst_case_and_waits_for_queue(template: Template) -> None:
    worker = template.to_json()['Resources']['CheckService']
    assert worker['Properties']['Timeout'] == 300
    assert any(dep.startswith('Checks') for dep in worker['DependsOn'])


def test_all_functions_share_one_role_with_generated_grants(template: Template) -> None:
    template.resource_count_is('AWS::IAM::Role', 1)
    actions: set[str] = set()
    for policy in template.find_resources('AWS::IAM::Policy').values():
        for statement in policy['Properties']['PolicyDocument']['Statement']:
            action = statement['Action']
            actions.update(action if isinstance(action, list) else [action])
    assert {'dynamodb:PutItem', 'dynamodb:Query', 'sqs:SendMessage', 'sqs:ReceiveMessage',
            'events:PutEvents', 'ssm:GetParameter'} <= actions


def test_app_receives_table_and_parameter_names(template: Template) -> None:
    template.has_resource_properties('AWS::Serverless::Function', {
        'Environment': {'Variables': Match.object_like({
            'SERVICES_TABLE': {'Ref': Match.string_like_regexp('^Services')},
            'CHECK_QUEUE_NAME': 'chalice-api-checks-test',
            'TELEGRAM_BOT_TOKEN_PARAM': '/chalice-api/test/telegram-bot-token',
        })},
    })
