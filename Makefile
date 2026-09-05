# Everything a contributor needs, without reading the CI files.
.PHONY: help install check offline collect derive build serve record fixtures cloud-sync clean

help:
	@echo "make install      install the package and dev tools into the current environment"
	@echo "make cloud-sync   pull newly department-built services from vhp4safety/cloud"
	@echo "make check        config validation, lint, and the offline test suite"
	@echo "make offline      build the whole site from fixtures with no network at all"
	@echo "make collect      fetch every enabled source live"
	@echo "make serve        build and serve the site at http://localhost:8000"
	@echo "make record       re-record HTTP fixtures from live APIs, then trim them"

install:
	pip install -e ".[dev]"

check:
	tgx doctor
	ruff check src tests
	pytest -q

# The important target. If this passes, the build has no hidden network dependency and
# needs no credential -- which is what makes the project safe to fork and to hand over.
offline:
	TGX_HTTP_MODE=replay tgx collect --replay
	tgx derive
	tgx build
	mkdocs build --strict
	@echo "\n  built offline, with no network and no secrets"

collect:
	tgx collect

derive:
	tgx derive

build:
	tgx build
	mkdocs build

serve: build
	mkdocs serve

record:
	tgx collect --record
	$(MAKE) fixtures

# Recorded responses are what upstream actually returned -- for Bioconductor that is a
# 12 MB table. Trim before committing.
fixtures:
	python tests/trim_fixtures.py

# See VHP_CLOUD_INPUT.md for what this leaves for a person, and the script's own
# docstring for what it decides on its own and what it won't guess at. Review the
# diff before committing -- it writes config/projects.csv and config/identifiers.csv
# directly.
cloud-sync:
	python scripts/cloud_sync.py
	tgx doctor

clean:
	rm -rf site includes/*.md docs/data/*.csv
