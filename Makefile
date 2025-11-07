.PHONY: help install services start worker stop clean test format lint docker-up docker-down docker-logs docker-restart docker-clean

help:
	@echo "RAG Service - Available Commands:"
	@echo ""
	@echo "Local Development:"
	@echo "  make install    - Install dependencies and setup environment"
	@echo "  make services   - Start Docker services (Qdrant & Redis only)"
	@echo "  make start      - Start the API server (local)"
	@echo "  make worker     - Start the background worker (local)"
	@echo ""
	@echo "Docker (Full Stack):"
	@echo "  make docker-up       - Build and start ALL services in Docker"
	@echo "  make docker-down     - Stop all Docker services"
	@echo "  make docker-logs     - View logs from all services"
	@echo "  make docker-restart  - Restart all Docker services"
	@echo "  make docker-clean    - Stop and remove all containers and volumes"
	@echo ""
	@echo "Utilities:"
	@echo "  make stop       - Stop Docker services"
	@echo "  make clean      - Clean up data and caches"
	@echo "  make test       - Run tests"
	@echo "  make format     - Format code with black"
	@echo "  make lint       - Lint code with ruff"
	@echo ""

install:
	@echo "Installing dependencies..."
	poetry install
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please configure it"; fi

services:
	@echo "Starting Docker services (Qdrant & Redis only)..."
	docker-compose up -d qdrant redis
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Services started!"
	@echo "Qdrant: http://localhost:6333/dashboard"
	@echo "Redis: localhost:6379"

start:
	@echo "Starting API server..."
	poetry run python main.py

worker:
	@echo "Starting background worker..."
	poetry run python worker.py

stop:
	@echo "Stopping Docker services..."
	docker-compose down

clean:
	@echo "Cleaning up..."
	rm -rf data/uploads/* data/processed/* data/chunks/*
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned!"

test:
	@echo "Running tests..."
	poetry run pytest tests/ -v

format:
	@echo "Formatting code..."
	poetry run black src/ tests/
	@echo "Done!"

lint:
	@echo "Linting code..."
	poetry run ruff check src/ tests/
	@echo "Done!"

docker-up:
	@./scripts/docker-start.sh

docker-down:
	@echo "Stopping all Docker services..."
	docker-compose down
	@echo "Services stopped!"

docker-logs:
	@echo "Showing logs (Ctrl+C to exit)..."
	docker-compose logs -f

docker-restart:
	@echo "Restarting all Docker services..."
	docker-compose restart
	@echo "Services restarted!"

docker-clean:
	@echo "WARNING: This will remove all containers and volumes (data will be lost)!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "All containers and volumes removed!"; \
	else \
		echo "Cancelled."; \
	fi

logs:
	docker-compose logs -f
