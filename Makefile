.PHONY: install test lint format check fix-pth data reproduce docker-reproduce
install:
	python3 -m venv .venv && .venv/bin/pip install -q -c requirements.lock -e ".[dev,model]" && $(MAKE) fix-pth
test:
	.venv/bin/pytest -q
	node --test tests/js/*.test.mjs
lint:
	.venv/bin/ruff check src tests scripts
	.venv/bin/mypy src
format:
	.venv/bin/ruff format src tests
# Do this before each push. A failed CI run sends an email.
check: lint test
fix-pth:
	@# macOS can hide .pth files. Then Python does not read them, and the editable install stops.
	@chflags nohidden .venv/lib/*/site-packages/*.pth 2>/dev/null || true

PY = PYTHONPATH=src $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
SCRIPTS = lap_baselines lap_model race_sim race_sim_b undercut undercut_b undercut_replication \
          undercut_open export_undercut_model holdout lap_intervals undercut_power decision_regret

# Download the public data (Jolpica dump with a pinned SHA-256, TracingInsights tyre files).
data:
	$(PY) scripts/fetch_dump.py
	$(PY) scripts/fetch_tyres.py --seasons 2018 2019 2020 2021 2022 2023 2024 2025 2026 --holdout 13 14 15 16 17 18

# Rebuild every result in results/ and the site model from the raw data. data_check.py is not in the list,
# because rule D4 needs the old API cache.
reproduce: data
	@for s in $(SCRIPTS); do echo "== $$s"; $(PY) scripts/$$s.py > /dev/null || exit 1; done
	$(PY) scripts/compare_results.py

# The same in a clean container. The data folder is mounted, so the download is done only once.
docker-reproduce:
	docker build -t pitwall .
	docker run --rm -v "$(CURDIR)/data:/app/data" -v "$(CURDIR)/results:/app/results" \
		-v "$(CURDIR)/site/data:/app/site/data" pitwall
