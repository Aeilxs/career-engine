.PHONY: lock sync lint format-check typecheck test check up down verify-j0

lock:
	uv lock --python 3.14

sync:
	uv sync --frozen

lint:
	uv run --frozen ruff check .

format-check:
	uv run --frozen ruff format --check .

typecheck:
	uv run --frozen mypy src

test:
	uv run --frozen pytest -q

check: lint format-check typecheck test

up:
	bash scripts/init-local.sh
	docker compose up --build -d --wait

down:
	docker compose down

verify-j0:
	bash scripts/verify-j0.sh
