"""Entrada do CDK para o acesso da pipeline à AWS (uma vez por conta): `make github-access`."""
import aws_cdk as cdk

from stacks.github_deploy_stack import GithubDeployStack

app = cdk.App()

GithubDeployStack(
    app, 'chalice-api-github',
    repo=app.node.try_get_context('github_repo') or 'HiagoScierry/sakura',
    environment='prod',
    existing_provider_arn=app.node.try_get_context('oidc_provider_arn'),
)

app.synth()
