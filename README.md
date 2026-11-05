# chalice-api — monitor de serviços

Verifica de hora em hora se Supabase, Z-API, APIs e monólitos estão no ar e avisa no Telegram
quando algo cai ou volta. Todo dia às 09:00 (Brasília) manda um resumo.

## Regras de negócio

Em cada contexto: modelos em `models/`, regras em `rules.py` (uma política por regra, descrita na docstring)
e fluxos em `use_cases/`.

| Regra | Onde |
|---|---|
| A verificação de hora em hora cobre só serviços habilitados; a manual roda em qualquer um | `monitoring/rules.py` → `MonitoringPolicy` |
| Um serviço só é declarado fora depois de falhar todas as tentativas (1 + `retries`) | `monitoring/rules.py` → `RetryPolicy` |
| Alerta só quando o estado vira; serviço novo no ar não alerta; serviço que continua fora não repete o alerta | `monitoring/rules.py` → `AlertPolicy` |
| `since` da saúde só reinicia quando o estado muda | `monitoring/models/service.py` → `Health.after` |
| Resumo diário: nada monitorado / tudo rodando / lista do que segue fora; serviço nunca verificado não conta como fora | `notification/rules.py` → `DailyReportPolicy` |
| O que é "saudável" para cada tipo de serviço | `monitoring/probes/*` (docstring de cada sonda) |

## Fluxos (casos de uso)

```
EventBridge (1h)        ─► ScheduleChecks ─► SQS (1 msg/serviço) ─► CheckService ─► histórico + saúde
                                               └─► DLQ (3 falhas)         └─► ServiceWentDown / ServiceRecovered
                                                                                 └─► NotifyStatusChange ─► Telegram
EventBridge (09:00 BRT) ─► SendDailyReport ─► Telegram
API                     ─► RegisterService, UpdateService, RemoveService, ListServices, GetService,
                           GetDashboard, GetCheckHistory, CheckService (manual), ScheduleChecks
```

## Estrutura

```
app.py                              # registra os Blueprints
chalicelib/
  monitoring/                       # CONTEXTO: monitoramento
    models/                         #   modelos pydantic do contexto
      service.py                    #     Service, ServiceSpec (Http/Supabase/Zapi), Health
      check.py                      #     ProbeOutcome, CheckResult, CheckRequest
      events.py                     #     ServiceWentDown, ServiceRecovered
      dashboard.py                  #     Dashboard, ServiceOverview
    rules.py                        #   MonitoringPolicy, RetryPolicy, AlertPolicy
    errors.py                       #   ServiceNotFound
    ports.py                        #   o que o contexto precisa de fora (repositórios, fila, eventos)
    probes/                         #   como sondar cada tipo de serviço
    use_cases/                      #   um arquivo por ação: register_service, check_service, ...
  notification/                     # CONTEXTO: notificação
    models.py                       #   DailyReport
    rules.py                        #   DailyReportPolicy
    messages.py                     #   texto das mensagens
    ports.py                        #   MessageSender
    use_cases/                      #   notify_status_change, send_daily_report
  shared/                           # clock, contratos de HTTP e segredos
  infra/                            # DynamoDB, SQS, EventBridge, SSM, HTTP, Telegram
  entrypoints/                      # api/ (rotas) e jobs.py (cron, SQS, eventos) — só traduzem e chamam casos de uso
  container.py                      # liga casos de uso às implementações
  config.py
infra/                              # CDK (Python): app.py + stacks/monitor_stack.py
tests/                              # mesma divisão: monitoring/, notification/, infra/, entrypoints/
```

**Novo tipo de serviço:** spec em `monitoring/models/service.py` (incluir na união `ServiceSpec`),
sonda em `monitoring/probes/` e registro em `container.py`.
**Novo canal de notificação:** implemente `notification/ports.MessageSender` e troque em `container.py`.

## Tipos de serviço

