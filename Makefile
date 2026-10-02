.DEFAULT_GOAL := help
.PHONY: help sync test docs doctest lint format format-check check clean

UV_RUN := uv run

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

sync: ## Install the development and docs dependencies
	uv sync

test: ## Run the test suite
	$(UV_RUN) pytest

docs: ## Build the HTML documentation into docs/_build/html
	$(UV_RUN) sphinx-build -W --keep-going -b html docs docs/_build/html

doctest: ## Run the examples in the documentation
	$(UV_RUN) sphinx-build -W --keep-going -b doctest docs docs/_build/doctest

lint: ## Lint with ruff and type-check with mypy
	$(UV_RUN) ruff check .
	@# mypy needs the benchmark libraries installed to check their types
	$(UV_RUN) --group benchmarks mypy

format: ## Format the code with ruff
	$(UV_RUN) ruff format .

format-check: ## Check formatting without changing files
	$(UV_RUN) ruff format --check .

check: lint format-check test doctest ## Run everything CI would run

clean: ## Remove build artifacts and caches
	rm -rf dist docs/_build .pytest_cache .mypy_cache .ruff_cache .benchmarks
