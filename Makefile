.PHONY: help install install-web run run-custom web web-prod test clean \
       build-container run-container deploy deploy-setup deploy-logs \
       deploy-status deploy-stop deploy-restart

SHELL := /bin/bash
PYTHON ?= python3
PORT ?= 8020
HOST ?= 127.0.0.1
SRC ?= source.txt
REQ ?= source-requirements.txt
OUT ?= result.md
OUT_JSON ?= result.json
CONFIG ?= config.json
CONTAINER_NAME ?= prose-critique
IMAGE_NAME ?= prose-critique
DEPLOY_HOST ?= alma
URL_PREFIX ?=

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install core dependencies
	$(PYTHON) -m pip install -r requirements.txt

install-web: ## Install core + web dependencies
	$(PYTHON) -m pip install -r requirements-web.txt

run: ## Run CLI with default files
	$(PYTHON) main.py -s $(SRC) -r $(REQ) -o $(OUT) -j $(OUT_JSON) -c $(CONFIG)

run-custom: ## Run CLI with custom SRC, REQ, OUT, OUT_JSON, CONFIG
	$(PYTHON) main.py -s $(SRC) -r $(REQ) -o $(OUT) -j $(OUT_JSON) -c $(CONFIG)

run-local: ## Run CLI with config.local.json (LiteLLM on alma:4000)
	$(PYTHON) main.py -s $(SRC) -r $(REQ) -o $(OUT) -j $(OUT_JSON) -c config.local.json

web: ## Start web UI (dev mode)
	$(PYTHON) -m web.app --host $(HOST) --port $(PORT) --debug

web-prod: ## Start web UI (production)
	$(PYTHON) -m web.app --host 0.0.0.0 --port $(PORT)

web-nginx: ## Start web UI with URL_PREFIX for nginx
	URL_PREFIX=$(URL_PREFIX) $(PYTHON) -m web.app --host $(HOST) --port $(PORT)

test: ## Run tests
	$(PYTHON) -m pytest tests/ -v

clean: ## Remove outputs and caches
	rm -f result.md result.json result.txt
	rm -rf workspace/logs/* workspace/runs/* workspace/cache/*
	rm -rf __pycache__ modules/__pycache__ modules/**/__pycache__
	rm -rf tests/__pycache__ web/__pycache__
	rm -rf .pytest_cache

# ── Container ──────────────────────────────────────────────────

build-container: ## Build container image (local platform)
	podman build -t $(IMAGE_NAME) -f Containerfile .

podman-build-amd64: ## Build container image for linux/amd64
	podman build --platform linux/amd64 -t $(IMAGE_NAME):amd64 -f Containerfile .

run-container: ## Run container
	podman run --rm -it \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8020 \
		--env-file .env \
		-v ./workspace:/app/workspace:z \
		-v ./config.json:/app/config.json:ro \
		$(IMAGE_NAME)

podman-local: build-container run-container ## Build and run locally

podman-cli: ## Run CLI inside container
	podman run --rm -it \
		--env-file .env \
		-v ./workspace:/app/workspace:z \
		-v ./config.json:/app/config.json:ro \
		-v ./$(SRC):/app/source.txt:ro \
		$(IMAGE_NAME) \
		python main.py -s source.txt -o result.md -j result.json

# ── Deploy to alma ─────────────────────────────────────────────

deploy-setup: ## One-time setup on deploy host
	ssh $(DEPLOY_HOST) 'mkdir -p ~/$(CONTAINER_NAME)/workspace/{logs,runs,cache}'
	ssh $(DEPLOY_HOST) 'mkdir -p ~/.config/systemd/user'
	scp .env.example $(DEPLOY_HOST):~/$(CONTAINER_NAME)/.env
	scp config.local.json $(DEPLOY_HOST):~/$(CONTAINER_NAME)/config.json
	scp $(CONTAINER_NAME).service $(DEPLOY_HOST):~/.config/systemd/user/$(CONTAINER_NAME).service
	ssh $(DEPLOY_HOST) 'systemctl --user daemon-reload'
	@echo "Setup complete. Edit ~/$(CONTAINER_NAME)/.env on $(DEPLOY_HOST) if needed."

deploy: podman-build-amd64 ## Deploy to alma (build, transfer, restart)
	podman save $(IMAGE_NAME):amd64 | ssh $(DEPLOY_HOST) 'podman load'
	ssh $(DEPLOY_HOST) 'podman tag localhost/$(IMAGE_NAME):amd64 $(IMAGE_NAME):latest'
	ssh $(DEPLOY_HOST) 'systemctl --user restart $(CONTAINER_NAME).service'
	@echo "Deployed. Check: make deploy-status"

deploy-logs: ## View container logs on deploy host
	ssh $(DEPLOY_HOST) 'podman logs -f $(CONTAINER_NAME)'

deploy-status: ## Check deployment status
	ssh $(DEPLOY_HOST) 'systemctl --user status $(CONTAINER_NAME).service; podman ps -f name=$(CONTAINER_NAME)'

deploy-stop: ## Stop container on deploy host
	ssh $(DEPLOY_HOST) 'systemctl --user stop $(CONTAINER_NAME).service'

deploy-restart: ## Restart container on deploy host
	ssh $(DEPLOY_HOST) 'systemctl --user restart $(CONTAINER_NAME).service'
