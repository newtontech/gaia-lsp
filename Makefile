.PHONY: install lint test typecheck build vscode upstream-examples package-check release-check check

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

vscode:
	cd gaia-vscode && npm run lint && npm test && npm run package

upstream-examples:
	PYTHONPATH=src scripts/check_upstream_examples.sh

package-check: build
	python3 -m twine check dist/*
	cd gaia-vscode && npm audit --audit-level=moderate

release-check: lint typecheck test package-check vscode upstream-examples
