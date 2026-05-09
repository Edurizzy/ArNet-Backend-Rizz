# Makefile for ArNet Backend Development
# Provides convenient commands for common development tasks

.PHONY: help setup build up down logs shell migrate test lint format clean backup

# Default target
help:
	@echo "ArNet Backend Development Commands"
	@echo "=================================="
	@echo "setup     - Initial project setup"
	@echo "build     - Build Docker containers"
	@echo "up        - Start all services"
	@echo "down      - Stop all services"
	@echo "logs      - View Docker logs"
	@echo "shell     - Access Django shell in container"
	@echo "migrate   - Run database migrations"
	@echo "test      - Run tests"
	@echo "lint      - Run code linting"
	@echo "format    - Format code with Black"
	@echo "clean     - Clean up containers and volumes"
	@echo "backup    - Backup database"

# Initial setup
setup:
	@echo "Setting up ArNet Backend..."
	cp .env.example .env
	@echo "Please edit .env with your configuration"
	@echo "Then run: make build && make up"

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-django:
	docker-compose logs -f django

logs-celery:
	docker-compose logs -f celery

# Database commands
migrate:
	docker-compose exec django python manage.py migrate

makemigrations:
	docker-compose exec django python manage.py makemigrations

createsuperuser:
	docker-compose exec django python manage.py createsuperuser

# Development commands
shell:
	docker-compose exec django python manage.py shell

shell-bash:
	docker-compose exec django bash

collectstatic:
	docker-compose exec django python manage.py collectstatic --noinput

# Testing
test:
	docker-compose exec django python manage.py test

test-coverage:
	docker-compose exec django coverage run --source='.' manage.py test
	docker-compose exec django coverage report -m

# Code quality
lint:
	docker-compose exec django flake8 .
	docker-compose exec django mypy .

format:
	docker-compose exec django black .
	docker-compose exec django isort .

# Celery commands
celery-worker:
	docker-compose exec celery celery -A core.celery worker --loglevel=info

celery-beat:
	docker-compose exec celery-beat celery -A core.celery beat --loglevel=info

celery-flower:
	docker-compose exec celery celery -A core.celery flower

# Maintenance
clean:
	docker-compose down -v
	docker system prune -f

clean-all:
	docker-compose down -v --rmi all
	docker system prune -af

backup:
	@echo "Creating database backup..."
	docker-compose exec postgres pg_dump -U postgres arnet_dev > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

# Production commands
prod-build:
	docker build -f Dockerfile -t arnet-backend:latest .

prod-deploy:
	@echo "Production deployment commands go here"
	@echo "This should be customized for your deployment strategy"

# Development tools
install-dev:
	pip install -r requirements.txt
	pip install black isort flake8 mypy coverage

run-local:
	python manage.py runserver

# Database utilities
reset-db:
	docker-compose down
	docker volume rm arnet-backend-rizz_postgres_data
	docker-compose up -d postgres
	sleep 5
	make migrate
	@echo "Database reset complete"

seed-data:
	docker-compose exec django python manage.py loaddata fixtures/initial_data.json