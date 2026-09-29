.PHONY: help install dev-api dev-web test lint

help:
	@echo "EDOS Foundation Commands:"
	@echo "  make install     - Install backend and frontend dependencies"
	@echo "  make dev-api     - Run FastAPI backend development server"
	@echo "  make dev-web     - Run Next.js frontend development server"
	@echo "  make test        - Run backend test suite (pytest)"
	@echo "  make lint        - Run frontend linting (next lint)"

install:
	cd apps/api && pip install -e ".[dev]"
	cd apps/web && npm install

dev-api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

dev-web:
	cd apps/web && npm run dev

test:
	cd apps/api && pytest

lint:
	cd apps/web && npm run lint
