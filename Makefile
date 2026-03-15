# Makefile for Spec2Test
# Usage:
#   make dev                # runs scripts/run_all.sh (prefers docker if available)
#   make dev DOC_SOURCE=/path/or/url   # pass a DOC_SOURCE override
#   make dev-local          # force local run (sets FORCE_LOCAL=1)
#   make dev-docker         # force docker run (passes 'docker' to start_dev.sh)
#   make stop               # stop started services (uses PID files)

DOC_SOURCE ?= $(shell pwd)/docs
SHELL := /bin/zsh

.PHONY: dev dev-local dev-docker stop help

help:
	@echo "Makefile targets:"
	@echo "  make dev           # start full pipeline (wrapper uses Docker when available)"
	@echo "  make dev DOC_SOURCE=/path  # override DOC_SOURCE"
	@echo "  make dev-local     # force local mode (no Docker)"
	@echo "  make dev-docker    # force docker mode"
	@echo "  make stop          # kill services started by scripts (uses logs/*.pid)"

dev:
	@echo "Running full pipeline (dev) with DOC_SOURCE=$(DOC_SOURCE)"
	@./scripts/run_all.sh "$(DOC_SOURCE)"

dev-local:
	@echo "Running full pipeline (local) with DOC_SOURCE=$(DOC_SOURCE)"
	@FORCE_LOCAL=1 ./scripts/run_all.sh "$(DOC_SOURCE)"

dev-docker:
	@echo "Running full pipeline (docker) with DOC_SOURCE=$(DOC_SOURCE)"
	@./scripts/run_all.sh "$(DOC_SOURCE)" --install

stop:
	@echo "Stopping services (if running)"
	@kill $$(cat logs/uvicorn.pid 2>/dev/null || echo) 2>/dev/null || true
	@kill $$(cat logs/celery.pid 2>/dev/null || echo) 2>/dev/null || true
	@kill $$(cat logs/frontend.pid 2>/dev/null || echo) 2>/dev/null || true
	@pkill -f 'uvicorn backend.app' 2>/dev/null || true
	@pkill -f 'celery -A backend.celery_app' 2>/dev/null || true
	@pkill -f 'next dev' 2>/dev/null || true
	@echo "Stopped (best effort)."
