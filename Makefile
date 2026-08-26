.PHONY: dev start

dev:
	uv run uvicorn app.main:app --reload

start:
	uv run uvicorn app.main:app
