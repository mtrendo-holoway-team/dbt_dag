.PHONY: lint test

lint:
	poetry run autoflake --remove-all-unused-imports --recursive --check src tests
	poetry run isort --check-only src tests
	poetry run black --check src tests
	poetry run flake8 src tests
	poetry run mypy src tests

test:
	poetry run pytest
