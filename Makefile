.PHONY: install dev test lint typecheck fmt todos clean web-install web-dev

install:  ## Install package + dev deps in editable mode
	pip install -e ".[dev]"

dev:  ## Run the control-plane API with auto-reload
	uvicorn agent_workspaces.main:app --reload --host $${AWS_API_HOST:-0.0.0.0} --port $${AWS_API_PORT:-8000}

web-install:  ## Install frontend dependencies
	cd frontend && npm install

web-dev:  ## Run the frontend dev server (Vite)
	cd frontend && npm run dev

test:  ## Run the test suite
	pytest -q

lint:  ## Lint with ruff
	ruff check src tests

typecheck:  ## Static type check with mypy
	mypy src

fmt:  ## Auto-format + fix imports
	ruff format src tests
	ruff check --fix src tests

todos:  ## List every TODO left in the scaffold
	@grep -rn "TODO:" src tests || echo "No TODOs left — nice."

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__ *.egg-info
