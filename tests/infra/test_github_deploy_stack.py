"""O papel da pipeline só pode ser assumido pelo repositório certo, no environment protegido."""
import sys
from pathlib import Path

from aws_cdk import App
from aws_cdk.assertions import Match, Template

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
from stacks.github_deploy_stack import GithubDeployStack  # noqa: E402


def synth(**kwargs: str) -> Template:
    return Template.from_stack(GithubDeployStack(App(), 'test', repo='acme/monitor', environment='prod', **kwargs))


def test_role_trusts_only_repo_environment() -> None:
    synth().has_resource_properties('AWS::IAM::Role', {
        'AssumeRolePolicyDocument': {'Statement': [Match.object_like({
            'Action': 'sts:AssumeRoleWithWebIdentity',
            'Condition': {'StringEquals': {
                'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
                'token.actions.githubusercontent.com:sub': 'repo:acme/monitor:environment:prod',
            }},
        })]},
    })


def test_role_only_assumes_cdk_roles_and_checks_secrets() -> None:
    statements = [s for p in synth().find_resources('AWS::IAM::Policy').values()
                  for s in p['Properties']['PolicyDocument']['Statement']]
    assert sorted(s['Action'] for s in statements) == ['ssm:GetParameters', 'sts:AssumeRole']


def test_reuses_existing_oidc_provider() -> None:
    template = synth(existing_provider_arn='arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com')
    template.resource_count_is('Custom::AWSCDKOpenIdConnectProvider', 0)