| `type` | Campos específicos | Saudável quando |
|---|---|---|
| `api`, `monolith` | `url`, `method`, `headers`, `body`, `expected_status`, `expect_contains`, `expect_json` | status esperado (padrão 2xx/3xx) e, se informados, texto/JSON presentes; aceita `{{ssm:/param}}` |
| `supabase` | `project_url`, `api_key_param`, `table` (opcional) | `/auth/v1/health` responde 200 e, com `table`, `SELECT ... LIMIT 1` responde |
| `zapi` | `instance_id_param`, `token_param`, `client_token_param`, `require_smartphone` | instância `connected` (e celular conectado, se exigido) |

Comuns: `name`, `enabled` (true), `timeout_seconds` (10), `retries` (1), `tags`.
Campos `*_param` são nomes de parâmetros SSM — segredos nunca vão para o DynamoDB.

## Notificações (Telegram)

| Quando | Mensagem |
|---|---|
| Serviço cai | 🔴 nome, tipo, motivo, HTTP, latência e horário |
| Serviço volta | 🟢 nome e quanto tempo ficou fora |
| 09:00 (Brasília) | ✅ "tudo rodando" — ou ⚠️ lista do que segue fora e há quanto tempo |

Bot: crie com o [@BotFather](https://t.me/BotFather) (`/newbot`), adicione ao grupo e pegue o `chat_id`
em `https://api.telegram.org/bot<token>/getUpdates` (grupos têm id negativo).

## Desenvolvimento

Requisitos: Python 3.12, Node.js 22 ou 24 (o CDK roda sobre Node, mesmo escrito em Python), AWS CLI e GNU Make.
No Windows, rode o `make` pelo **Git Bash**.

```bash
make install     # venv + dependências Python + CLI do CDK (fixado em infra/package.json)
make check       # pytest + mypy strict
make help        # lista todos os alvos
```

### Rodando localmente

```bash
make local             # API em http://localhost:8000
make local PORT=9000
```

O `make local` lê os outputs do stack `chalice-api-dev` (nomes das tabelas e da fila) e sobe o
`chalice local` apontando para esses recursos. Ou seja, **o stage dev precisa estar publicado** e a API
local usa os dados reais do dev: uma verificação manual pode gerar alerta no Telegram.
Os agendamentos e o worker da fila não rodam localmente; `POST /checks` enfileira no SQS do dev e o
worker publicado processa.

## Infraestrutura (CDK)

Tudo fica num stack só, em `infra/stacks/monitor_stack.py`: tabelas, fila + DLQ e o app Chalice
(construct oficial `chalice.cdk`). O CDK passa os nomes das tabelas para o app e gera as permissões
IAM a partir dos recursos (`table.grant_read_write_data(...)`), sem policy JSON manual.
A tabela de serviços tem `RemovalPolicy.RETAIN`: destruir o stack não apaga o cadastro.

## Deploy

```bash
# 1. Uma vez por conta/região
make bootstrap

# 2. Segredos obrigatórios (SecureString não é criado pelo CDK); troque "prod" por "dev" para o dev
aws ssm put-parameter --type SecureString --name /chalice-api/prod/api-token --value "<token-forte>"
aws ssm put-parameter --type SecureString --name /chalice-api/prod/telegram-bot-token --value "<token do BotFather>"
aws ssm put-parameter --type SecureString --name /chalice-api/prod/telegram-chat-id --value "<chat_id>"
#    e os dos serviços que for cadastrar, ex.: /chalice-api/prod/supabase-key, /chalice-api/prod/zapi-token...

# 3. Deploy
make deploy-dev
make deploy-prod
```

| Alvo | O que faz |
|---|---|
| `make deploy-dev` | testes + mypy → confere segredos no SSM → `cdk deploy` do dev, sem perguntar |
| `make deploy-prod` | testes + mypy → confere segredos no SSM → `cdk diff` de prod → pede para digitar `prod` (mostra a conta AWS) → `cdk deploy`, que ainda pergunta de novo se houver mudança de permissão IAM |
| `make diff STAGE=prod` | só mostra o que mudaria |
| `make synth STAGE=prod` | só gera o CloudFormation em `infra/cdk.out/` |

Cada stage é um stack isolado (`chalice-api-dev`, `chalice-api-prod`) com segredos em `/chalice-api/<stage>/...`.
Em prod as duas tabelas são retidas se o stack for destruído. A URL da API aparece nos outputs do deploy (`EndpointURL`).

## Pipeline (GitHub Actions)

Toda tag `vX.Y.Z` publica em produção (`.github/workflows/release.yml`):

```bash
git tag v1.0.0 && git push origin v1.0.0
```

1. **Testes e tipos:** confere se a tag é semver e aponta para um commit da `main`, depois `make check`.
2. **Deploy em produção** (environment `prod` do GitHub): assume o papel IAM via OIDC (sem chave de acesso
   guardada no GitHub), roda `make release` (check → segredos no SSM → `cdk deploy`) e cria a GitHub Release
   com as notas geradas a partir dos commits.

Deploys de produção rodam um por vez. Tags fora do padrão (`v1.0`, `v1.0.0-rc1`) não publicam.

### Configuração (uma vez)

```bash
make bootstrap                     # se ainda não fez
make github-access                 # cria o papel IAM chalice-api-github-deploy-prod (output DeployRoleArn)
# se a conta já tem o provedor OIDC do GitHub:
make github-access OIDC_PROVIDER_ARN=arn:aws:iam::<conta>:oidc-provider/token.actions.githubusercontent.com
```

No GitHub, em *Settings → Environments*, crie o environment **`prod`** com:
- variables `AWS_DEPLOY_ROLE_ARN` (o output acima) e `AWS_REGION`;
- *Required reviewers*, se quiser aprovar cada deploy antes de rodar;
- *Deployment branches and tags* → tags `v*.*.*`.

O papel só aceita jobs deste repositório no environment `prod` e só tem permissão de assumir os papéis do
`cdk bootstrap` e de conferir se os segredos de prod existem.

## Cadastrando serviços

```powershell
$url = "<EndpointURL do cdk deploy>"
$h = @{ Authorization = "Bearer <token-forte>" }

Invoke-RestMethod "$url/services" -Method Post -Headers $h -ContentType 'application/json' -Body '{
  "type": "supabase", "name": "Supabase prod",
  "project_url": "https://<projeto>.supabase.co",
  "api_key_param": "/chalice-api/dev/supabase-key", "table": "clientes"
}'

Invoke-RestMethod "$url/services" -Method Post -Headers $h -ContentType 'application/json' -Body '{
  "type": "zapi", "name": "Z-API WhatsApp",
  "instance_id_param": "/chalice-api/dev/zapi-instance",
  "token_param": "/chalice-api/dev/zapi-token",
  "client_token_param": "/chalice-api/dev/zapi-client-token",
  "require_smartphone": true
}'

Invoke-RestMethod "$url/services" -Method Post -Headers $h -ContentType 'application/json' -Body '{
  "type": "monolith", "name": "ERP", "url": "https://erp.empresa.com/health", "expected_status": [200]
}'
```

## Endpoints (todos exceto `/` exigem `Authorization: Bearer <token>`)

| Método | Rota | Caso de uso |
|---|---|---|
| GET | `/dashboard` | GetDashboard |
| GET / POST | `/services` | ListServices / RegisterService |
| GET / PATCH / DELETE | `/services/{id}` | GetService / UpdateService / RemoveService |
| GET | `/services/{id}/checks?limit=24` | GetCheckHistory |
| POST | `/services/{id}/checks` | CheckService (manual, síncrono) |
| POST | `/checks` | ScheduleChecks (assíncrono, 202) |

Logs (os nomes das funções são gerados pelo CloudFormation e começam com o nome do stack):

```powershell
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'chalice-api-dev')].FunctionName"
aws logs tail /aws/lambda/<nome da função CheckService> --follow
```

Remover: `npx cdk destroy -c stage=dev` (a tabela de serviços é mantida e precisa ser apagada à mão).
