.PHONY: dev start docker-build docker-up docker-down

dev:
	uv run uvicorn app.main:app --reload

start:
	uv run uvicorn app.main:app

docker-build:
	docker build -t routing-engine:latest .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
