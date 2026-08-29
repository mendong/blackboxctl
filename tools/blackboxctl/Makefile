PYTHON ?= python3

.PHONY: help selftest doctor test lint

help:
	@echo "make selftest  - offline protocol checks"
	@echo "make doctor    - host/MIDI/M-EFCS readiness"
	@echo "make test      - pytest"
	@echo "make lint      - ruff format and check"

selftest:
	$(PYTHON) -m blackboxctl selftest

doctor:
	$(PYTHON) -m blackboxctl doctor

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff format --check blackboxctl tests
	$(PYTHON) -m ruff check blackboxctl tests
