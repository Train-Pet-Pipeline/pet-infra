.PHONY: setup test lint clean clearml-up clearml-down smoke-mps

setup:
	python -m pip install -e ".[dev,api,sync]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/ && mypy src/

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

clearml-up:
	cd docker/clearml && docker compose up -d

clearml-down:
	cd docker/clearml && docker compose down

smoke-mps:
	pet run recipes/smoke_mps.yaml
