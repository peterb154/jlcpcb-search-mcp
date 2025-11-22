.PHONY: lint lint-fix test test-cov test-quick install dev clean release version help

help:
	@echo "Available targets:"
	@echo "  make lint       - Run ruff linter (check only)"
	@echo "  make lint-fix   - Run ruff linter and auto-fix issues"
	@echo "  make test       - Run pytest tests with coverage"
	@echo "  make test-cov   - Run tests with detailed coverage report"
	@echo "  make test-quick - Run tests without coverage (faster)"
	@echo "  make install    - Install package in development mode"
	@echo "  make dev        - Install package with dev dependencies"
	@echo "  make version    - Show next version (dry-run)"
	@echo "  make release    - Create a new release (bumps version, creates tag)"
	@echo "  make clean      - Remove build artifacts and cache files"

lint:
	@echo "Running ruff linter..."
	uv run ruff check src/

lint-fix:
	@echo "Running ruff linter with auto-fix..."
	uv run ruff check --fix src/
	uv run ruff format src/

test:
	@echo "Running tests with coverage..."
	uv run pytest tests/ -v

test-cov:
	@echo "Running tests with detailed coverage report..."
	uv run pytest tests/ --cov=jlcpcb_mcp --cov-report=term-missing --cov-report=html

test-quick:
	@echo "Running tests without coverage..."
	uv run pytest tests/ -v --no-cov

install:
	@echo "Installing package in development mode..."
	uv pip install -e .

dev:
	@echo "Installing with dev dependencies..."
	uv sync --group dev

version:
	@echo "Checking next version (dry-run)..."
	uv run semantic-release version --no-commit --no-tag --no-push

release:
	@echo "Creating new release..."
	uv run semantic-release version
	@echo "Release created! Don't forget to push: git push --follow-tags"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
