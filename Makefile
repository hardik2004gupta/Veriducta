.PHONY: install run test lint format type-check docker-up docker-down coverage clean pre-commit

PYTHON := python
UV := uv

install:
	$(UV) pip install --system ".[dev]"
	pre-commit install

run:
	$(PYTHON) -m api.app

test:
	pytest

lint:
	ruff check .

format:
	ruff format .
	black .

type-check:
	mypy .

pre-commit:
	pre-commit run --all-files

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

coverage:
	pytest --cov=. --cov-report=html
	@echo "Open htmlcov/index.html to view the coverage report."

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
