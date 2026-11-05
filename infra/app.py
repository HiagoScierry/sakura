"""Entrada do CDK. Um stage por execução: `npx cdk deploy -c stage=dev`."""
import aws_cdk as cdk

from stacks.monitor_stack import MonitorStack

app = cdk.App()
stage = app.node.try_get_context('stage') or 'dev'

MonitorStack(app, f'chalice-api-{stage}', stage=stage)

app.synth()
