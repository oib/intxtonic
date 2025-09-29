PYTHON?=.venv/bin/python
PIP?=.venv/bin/pip

.PHONY: venv install dev test apply-schema seeds ci

venv:
	python3 -m venv .venv
	$(PIP) install -U pip

install: venv
	$(PIP) install -r requirements.txt

apply-schema:
	PGPASSWORD=$(DB_PASSWORD) psql -h $(DB_HOST) -p $(DB_PORT) -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1 -f src/backend/app/db/schema.sql

seeds:
	PGPASSWORD=$(DB_PASSWORD) psql -h $(DB_HOST) -p $(DB_PORT) -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1 -f src/backend/app/db/seeds/initial.sql

dev: install
	bash scripts/dev_run.sh

test: install
	APP_ENV=test .venv/bin/pytest -q --cov=src/backend --cov-report=term-missing

ci:
	APP_ENV=ci .venv/bin/pytest -q --cov=src/backend --cov-report=xml
