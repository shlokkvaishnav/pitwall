.PHONY: install test lint format check fix-pth
install:
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]" && $(MAKE) fix-pth
test:
	.venv/bin/pytest -q
lint:
	.venv/bin/ruff check src tests
format:
	.venv/bin/ruff format src tests
# Do this before each push. A failed CI run sends an email.
check: lint test
fix-pth:
	@# macOS can hide .pth files. Then Python does not read them, and the editable install stops.
	@chflags nohidden .venv/lib/*/site-packages/*.pth 2>/dev/null || true
