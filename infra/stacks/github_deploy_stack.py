"""Papel IAM que a pipeline do GitHub Actions assume via OIDC para publicar em produção (sem chaves de acesso)."""
from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

GITHUB_OIDC_URL = 'https://token.actions.githubusercontent.com'


class GithubDeployStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, repo: str, environment: str,
                 existing_provider_arn: str | None = None, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Só pode haver um provedor OIDC do GitHub por conta: reaproveita se já existir
        provider: iam.IOpenIdConnectProvider
        if existing_provider_arn:
            provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, 'GithubOidc', existing_provider_arn)
        else:
            provider = iam.OpenIdConnectProvider(
                self, 'GithubOidc', url=GITHUB_OIDC_URL, client_ids=['sts.amazonaws.com'])

        # Só jobs deste repositório rodando no environment protegido conseguem assumir o papel
        role = iam.Role(
            self, 'DeployRole',
            role_name=f'chalice-api-github-deploy-{environment}',
            assumed_by=iam.OpenIdConnectPrincipal(provider, conditions={
                'StringEquals': {
                    'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
                    'token.actions.githubusercontent.com:sub': f'repo:{repo}:environment:{environment}',
                },
            }),
            description=f'GitHub Actions ({repo}) publica o chalice-api em {environment}',
        )

        # O deploy em si é feito pelos papéis do `cdk bootstrap`; aqui só a permissão de assumi-los
        role.add_to_policy(iam.PolicyStatement(
            actions=['sts:AssumeRole'],
            resources=[f'arn:aws:iam::{self.account}:role/cdk-*'],
        ))
        # `make preflight` confere se os segredos de produção existem (não lê os valores)
        role.add_to_policy(iam.PolicyStatement(
            actions=['ssm:GetParameters'],
            resources=[self.format_arn(service='ssm', resource='parameter',
                                       resource_name=f'chalice-api/{environment}/*')],
        ))

        CfnOutput(self, 'DeployRoleArn', value=role.role_arn)
