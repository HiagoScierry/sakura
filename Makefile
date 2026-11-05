# chalice-api — atalhos de desenvolvimento e deploy.
# No Windows, rode pelo Git Bash (os comandos usam sh). Veja os alvos com: make help

STAGE ?= dev
PORT  ?= 8000
PYTHON_BOOTSTRAP ?= python

ifeq ($(OS),Windows_NT)
  VENV_BIN := .venv/Scripts
else
  VENV_BIN := .venv/bin
endif

# Evita que o Git Bash converta "/chalice-api/..." (nomes de parâmetros SSM) em caminhos do Windows
export MSYS_NO_PATHCONV := 1

# O CDK executa o app Python do infra/ com o Python do venv
CDK = cd infra && npx cdk --app "$(abspath $(VENV_BIN))/python app.py"

# Parâmetros do SSM sem os quais o app não sobe
REQUIRED_PARAMS = api-token telegram-bot-token telegram-chat-id

# $(call stack_output,<OutputKey>) -> valor do output do stack do $(STAGE)
stack_output = $$(aws cloudformation describe-stacks --stack-name chalice-api-$(STAGE) \
	--query "Stacks[0].Outputs[?OutputKey=='$(1)'].OutputValue" --output text 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help install test typecheck check local synth diff bootstrap preflight deploy-dev deploy-prod

help: ## Lista os alvos disponíveis
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Desenvolvimento
# ---------------------------------------------------------------------------

install: ## Cria o venv e instala dependências (Python + CLI do CDK)
	$(PYTHON_BOOTSTRAP) -m venv .venv
	$(VENV_BIN)/python -m pip install -q --upgrade pip
	$(VENV_BIN)/python -m pip install -q -r requirements-dev.txt
	cd infra && npm install --no-fund --no-audit

test: ## Roda os testes
	$(VENV_BIN)/python -m pytest -q

typecheck: ## Checagem de tipos (mypy strict)
	$(VENV_BIN)/python -m mypy

check: test typecheck ## Testes + tipos

local: ## Sobe a API local (PORT=8000) usando os recursos AWS do stage dev
	@services=$(call stack_output,ServicesTableName); \
	history=$(call stack_output,CheckHistoryTableName); \
	queue=$(call stack_output,CheckQueueName); \
	if [ -z "$$services" ] || [ "$$services" = "None" ]; then \
		echo "Stack chalice-api-$(STAGE) não encontrado. Rode 'make deploy-dev' primeiro."; exit 1; \
	fi; \
	echo "API local em http://localhost:$(PORT) -> tabelas $$services / $$history, fila $$queue"; \
	echo "Atenção: usa os dados reais do stage $(STAGE); verificações manuais podem gerar alertas no Telegram."; \
	SERVICES_TABLE=$$services \
	CHECK_HISTORY_TABLE=$$history \
	CHECK_QUEUE_NAME=$$queue \
	EVENT_BUS_NAME=default \
	API_TOKEN_PARAM=/chalice-api/$(STAGE)/api-token \
	TELEGRAM_BOT_TOKEN_PARAM=/chalice-api/$(STAGE)/telegram-bot-token \
	TELEGRAM_CHAT_ID_PARAM=/chalice-api/$(STAGE)/telegram-chat-id \
	$(VENV_BIN)/chalice local --port $(PORT) --stage dev

# ---------------------------------------------------------------------------
# Infra / deploy
# ---------------------------------------------------------------------------

synth: ## Gera o CloudFormation (STAGE=dev) sem publicar nada
	$(CDK) synth -c stage=$(STAGE) --quiet

diff: ## Mostra o que mudaria na AWS (STAGE=dev)
	$(CDK) diff -c stage=$(STAGE)

bootstrap: ## Prepara a conta/região para o CDK (uma vez só)
	$(CDK) bootstrap

preflight: ## Confere se os parâmetros obrigatórios existem no SSM (STAGE=dev)
	@missing=$$(aws ssm get-parameters \
		--names $(foreach p,$(REQUIRED_PARAMS),/chalice-api/$(STAGE)/$(p)) \
		--query InvalidParameters --output text); \
	if [ -n "$$missing" ] && [ "$$missing" != "None" ]; then \
		echo "Faltam parâmetros no SSM ($(STAGE)): $$missing"; \
		echo "Crie com: aws ssm put-parameter --type SecureString --name <nome> --value <valor>"; \
		exit 1; \
	fi; \
	echo "SSM ok: $(REQUIRED_PARAMS)"

deploy-dev: ## Deploy no stage dev
	$(MAKE) --no-print-directory check
	$(MAKE) --no-print-directory preflight STAGE=dev
	$(CDK) deploy -c stage=dev --require-approval never

deploy-prod: ## Deploy em PRODUÇÃO: testes, tipos, SSM, diff e confirmação manual
	$(MAKE) --no-print-directory check
	$(MAKE) --no-print-directory preflight STAGE=prod
	$(CDK) diff -c stage=prod
	@account=$$(aws sts get-caller-identity --query Account --output text); \
	printf '\nDeploy em PRODUÇÃO na conta %s. Digite "prod" para confirmar: ' "$$account"; \
	read answer; \
	if [ "$$answer" != "prod" ]; then echo "Cancelado."; exit 1; fi
	$(CDK) deploy -c stage=prod --require-approval broadening
