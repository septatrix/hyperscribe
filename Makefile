.DEFAULT_GOAL := help
.PHONY: help sync test docs doctest lint format format-check check check-templates check-cdedb2 collect-cdedb2 clean

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

check-templates: ## Type-check annotated Jinja templates (experimental)
	PYTHONPATH=experiments/jinja_typecheck $(UV_RUN) --group benchmarks python -m tplcheck benchmarks/templates \
		--shadow-dir build/tplcheck --stub benchmarks/typed_templates.pyi \
		--config-file experiments/jinja_typecheck/mypy.ini

CDEDB_CASE := experiments/jinja_typecheck/examples/cdedb2
CDEDB_CHECK = MYPYPATH=build:$(CDEDB_CASE):$(CDEDB2) PYTHONPATH=experiments/jinja_typecheck:build:$(CDEDB_CASE) \
	$(UV_RUN) python -m tplcheck build/cdedb2_templates --shadow-dir build/cdedb2_shadow \
	--config-file $(CDEDB_CASE)/cdedb2.ini \
	--extension jinja2.ext.i18n --extension jinja2.ext.do --extension jinja2.ext.loopcontrols \
	--filters-registry cdedb_filters:JINJA_FILTERS --tests-module cdedb_tests \
	--globals-module cdedb_globals

check-cdedb2: ## Case study: type-check cdedb2's index page (CDEDB2=path to a checkout)
	@test -n "$(CDEDB2)" || { echo "usage: make check-cdedb2 CDEDB2=/path/to/cdedb2"; exit 1; }
	$(UV_RUN) python $(CDEDB_CASE)/prepare.py $(CDEDB2) build/cdedb2_templates
	$(CDEDB_CHECK)

collect-cdedb2: ## Case study: generate contexts from cdedb2's render() calls, then check
	@test -n "$(CDEDB2)" || { echo "usage: make collect-cdedb2 CDEDB2=/path/to/cdedb2"; exit 1; }
	mkdir -p build
	cd $(CDEDB2) && PYTHONPATH=$(CURDIR)/experiments/jinja_typecheck:$(CURDIR)/$(CDEDB_CASE) \
		$(CURDIR)/.venv/bin/python -m tplcheck.collect \
		--render cdedb.frontend.common.AbstractFrontend.render \
		--module cdedb_contexts --out $(CURDIR)/build/cdedb_contexts.py \
		--mapper cdedb_mapper:mapper --base-context cdedb_ctx.BaseContext \
		-- --python-version 3.14 --ignore-missing-imports --follow-imports=silent \
		--no-site-packages --explicit-package-bases cdedb/frontend
	$(UV_RUN) python $(CDEDB_CASE)/prepare.py $(CDEDB2) build/cdedb2_templates --generated
	$(CDEDB_CHECK) --contexts-module cdedb_contexts

format: ## Format the code with ruff
	$(UV_RUN) ruff format .

format-check: ## Check formatting without changing files
	$(UV_RUN) ruff format --check .

check: lint format-check test doctest ## Run everything CI would run

clean: ## Remove build artifacts and caches
	rm -rf dist docs/_build .pytest_cache .mypy_cache .ruff_cache .benchmarks
