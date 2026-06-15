.PHONY: install lint test typecheck build check

install:
	python3 -m pip install -e ".[dev]"

lint:
	ruff check src tests

test:
	python3 -m pytest

typecheck:
	mypy src

check: lint typecheck test build

build:
	python3 -m build
