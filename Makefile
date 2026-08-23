# Makefile for Autonomous Software Recovery & Trust PaaS

.PHONY: install-backend install-frontend test-backend test-frontend docker-up docker-down

install-backend:
	pip install -r apps/api/requirements.txt
	pip install pytest pytest-asyncio pytest-cov

install-frontend:
	cd frontend && npm install

test-backend:
	pytest tests/

test-frontend:
	cd frontend && npm run test

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v
