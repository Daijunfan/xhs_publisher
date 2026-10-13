.PHONY: setup check test format run start status stop preflight backup

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install 'uv==0.12.5'
	.venv/bin/uv sync --frozen --extra dev
	.venv/bin/python -m xhs_local migrate

check:
	.venv/bin/ruff check src tests
	.venv/bin/python -m compileall -q src tests

test:
	.venv/bin/pytest

format:
	.venv/bin/ruff format src tests ops

run:
	.venv/bin/python -m xhs_local run

start:
	.venv/bin/python -m xhs_local start

status:
	.venv/bin/python -m xhs_local status

stop:
	.venv/bin/python -m xhs_local stop

preflight:
	.venv/bin/python -m xhs_local check

backup:
	.venv/bin/python -m xhs_local backup
